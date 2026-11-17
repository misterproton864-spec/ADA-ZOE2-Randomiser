import portable_paths as _portable
"""Independent native-profile readback: no imported resources or boss rewrites."""
import json
import hashlib
import struct
from collections import defaultdict
from pathlib import Path

from archive_tools import Archive,L,VAN,sha
from mixed_boss_catalog import payloads
from native_seed_rules import REGULAR_STAGES,REGULAR_TYPES,HELPERS
from original_inputs import resolve_stage,STAGE_SHA
from actor_reference_adapter import selector_arguments
from scx_bytecode import native_calls,instructions,declarations
from scx_call_arguments import UnresolvedArguments
from scx_manager_chain_adapter import MANAGER_TYPES
from install_state import read
from opening_enemies import STAGES as OPENING_STAGES,target as opening_target,asset_set


def require(condition, message):
    if not condition:raise ValueError(message)


def enemy_offsets(data):
    require(len(data)>=32,'Truncated native ENE')
    count=struct.unpack_from('<H',data,2)[0];base=struct.unpack_from('<I',data,4)[0]
    require(base>=32 and base+count*112<=len(data),'Invalid native ENE bounds')
    return {base+r*112+48+s*8 for r in range(count) for s in range(4)
            if data[base+r*112+48+s*8+1] and data[base+r*112+48+s*8] in REGULAR_TYPES}


def apply_checked_changes(stage,name,original,changes,selector_offsets,rewards,levels,native_pool,manager_sites=None,ordinal_offsets=None,swarm_offsets=None):
    """Reconstruct allowed literals only; reject forged logs that edit callbacks."""
    result=bytearray(original);used=set()
    ene=enemy_offsets(original) if name.endswith('.ene') and changes else set()
    for row in changes:
        offset=row['offset'];before=bytes.fromhex(row['before']);after=bytes.fromhex(row['after']);kind=row['kind']
        require(type(offset) is int and 0<=offset<=len(original)-len(before),'Change outside native file')
        require(len(before)==len(after)>0 and original[offset:offset+len(before)]==before,'Change does not match native source')
        occupied=set(range(offset,offset+len(before)))
        require(not used&occupied,'Overlapping native changes');used|=occupied
        if kind=='enemy_type':
            require(stage in REGULAR_STAGES and offset in ene and len(before)==1 and after[0] in native_pool,'Unqualified enemy type change')
        elif kind=='mosquito_type':
            require(stage in REGULAR_STAGES and offset in ene and swarm_offsets is not None and offset in swarm_offsets
                    and len(before)==1 and after==b'\x0a','Unqualified finite swarm literal')
        elif kind=='enemy_level':
            require(stage in REGULAR_STAGES and offset-2 in ene and len(before)==1 and after[0]<=7 and levels,'Unqualified enemy level change')
        elif kind=='enemy_selector':
            require(stage in REGULAR_STAGES and name.endswith('.scx') and offset in selector_offsets and len(before)==4,'Unqualified actor selector change')
            require(struct.unpack('<I',after)[0] in (1,2,3,4,5,6,31,32,40,41,42,43),'Invalid native actor selector')
        elif kind=='enemy_selector_ordinal':
            require(stage in REGULAR_STAGES and name.endswith('.scx') and ordinal_offsets is not None
                    and offset in ordinal_offsets and len(before)==4 and struct.unpack('<I',after)[0]<=65535,
                    'Unqualified actor ordinal change')
        elif kind=='opening_manager':
            require(stage in OPENING_STAGES and name.endswith('.scx') and manager_sites is not None
                    and offset in manager_sites and len(before)==4 and after==struct.pack('<I',manager_sites[offset]),
                    'Unqualified opening manager change')
        elif kind=='subweapon':
            require((stage,name,offset,struct.unpack('<I',before)[0]) in rewards and len(before)==4,'Unqualified subweapon literal')
            require(struct.unpack('<I',after)[0] in (1,2,3,4,6,7,8,9,10,11,12),'Vector Cannon/unknown reward change')
        else:raise ValueError('Unknown native change kind')
        result[offset:offset+len(before)]=after
    return bytes(result)


