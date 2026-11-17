"""Fresh side-mode archive readback against deterministic original inputs."""
import hashlib
import json
from pathlib import Path

from archive_tools import Archive,VAN,sha
from mixed_boss_catalog import payloads
from original_inputs import resolve_stage
from settings_contract import normalise,effective
from survival_rules import build as build_survival,STAGES as SURVIVAL_STAGES
from boss_sequence_rules import (build as build_sequence,STAGES as SEQUENCE_STAGES,
                                 PROTECTED as SEQUENCE_PROTECTED,sound_packs)
from extra_missions_rules import build as build_extra,STAGES as EXTRA_STAGES,BOSS_STAGE as EXTRA_BOSS_STAGE


def need(condition,message):
    if not condition:raise ValueError(message)


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def verify(package):
    p=Path(package).resolve();m=read(p/'manifest.json')
    requested=normalise(read(p/'randomisation-settings.json'))
    applied=effective(requested)['applied']
    seed=m['seed']
    original=resolve_stage(VAN);stock=Archive(original['path']);actual=Archive(p/'STAGE.DAT')
    need(sha(actual.path)==m['patched_sha256'],'Side-mode archive digest differs')
    expected_updates={};expected_aliases={'main':{},'small':{}};expected_sound={}
    expected_report=dict(format=1,seed=seed,boss_sequence=None,survival=None,extra_missions=None,
                         gameplay_verified=False)
    def add_aliases(pairs):
        for label in expected_aliases:
            overlap=set(expected_aliases[label])&set(pairs[label])
            need(not overlap,'Side-mode atlas alias collision')
            expected_aliases[label].update(pairs[label])
    if applied['randomise_survival']:
        changes,expected_report['survival'],aliases=build_survival(
            seed,stock,applied['enemy_percentages'],applied['randomise_enemy_levels'])
        expected_updates.update(changes);add_aliases(aliases)
    if applied['randomise_boss_sequence']:
        changes,expected_report['boss_sequence'],aliases,expected_sound=build_sequence(seed,stock,applied)
        need(not set(changes)&set(expected_updates),'Side-mode stage overlap')
        expected_updates.update(changes);add_aliases(aliases)
    if applied['randomise_extra_missions']:
        changes,expected_report['extra_missions']=build_extra(seed,stock,applied['enemy_percentages'])
        expected_report['extra_missions']['boss_battle']=None
        need(not set(changes)&set(expected_updates),'Extra Mission stage overlap')
        expected_updates.update(changes)
        if applied['boss_mode']=='shuffle_test':
            from boss_sequence_rules import NATIVE as SEQUENCE_NATIVE
            battle_changes,battle_report,battle_aliases,battle_sounds=build_sequence(
                seed,stock,applied,(EXTRA_BOSS_STAGE,),dict(SEQUENCE_NATIVE,vs_ca02='Ardjet'),False)
            need(not set(battle_changes)&set(expected_updates),'Extra Mission boss stage overlap')
            expected_updates.update(battle_changes);add_aliases(battle_aliases)
            expected_report['extra_missions']['boss_battle']=battle_report['encounters'][0]
            expected_sound.update(battle_sounds)
    need(set(expected_updates)==set(m.get('side_mode_stages',[])),'Side-mode stage list differs')
    for stage in SEQUENCE_PROTECTED:
        if applied['randomise_boss_sequence']:
            before=payloads(stock,stage);after=payloads(actual,stage)
            need(before==after,'Protected Boss Sequence fight changed: '+stage)
            need(sound_packs(stock,stage)==sound_packs(actual,stage),
                 'Protected Boss Sequence sound changed: '+stage)
    files_checked=0;groups_checked=0;imports_checked=0;changed_sections=0
    for stage,changes in expected_updates.items():
        old_groups=stock.groups(stage);new_groups=actual.groups(stage)
        need(len(old_groups)==len(new_groups),'Side-mode group count differs: '+stage)
        before=payloads(stock,stage);after=payloads(actual,stage)
        need(set(after)==set(before)|{name for name in changes if name not in before},
             'Side-mode resource inventory differs: '+stage)
        need(changes,'Side-mode stage did not visibly change: '+stage)
        for name,body in after.items():
            need(body==changes.get(name,before.get(name)),
                 'Side-mode resource bytes differ: '+stage+'/'+name)
            files_checked+=1
            imports_checked+=name not in before
        for old_group,new_group in zip(old_groups,new_groups):
            need(old_group['folder']==new_group['folder'],'Side-mode group folder differs: '+stage)
            folder=old_group['folder'];groups_checked+=1
            if folder in ('cache','nocache','resident','sound'):continue
            need(stock.decode(old_group)==actual.decode(new_group),
                 'Unrelated side-mode resource group changed: '+stage+'/'+folder)
        native=sound_packs(stock,stage);added=expected_sound.get(stage,[])
        need(sound_packs(actual,stage)==native+added,'Side-mode sound order or bytes differ: '+stage)
        changed_sections+=1
    if expected_report['boss_sequence']:
        for row in expected_report['boss_sequence']['encounters']:
            row['sound_pack_import']['readback_verified']=True
            need(row['stage'] in expected_updates and row['sites'] and row['assets']['files'],
                 'Incomplete Boss Sequence spawn/resource report')
            for site in row['sites']:
                need(site['source_completion_bridge'] and site['phases'],
                     'Boss Sequence completion chain missing: '+row['stage'])
    if expected_report['extra_missions'] and expected_report['extra_missions']['boss_battle']:
        row=expected_report['extra_missions']['boss_battle']
        row['sound_pack_import']['readback_verified']=True
        need(row['stage']==EXTRA_BOSS_STAGE and row['sites'] and row['assets']['files'],
             'Extra Mission boss spawn/resource report missing')
        for site in row['sites']:
            need(site['source_completion_bridge'] and site['phases'],
                 'Extra Mission boss completion chain missing')
    expected_report=json.loads(json.dumps(expected_report))
    need(expected_report==m.get('side_modes')==read(p/'side-modes.json'),
         'Side-mode mapping differs from seed and original inputs')
    for label,rows in expected_aliases.items():
        saved=m.get('atlas_aliases',{}).get(label,{})
        need(all(saved.get(key)==value for key,value in rows.items()),
             'Side-mode texture alias manifest differs')
        aliases=dict(line.rstrip('\n').split('\t',1) for line in (p/(label+'-aliases.tsv')).read_text().splitlines() if '\t' in line)
        need(all(aliases.get(key)==value for key,value in rows.items()),
             'Side-mode texture alias input differs')
    return dict(format=1,passed=True,seed=seed,archive_sha256=sha(actual.path),
                stages_checked=changed_sections,resources_checked=files_checked,
                imported_resources_checked=imports_checked,groups_checked=groups_checked,
                boss_sequence_encounters=8 if applied['randomise_boss_sequence'] else 0,
                survival_stages=6 if applied['randomise_survival'] else 0,
                extra_missions_stages=len(EXTRA_STAGES) if applied['randomise_extra_missions'] else 0,
                extra_missions_boss_battles=1 if applied['randomise_extra_missions'] and applied['boss_mode']=='shuffle_test' else 0,
                atlas_aliases_checked=sum(len(x) for x in expected_aliases.values()),
                donor_sound_packs_checked=sum(len(x) for x in expected_sound.values()),
                protected_inhert_phases=2 if applied['randomise_boss_sequence'] else 0,
                gameplay_verified=False,
                limitation='Static byte, resource and completion-chain readback does not prove combat, mission objectives or transitions.')
