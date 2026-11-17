import portable_paths as _portable
"""Build an installable test seed from vanilla, retaining all native boss logic."""
import ast
import copy
import hashlib
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from archive_tools import Archive,L,VAN,V5,W,sha,save,rebuild_section,write_archive
from mixed_boss_catalog import payloads
from actor_reference_adapter import patch_references
from scx_bytecode import native_calls
from scx_call_arguments import UnresolvedArguments
from scx_manager_chain_adapter import MANAGER_TYPES
from native_seed_rules import REGULAR_STAGES,REGULAR_TYPES,HELPERS,PROTECTED,mode
from randomizer_settings import enemy_weights,enemy_level,weighted_enemy,weapon_selection,boss_selection
from experimental_bosses import require_neith_available
from original_inputs import resolve
from build_info import BUILD_ID,VERSION

SOURCE=Path(__file__).resolve().parent
GAME=Path(str(_portable.game()))


def build_audio(seed,directory,out,original_inputs):
    # Reuse exactly the audited audio-generation statements, never the mixed
    # boss/archive branch. Both profiles retain the same audio format checks.
    import seed_builder as sb
    tree=ast.parse(Path(sb.__file__).read_text(encoding='utf-8'))
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='generate')
    chosen=[];active=False
    for node in function.body:
        if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='audio':active=True
        if active and isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='m':break
        if active:chosen.append(node)
    if not chosen or not any(isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) for n in chosen):
        raise ValueError('Shared audio generation boundary changed')
    environment=dict(vars(sb),seed=seed,directory=directory,out=out,original_inputs=original_inputs)
    exec(compile(ast.Module(body=chosen,type_ignores=[]),str(sb.__file__),'exec'),environment)


def record_edit(edits,stage,name,offset,before,after,kind):
    if before!=after:edits.append(dict(stage=stage,file=name,offset=offset,before=before.hex(),after=after.hex(),kind=kind))