def verify(package):
    p=Path(package);m=read(p/'manifest.json');settings=read(p/'randomisation-settings.json')
    profile=settings.get('boss_mode');test=profile=='shuffle_test'
    require(profile in ('native','shuffle_test') and m['settings'].get('boss_mode')==profile,'Profile mode differs')
    from audio_options import helpers
    from settings_contract import effective
    contract=effective(settings)
    require(m.get('effective_settings')==contract,'Effective settings differ from requested settings')
    require(read(p/'effective-settings.json')==contract,'Effective settings snapshot differs')
    require(all(m['settings'].get(k)==v for k,v in contract['applied'].items()),'Applied settings differ from manifest')
    expected_helpers=helpers(m['settings']);boss_rows={}
    from mosquito_rules import helpers as swarm_helpers
    expected_helpers.update(swarm_helpers(m))
    from health_runtime_support import HELPER as HEALTH_HELPER,targets as health_targets
    health=m.get('health_multiplier_runtime')
    require(isinstance(health,dict) and health['enemy_multiplier']==settings['enemy_health_multiplier']
            and health['boss_multiplier']==settings['boss_health_multiplier'],
            'Health multiplier report differs from requested settings')
    require(health['enabled']==(settings['enemy_health_multiplier']>1 or settings['boss_health_multiplier']>1),
            'Health helper enablement differs')
    if health['enabled']:
        expected_helpers.add(HEALTH_HELPER)
        require(sha(p/health['target_file'])==health['target_sha256'] and
                sha(p/'runtime'/HEALTH_HELPER)==health['helper_sha256'],
                'Health monitor payload differs from seed manifest')
    if test:
        from boss_test_profile import stages,boss_helpers
        rows=read(p/'boss-mapping.json')
        expected_helpers.update(boss_helpers(m['settings'],rows))
        require(rows==m['boss_changes'] and [r['stage'] for r in rows]==list(stages(m['settings'])),'Boss test stage set differs')
        boss_rows={r['stage']:r for r in rows}
    else:
        require(not contract['applied']['include_viola_ai'],'Experimental boss selected in native profile')
        require(read(p/'boss-mapping.json')==[] and m['boss_changes']==[],'Boss replacement present in native profile')
    require({h['file'] for h in m['runtime_helpers']}==expected_helpers and len(m['runtime_helpers'])==len(expected_helpers),'Unexpected runtime gameplay/boss helper')
    if health['enabled']:
        side=read(p/'side-modes.json');side_bosses=[]
        if side['boss_sequence']:side_bosses.extend(side['boss_sequence']['encounters'])
        if side['extra_missions'] and side['extra_missions'].get('boss_battle'):
            side_bosses.append(side['extra_missions']['boss_battle'])
        expected=health_targets(read(p/'boss-mapping.json')+side_bosses)
        require((p/health['target_file']).read_text(encoding='utf-8')==
                ''.join('{}\t{}\n'.format(stage,ident) for stage,ident in expected)
                and health['target_count']==len(expected),
                'Boss HP actor target list differs from generated encounters')
    if test:
        from arena_runtime_support import verify as verify_reach
        verify_reach(p,m)
        from viper_runtime_support import verify as verify_viper
        verify_viper(p,m)
    original=resolve_stage(VAN);a=Archive(p/'STAGE.DAT');stock=Archive(original['path'])
    require(sha(a.path)==m['patched_sha256'],'Archive hash differs')
    require(set(a.stages)==set(stock.stages),'Stage set changed')
    side_stages=set(m.get('side_mode_stages',[]))
    expected_side=set()
    if settings.get('randomise_survival'):
        from survival_rules import STAGES as SURVIVAL_STAGES
        expected_side.update(SURVIVAL_STAGES)
    if settings.get('randomise_boss_sequence'):
        from boss_sequence_rules import STAGES as SEQUENCE_STAGES
        expected_side.update(SEQUENCE_STAGES)
    if settings.get('randomise_extra_missions'):
        from extra_missions_rules import STAGES as EXTRA_STAGES,BOSS_STAGE as EXTRA_BOSS_STAGE
        expected_side.update(EXTRA_STAGES)
        if profile=='shuffle_test':expected_side.add(EXTRA_BOSS_STAGE)
    require(side_stages==expected_side,'Side-mode stage inventory differs from requested settings')
    changes=read(p/'native-changes.json');byfile=defaultdict(list)
    for row in changes:byfile[row['stage'],row['file']].append(row)
    selectors={int(k,16) for k in read(L/'type-selector-command-catalog.json')['commands']}
    from mosquito_rules import schedule as swarm_schedule
    plan=read(L/'Full-Rerandomisation-v2/enemy-shuffle-plan.json')
    enemy_rows=read(p/'enemy-mapping.json')
    swarm=swarm_schedule(m['seed'],stock,plan['stages'],enemy_rows,contract['applied'],selectors)
    require(swarm==m.get('mosquito_replacements'),'Finite swarm selections differ from source eligibility/weighted settings')
    swarm_byfile=defaultdict(set)
    for spec in swarm['selected']:swarm_byfile[spec['stage'],spec['file']].add(spec['offset'])
    actual_swarm={(r['stage'],r['file'],r['offset']) for r in enemy_rows if r['enemy']==10}
    expected_swarm={(r['stage'],r['file'],r['offset']) for r in swarm['selected']}
    require(actual_swarm==expected_swarm,'Finite swarm enemy map differs')
    require({(r['stage'],r['file'],r['offset']) for r in changes if r['kind']=='mosquito_type'}==expected_swarm,'Finite swarm edit log differs')
    swarm_readback=dict(passed=True,selected_slots=0,gameplay_verified=False)
    if swarm['selected']:
        from mosquito_runtime import verify as verify_swarms
        swarm_readback=verify_swarms(p,m)
    template=read(Path(__file__).resolve().parents[2]/'ship-v5/Ship-v5/manifest.json')
    ownership=read(L/'Weapons-Preview-5/manifest.json')
    rewards={(row['stage'],row['file'],e['offset'],e['original']) for row in ownership['files'] for e in row['edits']}
    files_checked=0;scripts_checked=0;groups_checked=0;visited=set();native_pools={};imports=0;opening_imports=0;ship_imports=0
    opening={r['stage']:r for r in m.get('opening_enemy_imports',[])}
    require(set(opening)==OPENING_STAGES,'Opening coverage report missing or duplicated')
    ship=m.get('ship_enemy_imports',[])
    require(len(ship)==1 and ship[0]['stage']=='ba01','Ship coverage missing or duplicated')
    for stage in sorted(stock.stages):
        old_groups=stock.groups(stage);new_groups=a.groups(stage)
        require(len(old_groups)==len(new_groups),'Resource group count differs: '+stage)
        # validate_side_modes independently reconstructs every resource and
        # imported sound pack in these sections. No Story Mode change log may
        # claim them, and all other sections continue through this validator.
        if stage in side_stages:
            require(not any(key[0]==stage for key in byfile),'Story Mode edit log overlaps side mode: '+stage)
            continue
        oldfiles=payloads(stock,stage)
        boss=boss_rows.get(stage)
        declared={r['name']:r['sha256'] for r in boss['assets']['files']} if boss else {}
        opening_command=None
        ship_expected=None
        if stage=='ba01':
            from ship_validation import expected as expected_ship
            ship_expected,ship_declared=expected_ship(stock,m['seed'],settings,ship[0])
            declared={n:hashlib.sha256(b).hexdigest() for n,b in ship_declared.items()}
        if stage in OPENING_STAGES:
            typ=opening_target(m['seed'],stage,settings['enemy_percentages'])
            resources,donor,opening_command=asset_set(stock,typ)
            declared={n:hashlib.sha256(b).hexdigest() for n,b in resources.items() if n not in oldfiles}
            require(opening[stage]['target']==typ and opening[stage]['donor']==donor
                    and opening[stage]['manager_command']==opening_command and opening[stage]['files']==declared,
                    'Opening imports differ from pinned compatible donor')
        if boss or stage in OPENING_STAGES or ship_expected is not None:require(set(payloads(a,stage))==set(oldfiles)|set(declared),'Unexpected imported resources: '+stage)
        native_pool={MANAGER_TYPES[h] for n,b in oldfiles.items() if n.endswith('.scx') for _,h in native_calls(b) if h in MANAGER_TYPES}&REGULAR_TYPES
        native_pools[stage]=native_pool
        if stage in OPENING_STAGES:native_pool=native_pool|{typ};native_pools[stage]=native_pool
        if ship_expected is not None:native_pool=native_pool|{41,42};native_pools[stage]=native_pool
        for og,ng in zip(old_groups,new_groups):
            require(og['folder']==ng['folder'],'Resource group folder differs: '+stage)
            mutable=(boss or stage in OPENING_STAGES or ship_expected is not None) and og['folder'] in ('cache','nocache')
            sound_contract=boss.get('sound_pack_import') if boss and og['folder']=='sound' else None
            appended_sound=sound_contract['source_sha256'] if sound_contract and sound_contract['added'] else []
            old_names={f['name']:f for f in og['files']}
            if appended_sound:
                original_names=[f['name'] for f in og['files']]
                generated_names=[f['name'] for f in ng['files']]
                require(generated_names[:len(original_names)]==original_names and
                        generated_names[len(original_names):]==[f'pk{i:06x}.sdx' for i in range(len(original_names),len(original_names)+len(appended_sound))],
                        'Unexpected boss sound pack order: '+stage)
            elif not mutable:require([f['name'] for f in og['files']]==[f['name'] for f in ng['files']], 'Resource names/order differ: '+stage)
            else:require(set(old_names)<={f['name'] for f in ng['files']},'Native resources removed: '+stage)
            old_data=stock.decode(og);new_data=a.decode(ng);groups_checked+=1
            for nf in ng['files']:
                name=nf['name'];of=old_names.get(name);after=new_data[nf['offset']:nf['offset']+nf['size']]
                if appended_sound and of is None:
                    index=int(name[2:8],16)-len(old_names)
                    require(0<=index<len(appended_sound) and hashlib.sha256(after).hexdigest()==appended_sound[index],
                            'Imported boss sound pack differs: '+stage+'/'+name)
                    imports+=1;files_checked+=1;continue
                if mutable and name in declared:
                    require(hashlib.sha256(after).hexdigest()==declared[name],'Boss asset bytes differ: '+stage+'/'+name)
                    if of is None:
                        imports+=1
                        if stage in OPENING_STAGES:opening_imports+=1
                        if ship_expected is not None:ship_imports+=1
                    files_checked+=1;continue
                require(of is not None,'Undeclared resource import: '+stage+'/'+name)
                before=old_data[of['offset']:of['offset']+of['size']]
                if boss and boss.get('arena_geometry') and stage=='vc01' and name=='2690498c.hzt':
                    from nephtis_arena_geometry import verify as verify_perimeter
                    verify_perimeter(before,after,boss['arena_geometry'])
                    files_checked+=1;continue
                rows=byfile.get((stage,name),[]);selector_offsets=set();ordinal_offsets=set()
                if ship_expected is not None and name in ship_expected:
                    require(after==ship_expected[name],'Unexpected ship resource, counter or script edit: '+name)
                    if rows:visited.add((stage,name))
                    if name.endswith('.scx'):scripts_checked+=1
                    files_checked+=1;continue
                if rows and name.endswith('.scx'):
                    for offset,command in native_calls(before):
                        if command not in selectors:continue
                        try:items=selector_arguments(before,offset,command)
                        except UnresolvedArguments:continue
                        selector_offsets.update(r['value_offset'] for r in items if r['value_offset'] is not None)
                        from regular_selectors import triples
                        try:ordinal_offsets.update(t[2]['offset'] for t in triples(before,offset,command) if t[2]['kind']==0xc0 and t[2]['offset'] is not None)
                        except UnresolvedArguments:pass
                manager_sites={q+1:opening_command for q,h in native_calls(before) if MANAGER_TYPES.get(h)==40} if name.endswith('.scx') and opening_command else {}
                expected=apply_checked_changes(stage,name,before,rows,selector_offsets,rewards,settings['randomise_enemy_levels'],native_pool,manager_sites,ordinal_offsets,swarm_byfile[stage,name])
                boss_script=bool(boss and name==boss['file'])
                if boss_script:
                    allowed=set()
                    from nephtis_arena_limits import verify_prefix
                    allowed.update(verify_prefix(stage,name,before,after,boss.get('arena_limits')))
                    for row in boss.get('source_visual_overrides',[])+boss.get('source_registration_overrides',[]):allowed.update(range(row['offset'],row['offset']+5))
                    for site in boss['sites']:allowed.update(range(site['source_call'],site['source_call']+5))
                    require(len(after)>=len(expected) and all(x==after[i] or i in allowed for i,x in enumerate(expected)), 'Unrelated native boss script prefix changed: '+stage)
                else:require(after==expected,'Unexpected resource or script change: '+stage+'/'+name)
                if rows:visited.add((stage,name))
                if name.endswith('.scx') and not boss_script:
                    expected_calls=[(q,manager_sites.get(q+1,h)) for q,h in native_calls(before)]
                    require(expected_calls==native_calls(after) and declarations(before)==declarations(after)
                            and [(q,op) for q,op,_ in instructions(before)]==[(q,op) for q,op,_ in instructions(after)],'Native script control flow differs: '+stage)
                    scripts_checked+=1
                files_checked+=1
    require(visited==set(byfile),'Change log refers to missing/duplicate resources')
    require(any(r['kind']=='enemy_type' for r in changes),'No regular enemy randomisation was generated')
    for row in read(p/'enemy-mapping.json'):
        key=(row['stage'],row['file'],row['offset'])
        require(row['stage'] in REGULAR_STAGES and (row['enemy'] in native_pools[row['stage']] or row['enemy']==10 and key in expected_swarm),'Enemy map leaves native pools')
    plan=read(L/'Full-Rerandomisation-v2/enemy-shuffle-plan.json')
    rows=read(p/'enemy-mapping.json')
    for spec in plan['stages']:
        if spec['stage']=='ba01' or spec['stage'] in OPENING_STAGES:continue
        selected={r['original_type']:r.get('base_enemy',r['enemy']) for r in rows if r['stage']==spec['stage']}
        if not selected:continue
        from regular_selectors import patch as patch_selectors
        originals=payloads(stock,spec['stage']);actual=payloads(a,spec['stage'])
        for name,before in originals.items():
            if not name.endswith('.scx'):continue
            refs=[dict(offset=q,command=h) for q,h in native_calls(before) if h in selectors]
            expected_script,selector_changes=patch_selectors(before,refs,selected,spec['slots'])
            for change in selector_changes:
                off=change['offset'];require(actual[name][off:off+4]==expected_script[off:off+4],'Selector type/ordinal no longer addresses its authored actor')
    for helper in m['runtime_helpers']:require(sha(p/'runtime'/helper['file'])==helper['sha256'],'Runtime helper changed')
    from verify_voice import verify as verify_voice
    voice=verify_voice(p)
    from credits_validation import verify as verify_credits
    credits=verify_credits(p,m)
    return dict(passed=True,profile=profile,original_archive_sha256=STAGE_SHA,
                archive_sha256=m['patched_sha256'],resources_checked=files_checked,groups_checked=groups_checked,
                native_scripts_checked=scripts_checked,allowed_literal_changes=len(changes),
                imported_resources=imports,opening_imported_resources=opening_imports,ship_imported_resources=ship_imports,opening_stages_checked=len(opening),randomised_bosses=len(boss_rows),native_boss_scripts_preserved=not test,
                protected_boss_scripts_preserved=True,
                native_spider_stream_preserved=True,vector_cannon_protected=True,
                ship_native_secondary_actors_preserved=True,scripted_actor_collisions_checked=True,
                credits_music_readback=credits,finite_swarm_readback=swarm_readback,gameplay_verified=False,**voice)
