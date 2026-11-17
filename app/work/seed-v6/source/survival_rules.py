"""Deterministic six-stage Survival enemy preparation.

Each stage retains its native objectives and actor families that are not in a
qualified replacement pool. The report describes the resulting coverage.
"""
import hashlib
import json
import struct

from archive_tools import L
from mixed_boss_catalog import payloads
from side_enemy_rules import slots_in,candidates as side_candidates
from opening_enemies import prepare as opening_prepare,asset_set
from ship_enemies import prepare as ship_prepare
from randomizer_settings import weighted_enemy,enemy_level
from actor_reference_adapter import patch_references
from scx_bytecode import native_calls
from scx_manager_chain_adapter import MANAGER_TYPES

STAGES=('vs_ca01','vs_ba01','vs_wn02','vs_fr01','vs_mf01','vs_am01')
SHIP_SCRIPT='f51c3297.scx'
SHIP_SITES=(27389,)


def slots(stock,stage):
    files=payloads(stock,stage)
    return [slot for name,data in files.items() if name.endswith('.ene')
            for slot in slots_in(name,data)]


def narita_singleton(seed,stock,weights,levels,selectors):
    stage='vs_wn02';original=payloads(stock,stage)
    authored=slots(stock,stage)
    if len(authored)!=32 or {s['original_type'] for s in authored}!={31}:
        raise ValueError('Survival Stage 3 Narita source changed')
    target=weighted_enemy(seed,stage,'survival-single',[41,42],weights)
    if target==31:raise ValueError('Survival Stage 3 did not select a replacement')
    resources,donor,command=asset_set(stock,target)
    changed=original.copy();manager_sites=[];selector_edits=[];level_edits=[]
    for name,data in original.items():
        if not name.endswith('.scx'):continue
        calls=native_calls(data)
        patched,refs=patch_references(data,[dict(offset=at,command=h) for at,h in calls if h in selectors],{31:target})
        selector_edits.extend(refs)
        body=bytearray(patched)
        for at,h in calls:
            if h not in MANAGER_TYPES:continue
            if MANAGER_TYPES[h]!=31:raise ValueError('Unexpected Survival Stage 3 manager')
            body[at+1:at+5]=struct.pack('<I',command)
            manager_sites.append(dict(file=name,offset=at,original=f'{h:08x}',target=f'{command:08x}'))
        changed[name]=bytes(body)
    if len(manager_sites)!=1:raise ValueError('Survival Stage 3 manager site changed')
    for slot in authored:
        name,at=slot['file'],slot['offset'];body=bytearray(changed[name])
        if body[at:at+3]!=bytes((31,slot['count'],slot['level'])):
            raise ValueError('Survival Stage 3 ENE source changed')
        level=enemy_level(seed,stage,name+'/'+str(at),slot['level'],levels)
        body[at]=target;body[at+2]=level;changed[name]=bytes(body)
        if level!=slot['level']:level_edits.append(dict(file=name,offset=at+2,original=slot['level'],target=level))
    imported={name:data for name,data in resources.items() if name not in original}
    changed.update(resources)
    aliases={label:{'@'+stage+'_'+name[:8]+suffix:'@'+donor+'_'+name[:8]+suffix
                    for name in resources if name.endswith('.tex') for suffix in ('.dat','.tbl')}
             for label in ('main','small')}
    report=dict(stage=stage,target=target,donor=donor,slots_changed=len(authored),
                manager_sites=manager_sites,selector_edits=len(selector_edits),level_edits=level_edits,
                imported_resources={name:hashlib.sha256(data).hexdigest() for name,data in imported.items()},
                gameplay_verified=False)
    return changed,report,aliases


def build(seed,stock,weights,levels=False):
    selectors={int(key,16) for key in json.loads((L/'type-selector-command-catalog.json').read_text())['commands']}
    updates={};aliases={'main':{},'small':{}};reports=[]
    def take(stage,files,report,stage_aliases):
        original=payloads(stock,stage)
        updates[stage]={name:data for name,data in files.items() if name not in original or data!=original[name]}
        if not updates[stage]:raise ValueError('Survival stage did not visibly change: '+stage)
        reports.append(report)
        for label in aliases:
            overlap=set(aliases[label])&set(stage_aliases[label])
            if overlap:raise ValueError('Duplicate Survival atlas alias')
            aliases[label].update(stage_aliases[label])
    stage=STAGES[0]
    files,edits,logs,report,stage_aliases=opening_prepare(seed,stock,stage,
        dict(stage=stage,slots=slots(stock,stage)),weights,levels,selectors)
    if len(logs)!=9 or report['manager_calls']!=2 or not any(r['enemy']!=r['original_type'] for r in logs):
        raise ValueError('Survival Stage 1 Raptor replacement incomplete')
    report=dict(report,enemy_slots=len(logs),changed_enemy_slots=sum(r['enemy']!=r['original_type'] for r in logs),
                slot_changes=[dict(file=r['file'],offset=r['offset'],source=r['original_type'],target=r['enemy']) for r in logs],
                native_swarm_slots_preserved=4,mode='survival',gameplay_verified=False)
    take(stage,files,report,stage_aliases)
    stage=STAGES[1]
    files,edits,logs,report,stage_aliases=ship_prepare(seed,stock,
        dict(stage=stage,slots=slots(stock,stage)),weights,levels,selectors,
        stage=stage,script=SHIP_SCRIPT,sites=SHIP_SITES,force_different=True)
    if not report['adapters'] or not all(r['enemy']!=r['original_type'] for r in logs if r['original_type']==40):
        raise ValueError('Survival Stage 2 guarded Raptor replacement incomplete')
    if any(r['enemy']!=32 for r in logs if r['original_type']==32):
        raise ValueError('Survival Stage 2 Mummyhead identity changed')
    report=dict(report,enemy_slots=len(logs),changed_enemy_slots=sum(r['enemy']!=r['original_type'] for r in logs),
                slot_changes=[dict(file=r['file'],offset=r['offset'],source=r['original_type'],target=r['enemy']) for r in logs],
                native_secondary_actors_preserved=True,mode='survival')
    take(stage,files,report,stage_aliases)
    stage=STAGES[2]
    files,report,stage_aliases=narita_singleton(seed,stock,weights,levels,selectors)
    take(stage,files,report,stage_aliases)
    side_report,side_updates=side_candidates(stock,seed,weights)
    for stage in STAGES[3:]:
        entry=next(row for row in side_report['stages'] if row['stage']==stage)
        if stage not in side_updates or not entry['qualified'] or not entry['enemy_type_changes']:
            raise ValueError('Survival Stage native pool did not visibly change: '+stage+' / '+entry.get('reason',''))
        files=payloads(stock,stage).copy();files.update(side_updates[stage])
        take(stage,files,dict(entry,mode='survival',gameplay_verified=False),{'main':{},'small':{}})
    return updates,dict(format=1,seed=seed,stages=reports,all_six_changed=True,
                        level_policy='Stage 4–6 levels retain their authored values',gameplay_verified=False),aliases