def generate(seed,directory,settings=None,include_neith_experimental=False):
    from beta_support import prepare
    prepare()
    seed=str(seed)
    if not seed.strip():raise ValueError('Seed required')
    from settings_contract import normalise,effective
    options=normalise(settings)
    if include_neith_experimental:options['include_neith_experimental']=True
    effective_settings=effective(options)
    if effective_settings['blocked']:raise ValueError('; '.join(effective_settings['blocked']))
    profile_mode=mode(options.get('boss_mode','shuffle_test'));boss_test=profile_mode=='shuffle_test'
    weights=enemy_weights(options.get('enemy_percentages'))
    weapons=weapon_selection(options.get('enabled_subweapons'))
    levels=options.get('randomise_enemy_levels',False)
    if type(levels) is not bool:raise ValueError('Enemy level setting must be boolean')
    applied=effective_settings['applied']
    viola=applied['include_viola_ai']
    selected_bosses=applied['enabled_bosses']
    sources={p.name:sha(p) for p in SOURCE.glob('*.py')}
    original=resolve(GAME,VAN);stock=Archive(original['stage']['path'])
    print('Original inputs verified; preparing native regular pools.',flush=True)
    directory=Path(directory).resolve()
    if not directory.is_relative_to(Path(str(_portable.BUILD_ROOT)).resolve()):raise ValueError('Build output must stay inside the beta data folder')
    directory.mkdir(parents=True,exist_ok=False)
    out=directory/'Ship-v5';out.mkdir();(directory/'reports').mkdir();(out/'runtime').mkdir()
    template=json.loads((V5/'manifest.json').read_text())
    updates={};edits=[];enemylog=[];coverage=[];opening_reports=[];ship_reports=[];opening_aliases={'main':{},'small':{}}
    plan=json.loads((L/'Full-Rerandomisation-v2/enemy-shuffle-plan.json').read_text())
    selectors={int(k,16) for k in json.loads((L/'type-selector-command-catalog.json').read_text())['commands']}
    for row in plan['stages']:
        stage=row['stage']
        if stage=='ba01':
            from ship_enemies import prepare as prepare_ship
            files,changes,logs,report,pairs=prepare_ship(seed,stock,row,weights,levels,selectors)
            updates[stage]=files;edits.extend(changes);enemylog.extend(logs);ship_reports.append(report)
            for label in opening_aliases:opening_aliases[label].update(pairs[label])
            coverage.append(dict(stage=stage,randomised=bool(changes),mapping=report['group_mapping'],slots=len(logs),ship_imports=True,protected_regular_types=[32],reason='Native Mummyhead dependency and secondary actors retained; standalone Raptor replacements.'))
            continue
        from opening_enemies import STAGES as OPENING_STAGES,prepare as prepare_opening
        if stage in OPENING_STAGES:
            files,changes,logs,report,pairs=prepare_opening(seed,stock,stage,row,weights,levels,selectors)
            updates[stage]=files;edits.extend(changes);enemylog.extend(logs);opening_reports.append(report)
            for label in opening_aliases:opening_aliases[label].update(pairs[label])
            coverage.append(dict(stage=stage,randomised=bool(changes),mapping={40:report['target']},slots=len(logs),opening_imports=True))
            continue
        if stage not in REGULAR_STAGES:
            coverage.append(dict(stage=stage,randomised=False,reason='Native boss/objective, regression boundary or unqualified pool'));continue
        files=payloads(stock,stage);changed=files.copy();stage_edits=[];stage_log=[]
        pools={MANAGER_TYPES[h] for name,data in files.items() if name.endswith('.scx') for p,h in native_calls(data) if h in MANAGER_TYPES}
        present={r['original_type'] for r in row['slots']}&REGULAR_TYPES
        pool=sorted(pools&present&REGULAR_TYPES)
        if not present<=pools or len(pool)<2:
            coverage.append(dict(stage=stage,randomised=False,reason='Only one native pool or original manager not resolved'));continue
        mapping={typ:weighted_enemy(seed,stage,'native/'+str(typ),pool,weights) for typ in sorted(present)}
        try:
            for name,data in files.items():
                if not name.endswith('.scx'):continue
                refs=[dict(offset=p,command=h) for p,h in native_calls(data) if h in selectors]
                from regular_selectors import patch as patch_regular_selectors
                patched,changes=patch_regular_selectors(data,refs,mapping,row['slots'])
                changed[name]=patched
                for item in changes:
                    p=item['offset'];record_edit(stage_edits,stage,name,p,data[p:p+4],patched[p:p+4],item['kind'])
        except UnresolvedArguments:
            coverage.append(dict(stage=stage,randomised=False,reason='Computed actor selector retained native'));continue
        for slot in row['slots']:
            typ=slot['original_type']
            if typ not in mapping:continue  # Native mosquito/swarm is never replaced.
            name=slot['file'];p=slot['offset'];data=bytearray(changed[name])
            if data[p:p+3]!=bytes((typ,slot['count'],slot['level'])):raise ValueError('Original enemy record differs: '+stage)
            target=mapping[typ];level=enemy_level(seed,stage,name+'/'+str(p),slot['level'],levels)
            record_edit(stage_edits,stage,name,p,bytes((typ,)),bytes((target,)),'enemy_type')
            record_edit(stage_edits,stage,name,p+2,bytes((slot['level'],)),bytes((level,)),'enemy_level')
            data[p]=target;data[p+2]=level;changed[name]=bytes(data)
            stage_log.append(dict(stage=stage,file=name,record=slot['record'],slot=slot['slot'],offset=p,enemy=target,
                                  original_type=typ,count=slot['count'],original_level=slot['level'],level=level,native_pool=pool))
        if stage_edits:updates[stage]=changed;edits.extend(stage_edits)
        enemylog.extend(stage_log)
        coverage.append(dict(stage=stage,randomised=bool(stage_edits),mapping=mapping,native_pool=pool,slots=len(stage_log)))
    from mosquito_rules import schedule as swarm_schedule,apply_selection as apply_swarms
    swarm=swarm_schedule(seed,stock,plan['stages'],enemylog,applied,selectors)
    for stage in sorted({r['stage'] for r in swarm['selected']}):
        original_files=payloads(stock,stage)
        updates[stage]=apply_swarms(stage,original_files,updates.get(stage,original_files.copy()),
            [r for r in swarm['selected'] if r['stage']==stage],edits,enemylog)
        for c in coverage:
            if c['stage']==stage:c.update(randomised=True,finite_swarm_slots=sum(r['stage']==stage for r in swarm['selected']))
    from reward_rules import weapon_permutation
    mapping={ident:ident for ident in weapon_selection()};mapping.update(weapon_permutation(seed+'/subweapons',weapons))
    weaponlog=[];ownership=json.loads((L/'Weapons-Preview-5/manifest.json').read_text())
    print('Regular pool mappings:',len(enemylog),'slots; preparing rewards.',flush=True)
    for row in ownership['files']:
        stage=row['stage'];name=row['file']
        if stage not in updates:updates[stage]=payloads(stock,stage).copy()
        files=updates[stage]
        data=bytearray(files[name])
        for item in row['edits']:
            p=item['offset'];old=item['original'];new=mapping[old]
            if struct.unpack_from('<I',data,p)[0]!=old:raise ValueError('Original weapon literal differs')
            record_edit(edits,stage,name,p,struct.pack('<I',old),struct.pack('<I',new),'subweapon')
            struct.pack_into('<I',data,p,new)
            weaponlog.append(dict(stage=stage,file=name,offset=p,original=old,reward=new,operation=item['operation']))
        files[name]=bytes(data)
    bosses=[];aliases={'main':{},'small':{}}
    if boss_test:
        from boss_test_profile import build as build_bosses
        bosses,aliases=build_bosses(seed,stock,updates,selected_bosses,viola,applied['include_inhert_experimental'],applied['valley_viper_test'])
    for label in aliases:aliases[label].update(opening_aliases[label])
    side_modes=dict(format=1,seed=seed,boss_sequence=None,survival=None,extra_missions=None,
                    gameplay_verified=False)
    side_stages=set();side_bosses=[];side_import_stages=set()
    if applied['randomise_survival']:
        from survival_rules import build as build_survival
        side_files,side_modes['survival'],side_aliases=build_survival(seed,stock,weights,levels)
        for stage,changed in side_files.items():
            before=payloads(stock,stage)
            if stage in updates:raise ValueError('Survival stage overlaps Story Mode edits: '+stage)
            updates[stage]=dict(before,**changed);side_stages.add(stage)
            if set(changed)-set(before):side_import_stages.add(stage)
        for label in aliases:aliases[label].update(side_aliases[label])
    if applied['randomise_boss_sequence']:
        from boss_sequence_rules import build as build_sequence
        side_files,side_modes['boss_sequence'],side_aliases,side_sounds=build_sequence(seed,stock,applied)
        side_bosses=list(side_modes['boss_sequence']['encounters'])
        for stage,changed in side_files.items():
            before=payloads(stock,stage)
            if stage in updates:raise ValueError('Boss Sequence overlaps Story Mode edits: '+stage)
            updates[stage]=dict(before,**changed);side_stages.add(stage)
            if set(changed)-set(before):side_import_stages.add(stage)
        for label in aliases:aliases[label].update(side_aliases[label])
    if applied['randomise_extra_missions']:
        from extra_missions_rules import build as build_extra,BOSS_STAGE as EXTRA_BOSS_STAGE
        side_files,side_modes['extra_missions']=build_extra(seed,stock,weights)
        side_modes['extra_missions']['boss_battle']=None
        for stage,changed in side_files.items():
            before=payloads(stock,stage)
            if stage in updates:raise ValueError('Extra Mission stage overlaps existing edits: '+stage)
            updates[stage]=dict(before,**changed);side_stages.add(stage)
        if boss_test:
            from boss_sequence_rules import build as build_side_battle,NATIVE as SEQUENCE_NATIVE
            battle_files,battle_report,battle_aliases,_=build_side_battle(
                seed,stock,applied,(EXTRA_BOSS_STAGE,),dict(SEQUENCE_NATIVE,vs_ca02='Ardjet'),False)
            battle=battle_report['encounters'][0]
            side_modes['extra_missions']['boss_battle']=battle;side_bosses.append(battle)
            before=payloads(stock,EXTRA_BOSS_STAGE)
            if EXTRA_BOSS_STAGE in updates:raise ValueError('Extra Mission boss overlaps existing edits')
            updates[EXTRA_BOSS_STAGE]=dict(before,**battle_files[EXTRA_BOSS_STAGE])
            side_stages.add(EXTRA_BOSS_STAGE);side_import_stages.add(EXTRA_BOSS_STAGE)
            for label in aliases:aliases[label].update(battle_aliases[label])
    boss_stages={r['stage'] for r in bosses+side_bosses}
    def stage_sound(archive,stage):
        result=[]
        for group in archive.groups(stage):
            if group['folder']!='sound':continue
            bits=archive.decode(group)
            result.extend(bits[row['offset']:row['offset']+row['size']] for row in group['files'])
        return result
    sound_imports={}
    for row in bosses+side_bosses:
        stage=row['stage'];donors=row.get('sound_donors',[row['assets']['donor']])
        native=stage_sound(stock,stage)
        if not native:raise ValueError('Boss arena has no native sound pack: '+stage)
        if len(donors)==1 and donors[0]==stage:
            row['sound_pack_import']=dict(donor=stage,added=0,readback_verified=False)
            continue
        packs=[];seen=set()
        for donor in donors:
            if donor==stage or donor in seen:continue
            seen.add(donor)
            donor_packs=stage_sound(stock,donor)
            if not donor_packs or any(len(p)%2048 or struct.unpack_from('<I',p)[0]!=1 for p in donor_packs):
                raise ValueError('Invalid donor sound pack: '+donor)
            packs.extend(donor_packs)
        sound_imports[stage]=packs
        metadata=dict(added=len(packs),source_sha256=[hashlib.sha256(p).hexdigest() for p in packs],readback_verified=False)
        metadata['donor' if len(donors)==1 else 'donors']=donors[0] if len(donors)==1 else donors
        row['sound_pack_import']=metadata
    blocks={}
    print('Packing updated stage sections:',len(updates),flush=True)
    for stage,files in updates.items():
        before=payloads(stock,stage);changes={n:b for n,b in files.items() if n in before and before[n]!=b}
        imports=[(n,b) for n,b in files.items() if n not in before]
        if stage in boss_stages or stage in OPENING_STAGES or stage=='ba01' or stage in side_import_stages:
            blocks[stage]=rebuild_section(stock,stage,changes,imports,sound_imports=sound_imports.get(stage,()));continue
        if changes:
            # No imports: retain the original native resource table order too.
            import model_texture_load_order as ordering
            previous=ordering.order_model_textures
            ordering.order_model_textures=lambda entries,data:(entries,data,[])
            try:blocks[stage]=rebuild_section(stock,stage,changes,order_motion=False)
            finally:ordering.order_model_textures=previous
    write_archive(stock,blocks,out/'STAGE.DAT');arc=Archive(out/'STAGE.DAT')
    for row in bosses+side_bosses:
        stage=row['stage'];before=stage_sound(stock,stage);added=sound_imports.get(stage,())
        if stage_sound(arc,stage)!=before+list(added):raise ValueError('Boss sound pack readback differs: '+stage)
        row['sound_pack_import']['readback_verified']=True
    m=dict(format=3,baseline='Hash-pinned original Steam archive',source_sha256=original['stage']['sha256'],
           vanilla_sha256=original['stage']['sha256'],original_music_banks=copy.deepcopy(template['original_music_banks']),
           boss_seed=seed+'/bosses',enemy_seed=seed+'/enemies',subweapon_seed=seed+'/subweapons',
           runtime_launcher='runtime/Attach-Full-Preview.ps1',runtime_hooks_attached=False,
           weapon_manifest=str(out/'subweapon-mapping.json'),full_game_playable=False,
           baseline_game_executable_sha256=template['baseline_game_executable_sha256'])
    m.update(seed=seed,candidate_seed=seed,patched_sha256=sha(out/'STAGE.DAT'),settings=dict(template['settings'],**options),
             boss_changes=bosses,enemy_changes=[dict(stage=r['stage']) for r in coverage if r['randomised']],
             native_enemy_coverage=coverage,opening_enemy_imports=opening_reports,ship_enemy_imports=ship_reports,atlas_aliases=aliases,atlases=[],runtime_helpers=[],
             release_name='v'+VERSION+(' experimental boss-shuffle diagnostic' if boss_test else ' original-boss Normal test seed'),gameplay_verified=False,full_requirements_complete=False,
             full_campaign_gameplay_verified=False,installed=False,preview_ready_for_install=False)
    m['side_modes']=side_modes
    m['side_mode_stages']=sorted(side_stages)
    m['settings'].update(applied)
    m['settings']['mosquito_excluded']=not bool(swarm['selected'])
    m['mosquito_replacements']=swarm
    m['enemy_support_status']=dict(spider_regular_replacements=False,mosquito_regular_replacements=bool(swarm['selected']),
        mosquito_experimental=True,mosquito_gameplay_verified=False,
        native_spider_objectives_preserved=True,native_swarm_scripts_preserved=True,
        ship_pool_branches_repaired=True,ship_softlock_repair_gameplay_verified=False,
        enemy_count_increase_supported=False)
    m['effective_settings']=effective_settings
    m['seed_scope']=dict(rerolled=['eligible native regular-enemy pools','selected subweapons/Metatron']+(['compatible music'] if applied['randomise_music'] else [])+(['compatible ADA streams'] if applied['randomise_ada'] else []),
                         protected=PROTECTED,full_campaign_reroll_complete=False)
    m['fallback_sections']={r['stage']:r['reason'] for r in coverage if not r['randomised'] and 'reason' in r}
    m['boss_mapping_policy']=('Diagnostic assignments exhaust compatible identities; Apply enforces '+applied['repeat_rule']+'. Only Zakat remains protected.') if boss_test else 'Original bosses retained.'
    m['seed_scope']['rerolled']+=['fourteen experimental boss arena assignments'] if boss_test else []
    if side_modes['boss_sequence']:m['seed_scope']['rerolled'].append('eight Boss Sequence opponent handoffs')
    if side_modes['survival']:m['seed_scope']['rerolled'].append('six Survival enemy stages')
    if side_modes['extra_missions']:
        m['seed_scope']['rerolled'].append('six currently eligible Extra Mission enemy sections')
        if side_modes['extra_missions']['boss_battle']:
            m['seed_scope']['rerolled'].append('separate Extra Mission Ardjet boss battle')
    if applied['valley_viper_test']:m['seed_scope']['rerolled']+=['controlled Valley-only Vic Viper close-combat test']
    m['seed_scope']['protected']='Zakat; non-boss Vector Cannon and native Spider/Mosquito objectives. Cinematic-only actors retain their scene scripts.' if boss_test else PROTECTED
    for name,value in [('manifest.json',m),('randomisation-settings.json',options),('original-inputs.json',original),
                       ('native-changes.json',edits),('enemy-mapping.json',enemylog),('boss-mapping.json',bosses),
                       ('side-modes.json',side_modes),
                       ('subweapon-mapping.json',dict(mapping=mapping,files=weaponlog,enabled_pool=weapons,vector_cannon_protected=True))]:save(out/name,value)
    print('Generating compatible music, ADA and runtime rewards.',flush=True)
    build_audio(seed,directory,out,original)
    from audio_options import apply as apply_audio_options,helpers as selected_helpers
    apply_audio_options(directory,applied)
    m=json.loads((out/'manifest.json').read_text())
    if applied['randomise_music']:
        m['beyond_the_bounds']=json.loads((out/'audio/beyond-the-bounds.json').read_text())
        m['beyond_the_bounds'].update(included=True,in_music_pool=True)
    m['music_track_shuffle']['beyond_the_bounds_asset_identified']=True
    for name in ('FakeAnubisDamageAdapter.cs','verify_load_fix_native.py'):
        shutil.copy2(V5/'runtime'/name,out/'runtime'/name)
    sys.path.insert(0,str(W/'progression-v4/source'));import build_candidate as bc
    bc.OUT=out;bc.ROOT=directory;bc.bank_helpers(stock,arc,m)
    from selected_rewards import configure
    configure(out,weapons)
    helpers=selected_helpers(applied)
    from health_runtime_support import install as install_health,HELPER as HEALTH_HELPER
    m['health_multiplier_runtime']=install_health(out,applied,bosses,side_bosses,m['baseline_game_executable_sha256'])
    if m['health_multiplier_runtime']['enabled']:
        helpers.add(HEALTH_HELPER)
    if swarm['selected']:
        from mosquito_runtime import build as build_swarms
        m['finite_mosquito_runtime']=build_swarms(out,swarm['selected'])
        from mosquito_rules import helpers as swarm_helpers
        helpers.update(swarm_helpers(m))
    if boss_test:
        from boss_test_profile import BOSS_HELPERS,boss_helpers
        helpers.update(boss_helpers(applied,bosses))
        for name in BOSS_HELPERS:
            from arena_runtime_support import HELPERS as reach_helpers
            from viper_runtime_support import HELPERS as viper_helpers
            if name!='NephtisDialogueAdapter.exe' and name not in reach_helpers|viper_helpers:shutil.copy2(V5/'runtime'/name,out/'runtime'/name)
        from arena_runtime_support import install as install_reach
        m['proximity_fixes']=install_reach(out)
        from viper_runtime_support import install as install_viper
        m['viper_combat_fixes']=install_viper(out)
    m['runtime_helpers']=[dict(file=n,sha256=sha(out/'runtime'/n)) for n in sorted(helpers)]
    from metatron_manifest import manifest as metatron
    save(out/'metatron-counter-manifest.json',metatron(seed,chance=applied['metatron_subweapon_chance_percent'],pool=weapons))
    save(out/'effective-settings.json',effective_settings)
    for name in ('Attach at main menu.cmd','Install-preview.ps1','Install preview.cmd','Restore previous build.cmd','Capture stuck encounter.cmd','Record progression.cmd'):
        shutil.copy2(V5/name,out/name)
    shutil.copy2(V5/'runtime/Attach-Full-Preview.ps1',out/'runtime/Attach-Full-Preview.ps1')
    from attachment_support import prepare
    prepare(out)
    from capture_diagnostics import build as capture
    capture(out,seed,m['patched_sha256'])
    from installer_support import allow_new_files
    script=out/'Install-preview.ps1';script.write_text(allow_new_files(script.read_text()))
    from boss_install_guard import ensure_gate
    ensure_gate(out)
    files=[dict(relative_path='ZOE2/STAGE.DAT',package_path='STAGE.DAT',expected_before_sha256=sha(GAME/'ZOE2/STAGE.DAT'),patched_sha256=m['patched_sha256'])]
    if boss_test or any(r['files'] for r in opening_reports+ship_reports):
        script=directory/'Build-Atlases.ps1'
        for label in ('main','small'):(out/(label+'-aliases.tsv')).write_text(''.join(k+'\t'+v+'\n' for k,v in sorted(aliases[label].items())))
        from boss_install_guard import ps_quote
        atlas_text="$ErrorActionPreference='Stop'\nAdd-Type -Path "+ps_quote(L/'CampaignAtlasAlias.cs')+'\n'
        for label,name in [('small','atlas_pc_jp_Zlib_ps2.pac'),('main','atlas_pc_Zlib.pac')]:
            atlas_text+='[CampaignAtlasAlias]::BuildWithReplacements('+','.join(ps_quote(value) for value in [original['atlases'][name]['path'],out/name,L/'Loader-Test'/(label+'-index.txt'),out/(label+'-aliases.tsv')])+')\n'
        script.write_text(atlas_text)
        subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script)],check=True)
        for name in original['atlases']:
            digest=sha(out/name);files.append(dict(relative_path='atlas/'+name,package_path=name,expected_before_sha256=sha(GAME/'atlas'/name),patched_sha256=digest));m['atlases'].append(dict(file=name,sha256=digest))
    for row in json.loads((directory/'reports/audio-install-files.json').read_text()):
        row=dict(row);target=GAME/row['relative_path'];row['expected_before_sha256']=sha(target) if target.is_file() else None;files.append(row)
    changed={r['relative_path'] for r in files}
    dependencies=[] if m['atlases'] else [dict(relative_path='atlas/'+n,sha256=r['sha256']) for n,r in original['atlases'].items()]
    dependencies += [dict(relative_path='sound/Windows/'+r['file'],sha256=r['sha256']) for r in m['original_music_banks'] if 'sound/Windows/'+r['file'] not in changed]
    save(out/'installation-plan.json',dict(format=1,baseline='Current hash-pinned installation; native original build input',files=files,dependencies=dependencies))
    save(out/'manifest.json',m)
    from validate_native_seed import verify
    print('Reading back resources and protected progression.',flush=True)
    proof=verify(out);m['native_preservation']=proof
    if side_stages:
        from validate_side_modes import verify as verify_side_modes
        mode_proof=verify_side_modes(out);m['side_mode_validation']=mode_proof
        save(out/'verification-side-modes.json',mode_proof)
    if boss_test:
        from validate_boss_spawns import validate as validate_bosses
        boss_proof=validate_bosses(out);m['boss_test_validation']=boss_proof;save(out/'verification-boss-test.json',boss_proof)
    from build_policy import assess
    policy=assess(m,bosses);m['release_policy']=policy;m['preview_ready_for_install']=policy['passed'];save(out/'manifest.json',m)
    (out/'verification').mkdir(exist_ok=True)
    save(out/'verification/native-preservation.json',proof);save(out/'verification/boss-spawn-validation.json',boss_proof if boss_test else proof)
    save(out/'release-policy.json',policy)
    categories=dict(enemies=enemylog,bosses=bosses,subweapons=mapping,music=m['music_track_shuffle']['track_mapping'],ada=m['ada_overlay']['mapping'])
    categories['side_modes']=side_modes
    categories['health_multiplier_runtime']=m['health_multiplier_runtime']
    result=dict(seed=seed,build_id=BUILD_ID,archive_sha256=m['patched_sha256'],package=str(out),installable=policy['passed'],
                blocked_reasons=policy['blockers'],payloads_complete=True,gameplay_verified=False,profile=profile_mode,
                category_manifest_hashes={k:hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest() for k,v in categories.items()})
    save(out/'build-result.json',result)
    if {p.name:sha(p) for p in SOURCE.glob('*.py')}!=sources:raise ValueError('Source changed while generating; rebuild required')
    sealed=['manifest.json','build-result.json','installation-plan.json','Install-preview.ps1','Validate boss spawns.ps1','boss-spawn-check.json',
            'randomisation-settings.json','effective-settings.json','metatron-counter-manifest.json','original-inputs.json','native-changes.json','enemy-mapping.json','boss-mapping.json','side-modes.json','subweapon-mapping.json','release-policy.json',
            'runtime/Attach-Full-Preview.ps1','Attach at main menu.cmd']
    if boss_test:sealed+=['proximity-fix-contract.json','viper-combat-contract.json']
    if side_stages:sealed+=['verification-side-modes.json']
    if 'ValleyViperAdapter.exe' in helpers:sealed+=['valley-viper-contract.json','valley-viper-tests.json','runtime/valley-viper.c','runtime/valley-viper.obj','runtime/ValleyViperAdapter.cs']
    if swarm['selected']:sealed+=['finite-mosquito-contract.json','finite-mosquito-tests.json','runtime/finite-mosquito.c','runtime/finite-mosquito.obj','runtime/FiniteMosquitoAdapter.cs']
    if m['health_multiplier_runtime']['enabled']:sealed+=['health-boss-targets.tsv','runtime/HealthMultiplierAdapter.cs']
    sealed += [r['package_path'] for r in files]+['runtime/'+n for n in sorted(helpers)]
    save(out/'build-provenance.json',dict(format=2,build_id=BUILD_ID,seed=seed,source_snapshot_stable=True,source_hashes=sources,
                                       package_hashes={n:sha(out/n) for n in sorted(set(sealed))}))
    save(out/'checksums.json',{p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file() and p.name!='checksums.json'})
    print('BUILD COMPLETE',json.dumps(result),flush=True)
    return result
