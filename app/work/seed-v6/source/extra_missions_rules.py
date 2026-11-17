"""Experimental seed-driven Extra Mission ENE and group-bound script changes.

Qualified computed actor selectors retain their instructions while the exact
script group/species pairs feeding them are updated. Live mission objectives
and the vs_tr01 crash repair remain unverified.
"""
import json
import struct
from collections import defaultdict

from archive_tools import L
from mixed_boss_catalog import payloads
from side_enemy_rules import slots_in
from scx_bytecode import native_calls
from scx_manager_chain_adapter import MANAGER_TYPES
from native_seed_rules import REGULAR_TYPES
from regular_selectors import triples,patch as patch_selectors
from randomizer_settings import weighted_enemy
from verified_extra_type_pairs import patch as patch_group_types

STAGES=('vs_sp01','vs_ex01','vs_fa01','vs_af01','vs_tr01','vs_ef03')
BOSS_STAGE='vs_ca02'
PAIRED_SCRIPT_STAGES=frozenset(('vs_sp01','vs_ex01','vs_fa01','vs_af01','vs_tr01'))
UNQUALIFIED=('vs_af01g','vs_cf01','ex02','ex03','ex04')


def build(seed,stock,weights):
    selectors={int(key,16) for key in json.loads((L/'type-selector-command-catalog.json').read_text())['commands']}
    rows=[];updates={}
    for stage in STAGES:
        files=payloads(stock,stage);changed=files.copy()
        slots=[slot for name,data in files.items() if name.endswith('.ene') for slot in slots_in(name,data)]
        groups=defaultdict(set)
        for slot in slots:groups[slot['script_group_id']].add(slot['original_type'])
        managers={MANAGER_TYPES[h] for name,data in files.items() if name.endswith('.scx')
                  for at,h in native_calls(data) if h in MANAGER_TYPES}&REGULAR_TYPES
        sources={s['original_type'] for s in slots}&managers
        if not sources or len(managers)<2:raise ValueError('No qualified Extra Mission native pool: '+stage)
        mapping={typ:weighted_enemy(seed,stage,'extra-native/'+str(typ),sorted(managers-{typ}),weights)
                 for typ in sorted(sources)}
        computed=[];literal=[];paired=[]
        for name,data in files.items():
            if not name.endswith('.scx'):continue
            if stage in PAIRED_SCRIPT_STAGES:
                selected_groups={group:types for group,types in groups.items()
                                 if struct.pack('<I',group) in data}
                if selected_groups:
                    changed[name],edits=patch_group_types(data,selected_groups,mapping)
                    paired.extend(dict(file=name,**edit) for edit in edits)
            selected=[]
            for at,h in native_calls(data):
                if h not in selectors:continue
                parts=triples(data,at,h)
                dynamic=[(group,typ) for group,typ,ordinal in parts
                         if typ['kind']!=0xc0 or typ['offset'] is None]
                if dynamic:
                    if any(group['kind']!=0xb1 or typ['kind']!=0xb1 for group,typ in dynamic):
                        raise ValueError('Unsupported computed Extra Mission selector: '+stage)
                    if any(len(types)!=1 for types in groups.values()):
                        raise ValueError('Computed selector has mixed ENE group: '+stage)
                    computed.append(dict(file=name,offset=at,command=f'{h:08x}'))
                    continue
                selected.append(dict(offset=at,command=h))
            if selected:
                changed[name],edits=patch_selectors(changed[name],selected,mapping,slots)
                literal.extend(edits)
        if stage in PAIRED_SCRIPT_STAGES:
            changed_groups={group for group,types in groups.items()
                            if len(types)==1 and mapping.get(next(iter(types)),next(iter(types)))!=next(iter(types))}
            if len(paired)!=2*len(changed_groups) or {edit['group'] for edit in paired}!=changed_groups:
                raise ValueError('Extra Mission group-bound script pair coverage differs: '+stage)
        enemy_edits=0
        for slot in slots:
            typ=slot['original_type']
            if typ not in mapping:continue
            name,at=slot['file'],slot['offset'];body=bytearray(changed[name])
            if body[at:at+3]!=bytes((typ,slot['count'],slot['level'])):
                raise ValueError('Extra Mission ENE source changed: '+stage)
            body[at]=mapping[typ];changed[name]=bytes(body)
            enemy_edits+=typ!=mapping[typ]
        if not enemy_edits:raise ValueError('Extra Mission stage did not visibly change: '+stage)
        updates[stage]={name:data for name,data in changed.items() if data!=files[name]}
        rows.append(dict(stage=stage,mapping=mapping,regular_type_edits=enemy_edits,
            preserved_computed_selectors=computed,literal_selector_edits=len(literal),
            group_bound_script_type_edits=len(paired),
            ENE_groups_single_type=all(len(types)==1 for types in groups.values()),
            changed_files=sorted(updates[stage]),gameplay_verified=False))
    return updates,dict(format=1,seed=seed,stages=rows,all_qualified_changed=True,
        unqualified_sections=list(UNQUALIFIED),
        limitation='vs_tr01 has a group-bound script type repair candidate after the live null-actor crash; it needs a new gameplay retest. The irregular vs_af01g section and other listed unqualified sections retain native data. Objectives remain to be tested in game.',
        gameplay_verified=False)
