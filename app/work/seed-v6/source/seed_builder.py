import portable_paths as _portable
"""Private local seed builder. Offline validation is not gameplay validation."""
import argparse,copy,json,struct,hashlib,secrets,shutil,subprocess,sys
from pathlib import Path
from archive_tools import *
from mixed_boss_catalog import payloads,catalog,assets
from actor_reference_adapter import patch_references
from scx_bytecode import native_calls
from boss_handoff import append_mixed_handoff
from boss_variant_pool import variant_profiles,choose_profile
from nephtis_encounter_support import append_nephtis_support,SNOW_POLES,SNOW_CUBE
from reward_rules import weapon_permutation
from stage_compatibility import regular_pool,suppress_incompatible_pools
from randomizer_settings import enemy_weights,boss_selection,weapon_selection,weighted_enemy,enemy_level,BOSSES,WEAPONS
from experimental_bosses import neith_selection,require_neith_available,ExperimentalBossUnavailable
ROOT=Path(__file__).resolve().parents[1]
GAME=Path(str(_portable.game()))
CSC=_portable.compiler()
ORDER=['ca02','ba02','ba03','wn01','vc01','cy02','ef01','fr02','cs01','fa01','fr04g','am02']
def rank(seed,domain,key):return hashlib.sha256((seed+'\0'+domain+'\0'+str(key)).encode()).digest()
def boss_schedule(seed,enabled_bosses=None):
 selected={BOSSES[n] for n in boss_selection(enabled_bosses,include_viola_ai='Viola AI (full rescue fight)' in (enabled_bosses or []))}
 used=set();rows=[];cycle=0
 for stage in ORDER:
  allowed={'Ardjet','Nephtis','Anubis','Vic Viper'}
  if stage=='fr02':allowed.add('Inhert')
  if stage=='vc01':allowed.remove('Vic Viper') # unresolved 0-HP death stall
  allowed &= selected
  if not allowed:raise ValueError('No enabled compatible boss for story stage '+stage+'. Enable another boss; no unsafe fallback was applied.')
  remaining=allowed-used;reset=False
  if not remaining:used-=allowed;remaining=allowed;cycle+=1;reset=True
  identity=min(remaining,key=lambda k:rank(seed,'bosses',stage+'/'+k));used.add(identity)
  rows.append(dict(stage=stage,identity=identity,compatible=sorted(allowed),cycle=cycle,compatible_bag_reset=reset))
 return rows
def compile_cs(source,target):
 subprocess.run([CSC,'/nologo','/platform:x64','/optimize+','/out:'+str(target),str(source)],check=True)
def generate(seed,directory,skip_atlases=False,include_viola_ai=False,settings=None,include_neith_experimental=False):
 settings=dict(settings or {})
 if include_viola_ai:settings['include_viola_ai']=True
 from settings_contract import normalise
 settings=normalise(settings)
 from native_seed_rules import mode
 if mode((settings or {}).get('boss_mode','shuffle_test')) in ('native','shuffle_test'):
  from native_seed_builder import generate as native_generate
  return native_generate(seed,directory,settings,include_neith_experimental)
 seed=str(seed)
 if not seed.strip():raise ValueError('Seed must contain text or an integer')
 options=dict(settings or {});include_viola_ai=options.get('include_viola_ai',include_viola_ai)
 include_neith_experimental=neith_selection(options.get('include_neith_experimental',include_neith_experimental))
 require_neith_available(include_neith_experimental)
 source_hashes={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}
 weights=enemy_weights(options.get('enemy_percentages'));selected_bosses=boss_selection(options.get('enabled_bosses'),include_viola_ai)
 selected_weapons=weapon_selection(options.get('enabled_subweapons'))
 levels=options.get('randomise_enemy_levels',False)
 if type(levels) is not bool:raise ValueError('Enemy level toggle must be true or false')
 options=dict(boss_mode='shuffle',enemy_percentages=weights,enabled_bosses=selected_bosses,enabled_subweapons=selected_weapons,include_viola_ai=include_viola_ai,randomise_enemy_levels=levels,include_neith_experimental=include_neith_experimental)
 allocations=boss_schedule(seed,selected_bosses)
 from original_inputs import resolve as resolve_original_inputs
 original_inputs=resolve_original_inputs(GAME,VAN)
 import mixed_boss_catalog as native_catalog
 native_catalog.ORIGINAL=Path(original_inputs['stage']['path'])
 directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=False)
 out=directory/'Ship-v5';out.mkdir();(directory/'reports').mkdir()
 base=Archive(V5/'STAGE.DAT');van=Archive(VAN);compatibility_edits=[]
 assert sha(base.path)=='98a513765a6903675ba953292c5b25204f511d20ee39a7a77ad9476847cf3567'
 m=json.loads((V5/'manifest.json').read_text());blocks={};updates={};enemylog=[];weaponlog=[];bosslog=[]
 save(out/'randomisation-settings.json',options)
 save(out/'original-inputs.json',original_inputs)
 m['settings']['enemy_percentages']=weights;m['settings']['enabled_bosses']=selected_bosses;m['settings']['enabled_subweapons']=selected_weapons
 m['settings']['randomise_enemy_levels']=levels
 m['settings']['include_neith_experimental']=include_neith_experimental
 aliases=copy.deepcopy(m['atlas_aliases'])
 # Start every build from the same pinned V5 input, never the installed seed.
 def get(stage):return updates.setdefault(stage,payloads(base,stage).copy())
 selectors={int(h,16) for h in json.loads((L/'type-selector-command-catalog.json').read_text())['commands']}
 binding=json.loads((L/'battleship-binding.json').read_text())
 for row in m['enemy_changes']:
  stage=row['stage'];files=get(stage)
  if stage=='ba01':
   groups=sorted({r['group'] for r in row['slot_edits']});mapping={g:weighted_enemy(seed,stage,'ship/'+str(g),[41,42],weights) for g in groups}
   for r in row['slot_edits']:
    b=bytearray(files[r['file']]);b[r['offset']]=mapping[r['group']];b[r['offset']+2]=enemy_level(seed,stage,str(r['file'])+'/'+str(r['record'])+'/'+str(r['slot']),r['level'],levels);files[r['file']]=bytes(b)
    enemylog.append(dict(stage=stage,file=r['file'],record=r['record'],slot=r['slot'],group=r['group'],enemy=mapping[r['group']],count=r['count'],original_level=r['level'],level=b[r['offset']+2]))
   for r in row['selector_edits']:
    # Match selector to group from the original V5 ship manifest.
    b=bytearray(files['ef1d2ddf.scx']);new={41:3,42:5}[mapping[r['group']]] if r['original']==1 else mapping[r['group']]
    struct.pack_into('<I',b,r['offset'],new);files['ef1d2ddf.scx']=bytes(b)
   continue
  pool=regular_pool(stage,row['pools'])
  if not pool:
   enemylog.append(dict(stage=stage,protected=True,reason='Only native mosquito controller available; no compatible non-mosquito pool'))
   continue
  origins=sorted({r['original_type'] for r in row['slot_edits']})
  mapping={t:weighted_enemy(seed,stage,'source/'+str(t),pool,weights) for t in origins}
  for r in row['slot_edits']:
   b=bytearray(files[r['file']]);p=r['offset'];assert b[p+1:p+3]==bytes([r['count'],r['level']])
   b[p]=mapping[r['original_type']];b[p+2]=enemy_level(seed,stage,str(r['file'])+'/'+str(r['record'])+'/'+str(r['slot']),r['level'],levels);files[r['file']]=bytes(b)
   enemylog.append(dict(stage=stage,file=r['file'],record=r['record'],slot=r['slot'],group=r['script_group_id'],enemy=b[p],count=r['count'],original_level=r['level'],level=b[p+2]))
  for name,original in payloads(van,stage).items():
   if not name.endswith('.scx'):continue
   refs=[dict(offset=p,command=h) for p,h in native_calls(original) if h in selectors]
   _,edits=patch_references(original,refs,mapping,binding if stage=='af01g' and name==binding['file'] else None)
   b=bytearray(files[name])
   for e in row.get('selector_edits',[]):
    if e['file']==name: b[e['offset']:e['offset']+4]=original[e['offset']:e['offset']+4]
   for e in edits:struct.pack_into('<I',b,e['offset'],e['replacement'])
   files[name]=bytes(b)
  compatibility_edits.extend(suppress_incompatible_pools(stage,files,row))
 print('Enemy assignments regenerated:',len(enemylog),flush=True)
 from mission_enemies import restore as restore_mission_enemies,STAGES as MISSION_STAGES
 mission_log,mission_reports=restore_mission_enemies(seed,van,updates,aliases,weights,levels);enemylog.extend(mission_log)
 m['scripted_mission_randomisation']=mission_reports
 for stage in MISSION_STAGES:m['fallback_sections'].pop(stage,None)
 # Story reward ownership writes and their corresponding ownership reads.
 mapping={ident:ident for ident in WEAPONS};mapping.update(weapon_permutation(seed+'/subweapons',selected_weapons));wm=json.loads(Path(m['weapon_manifest']).read_text())
 for row in wm['files']:
  files=get(row['stage']);b=bytearray(files[row['file']]);original=payloads(van,row['stage'])[row['file']]
  for e in row['edits']:
   p=e['offset'];old=e['original'];assert struct.unpack_from('<I',original,p)[0]==old
   struct.pack_into('<I',b,p,mapping[old]);weaponlog.append(dict(stage=row['stage'],file=row['file'],offset=p,original=old,reward=mapping[old],operation=e['operation']))
  files[row['file']]=bytes(b)
 # Rebuild distinct story fights using the user's exhaustion-before-repeat rule.
 _,encounters,profiles,sources,_,_,_=catalog(seed)
 variants=variant_profiles(van,profiles,include_viola_ai=include_viola_ai);used_variants={}
 variants={identity:[p for p in rows if p['variant_label'] in selected_bosses] for identity,rows in variants.items()}
 oldboss={r['stage']:r for r in m['boss_changes']}
 for allocation in allocations:
  stage=allocation['stage'];files=get(stage);source=sources[stage];names={r['file'] for r in source};assert len(names)==1
  name=names.pop();b=bytearray(files[name]);stock=payloads(van,stage);old=oldboss.get(stage)
  if old:
   for r in old['sites']:p=r['source_call'];b[p:p+5]=stock[name][p:p+5]
   for r in old['source_visual_overrides']+old['source_registration_overrides']:p=r['offset'];b[p:p+5]=stock[name][p:p+5]
  for row in source:
   offsets=[a['offset'] for a in row['contract']['arguments'] if a['offset'] is not None];start=min(offsets)-3;end=row['offset']+5
   assert b[start:end]==row['data'][start:end],(stage,'source boss frame changed')
  profile=choose_profile(seed,allocation,profiles,variants,used_variants);sites=[dict(offset=r['offset'],command=r['command'],phase_index=i) for i,r in enumerate(source)]
  patched,report=append_mixed_handoff(bytes(b),sites,profile,hashlib.sha256(b).hexdigest(),suppress_nephtis_pole_visuals=True,guard_source_fades=True)
  required,texaliases,assetreport=assets(van,profile)
  # Donor discovery traverses sets. Canonicalise diagnostic list order so
  # repeated seeds keep the same boss-mapping/category fingerprints.
  assetreport['motion_dependencies']=sorted(assetreport.get('motion_dependencies',[]),key=lambda r:(r['script'],r['library']))
  if profile['boss']=='Nephtis':
   for key in ('389b56cb.tex','91da1b63.mdz'):required[key]=(L/'Campaign-Boss-Handoff-Candidates/wn01-assets'/key).read_bytes()
   reserved={s['source_actor_id'] for s in report['sites']}
   for site in report['sites']:
    xyz=[struct.unpack('<f',struct.pack('<I',a['value']))[0] if a['kind']==0xc1 else float(a['value']) for a in site['coordinates'][:3]];x,y,z=xyz
    poles,cube=(SNOW_POLES,SNOW_CUBE) if stage=='ca02' else ([(x+dx,y,z+dz) for dx,dz in ((-800,-600),(0,-900),(800,-600),(-1000,0),(1000,0),(-800,600),(0,900),(800,600))],(x,y,z-1200))
    patched,info=append_nephtis_support(patched,site['source_call'],site['procedure_entry'],seed+'/bosses',stage,str(site['source_call']),poles,cube,reserved)
    reserved.update(info['poles']['actor_ids']);reserved.add(info['cube']['actor_id'])
  for label,pairs in texaliases.items():
   for suffix,donor in pairs.items():aliases[label]['@'+stage+'_'+suffix]=donor
   if profile['boss']=='Nephtis':
    for suffix in ('.dat','.tbl'):aliases[label]['@'+stage+'_389b56cb'+suffix]='@fc01_389b56cb'+suffix
  files.update(required);files[name]=patched+bytes((-len(patched))%16)
  report.update(allocation,stage=stage,file=name,assets=assetreport,variant=profile.get('variant_label',profile['boss']),gameplay_verified=False)
  bosslog.append(report);print('Boss',stage,'->',report['variant'],flush=True)
 # Preserve native Vector Cannon reward/check bytes from the verified baseline.
 for row in json.loads((L/'weapon-ownership-script-sites.json').read_text()):
  if row['index']==5 and row['stage'] in updates:
   stage,name,p=row['stage'],row['file'],row['offset'];assert updates[stage][name][p-7:p+6]==payloads(base,stage)[name][p-7:p+6],('Vector Cannon altered',stage,p)
 print('Packing',len(updates),'updated stage sections…',flush=True)
 for stage,want in updates.items():
  before=payloads(base,stage);replacements={k:v for k,v in want.items() if k in before and before[k]!=v};imports=[(k,v) for k,v in want.items() if k not in before]
  blocks[stage]=rebuild_section(base,stage,replacements,imports)
 write_archive(base,blocks,out/'STAGE.DAT');arc=Archive(out/'STAGE.DAT')
 for stage,want in updates.items():assert payloads(arc,stage)==want,stage
 for stage in arc.stages:
  for g in arc.groups(stage):arc.decode(g)
 m.update(release_name='Seed v6 experimental',seed=seed,candidate_seed=seed,enemy_seed=seed+'/enemies',boss_seed=seed+'/bosses',subweapon_seed=seed+'/subweapons',patched_sha256=sha(out/'STAGE.DAT'),atlas_aliases=aliases,boss_changes=bosslog+[r for r in m['boss_changes'] if r['stage'] not in ORDER],installed=False,gameplay_verified=False,full_requirements_complete=False,full_campaign_gameplay_verified=False)
 m['enemy_compatibility_edits']=compatibility_edits
 m['settings'].update(mosquito_excluded=True,metatron_subweapon_chance_percent=20 if selected_weapons else 0)
 m['settings']['include_viola_ai']=bool(include_viola_ai)
 m['settings']['boss_variants']={identity:[n for n in selected_bosses if BOSSES[n]==identity] for identity in ('Anubis','Ardjet')}
 m['boss_variant_rule']='Use remaining variants within each identity before a variant repeats; identities still share the approved compatible exhaustion rule.'
 m['seed_scope']=dict(rerolled=['eligible regular enemy assignments','12 distinct story boss allocations','compatible music bank maps','story subweapon rewards and runtime Metatron seed','Spider stream'],protected=dict(m['fallback_sections']),full_campaign_reroll_complete=False)
 m['seed_scope']['protected']={k:v for k,v in m['seed_scope']['protected'].items() if k not in ORDER}
 m['fallback_sections']=dict(m['seed_scope']['protected'])
 m['historical_enemy_topology']=m.pop('enemy_changes')
 m['enemy_changes']=[dict(stage=s,assignments=[r for r in enemylog if r['stage']==s],current_mapping_manifest='enemy-mapping.json') for s in sorted({r['stage'] for r in enemylog})]
 m['historical_boss_identity_policy']=m.pop('boss_identity_policy',None)
 m['boss_mapping_policy']='Per distinct story encounter; compatible bag exhaustion before repeats'
 m['boss_mapping_is_permutation']=False
 m['linked_identity_mapping']={}
 m['boss_repeat_rule']='Release requires no repeated main identity. Historical bag allocation remains diagnostic only until enough safe identities exist.'
 m['metatron_runtime_not_integrated']=False
 from metatron_manifest import manifest as metatron_manifest
 save(out/'metatron-counter-manifest.json',metatron_manifest(seed,chance=m['settings']['metatron_subweapon_chance_percent'],pool=selected_weapons))
 m['weapon_manifest']=str(out/'subweapon-mapping.json')
 save(out/'enemy-mapping.json',enemylog);save(out/'boss-mapping.json',bosslog);save(out/'subweapon-mapping.json',dict(seed=seed+'/subweapons',mapping=mapping,files=weaponlog,enabled_pool=selected_weapons,metatron_runtime_seed=seed,metatron_chance_percent=m['settings']['metatron_subweapon_chance_percent'],vector_cannon_protected=True))
 save(out/'manifest.json',m)
 shutil.copytree(V5/'runtime',out/'runtime')
 for name in ('CaptureEncounter.exe','Capture stuck encounter.cmd','Record progression.cmd','Attach at main menu.cmd','Install-preview.ps1','Install preview.cmd','Restore previous build.cmd'):shutil.copy2(V5/name,out/name)
 from capture_diagnostics import build as build_capture
 build_capture(out,seed,m['patched_sha256'])
 # Independent Spider stream, supplied as runtime configuration by this helper.
 sp=out/'runtime/SpiderReplacementAdapter.cs';text=sp.read_text();assert text.count('(uint)3972873655')==1
 sp.write_text(text.replace('(uint)3972873655','(uint)'+str(int.from_bytes(rank(seed,'spider','runtime')[:4],'little'))));compile_cs(sp,sp.with_suffix('.exe'))
 # Reuse the tested music compiler, with seed and output roots parameterized.
 audio=(W/'ship-v5/source/build_audio.py').read_text()
 audio=audio.replace("R=Path(__file__).resolve().parents[1];W=R.parent;OUT=R/'Ship-v5'",'R=Path('+repr(str(directory))+');W=Path('+repr(str(W))+');OUT=R/\'Ship-v5\'')
 audio=audio.replace("SEED=json.loads((R/'seed.json').read_text())['seed']",'SEED='+repr(seed))
 audio=audio.replace(' # Reuse the previously machine-tested', ' from beyond_bounds import prepare\n patches.extend(prepare(tree,OUT))\n # Reuse the previously machine-tested')
 voice_start=audio.index(' # Expand from two hardcoded pairs')
 voice_end=audio.index(" for bank in m['original_music_banks']:",voice_start)
 audio=audio[:voice_start]+" from ada_gameplay import build as build_ada\n voices,voice_report=build_ada(tree,OUT,SEED,SOUND,clean)\n m=json.loads((OUT/'manifest.json').read_text());m['music_track_shuffle']=json.loads((R/'reports/music-tracks-verification.json').read_text())\n m['ada_overlay']=voice_report\n mapping=voice_report['mapping']\n"+audio[voice_end:]
 audio=audio.replace("print('ADA',len(voices),'files',mapping,flush=True)","print('Compatible ADA gameplay clips shuffled:',len(mapping),flush=True)")
 audio=audio.replace(' exec(compile(text'," from audio_generation_support import pinned_music_input\n text=pinned_music_input(text,Path("+repr(original_inputs['stage']['path'])+"))\n exec(compile(text")
 audio=audio.replace(" exec(compile(text", " text=text.replace('families={};ineligible=[]',\"bank_stages[0xf0b0].update(bank_stages[0x2287f])\\n families={};ineligible=[]\")\n text=text.replace(\"assert (GAME/'sound/Windows'/path).is_file()\",\"assert (GAME/'sound/Windows'/path).is_file() or (ROOT/'Ship-v5/audio/files'/path).is_file()\")\n exec(compile(text")
 # build_audio has its normal main guard; call explicitly.
 audioenv={'__name__':'seeded_audio','__file__':str(W/'ship-v5/source/build_audio.py')};exec(compile(audio,'seeded_audio_builder','exec'),audioenv);audioenv['build']()
 m=json.loads((out/'manifest.json').read_text())
 m['beyond_the_bounds']=json.loads((out/'audio/beyond-the-bounds.json').read_text())
 m['beyond_the_bounds'].update(included=True,in_music_pool=True)
 m['music_track_shuffle']['beyond_the_bounds_asset_identified']=True
 m['preview_ready_for_install']=not skip_atlases
 sys.path.insert(0,str(W/'progression-v4/source'));import build_candidate as bc
 bc.OUT=out;bc.ROOT=directory;bc.bank_helpers(van,arc,m)
 from selected_rewards import configure as configure_rewards
 configure_rewards(out,selected_weapons)
 m['runtime_helpers']=[h for h in m['runtime_helpers'] if h['file']!='SkyResourceAdapter.exe']
 m.pop('sky_resource_fix',None)
 m['release_name']='Seed v6.4.5 — experimental controls; diagnostic gameplay candidate'
 from attachment_support import prepare as prepare_attachment
 prepare_attachment(out)
 for helper in m['runtime_helpers']:helper['sha256']=sha(out/'runtime'/helper['file'])
 save(out/'manifest.json',m)
 # Generate atlas aliases against the preserved original atlases.
 for label,pairs in aliases.items():(out/(label+'-aliases.tsv')).write_text(''.join(k+'\t'+v+'\n' for k,v in sorted(pairs.items())))
 atlasps=directory/'Build-Atlases.ps1'
 atlasps.write_text("$ErrorActionPreference='Stop'\nAdd-Type -Path '"+str(L/'CampaignAtlasAlias.cs')+"'\n"+''.join("[CampaignAtlasAlias]::BuildWithReplacements('"+original_inputs['atlases'][name]['path']+"','"+str(out/name)+"','"+str(L/'Loader-Test'/(label+'-index.txt'))+"','"+str(out/(label+'-aliases.tsv'))+"')\n" for label,name in [('small','atlas_pc_jp_Zlib_ps2.pac'),('main','atlas_pc_Zlib.pac')]))
 if not skip_atlases:subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(atlasps)],check=True)
 from installer_support import allow_new_files
 installer=out/'Install-preview.ps1';installer.write_text(allow_new_files(installer.read_text()))
 from boss_install_guard import ensure_gate
 ensure_gate(out)
 previous=json.loads((V5/'installation-plan.json').read_text());current={r['relative_path']:r['patched_sha256'] for r in previous['files']};current.update({r['relative_path']:r['sha256'] for r in previous['dependencies']})
 files=[dict(relative_path='ZOE2/STAGE.DAT',package_path='STAGE.DAT',expected_before_sha256=sha(GAME/'ZOE2/STAGE.DAT'),patched_sha256=m['patched_sha256'])]
 if not skip_atlases:
  for name in ('atlas_pc_jp_Zlib_ps2.pac','atlas_pc_Zlib.pac'):files.append(dict(relative_path='atlas/'+name,package_path=name,expected_before_sha256=sha(GAME/'atlas'/name),patched_sha256=sha(out/name)))
 for row in json.loads((directory/'reports/audio-install-files.json').read_text()):
  row=dict(row);row['expected_before_sha256']=sha(GAME/row['relative_path']) if (GAME/row['relative_path']).exists() else None;files.append(row)
 changed={r['relative_path'] for r in files};deps=[dict(relative_path=k,sha256=v) for k,v in current.items() if k not in changed]
 if not skip_atlases:save(out/'installation-plan.json',dict(format=1,baseline='Hash-pinned local installation at build time',files=files,dependencies=deps))
 hashes={k:hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest() for k,v in dict(enemies=enemylog,bosses=bosslog,subweapons=mapping,music=m['music_track_shuffle']['track_mapping'],ada=m['ada_overlay']['mapping']).items()}
 from build_policy import assess
 from apply_validation import BUILD_ID
 policy=assess(m,bosslog);save(out/'release-policy.json',policy)
 m['preview_ready_for_install']=not skip_atlases and policy['passed'];m['release_policy']=policy;save(out/'manifest.json',m)
 result=dict(seed=seed,archive_sha256=m['patched_sha256'],category_manifest_hashes=hashes,gameplay_verified=False,package=str(out),build_id=BUILD_ID,installable=not skip_atlases and policy['passed'],payloads_complete=not skip_atlases,blocked_reasons=policy['blockers'],protected_sections=m['seed_scope']['protected'])
 from verify_builds import verify as verify_archive
 from verify_features import verify as verify_features
 validation=verify_archive(out);validation.update(verify_features(out),passed=True)
 (out/'verification').mkdir(exist_ok=True);save(out/'verification/automatic-checks.json',validation)
 save(out/'build-result.json',result)
 from validate_boss_spawns import validate as validate_bosses
 save(out/'verification/boss-spawn-validation.json',validate_bosses(out))
 sealed=['manifest.json','boss-mapping.json','enemy-mapping.json','subweapon-mapping.json','build-result.json','installation-plan.json','Install-preview.ps1','Validate boss spawns.ps1','boss-spawn-check.json','release-policy.json','randomisation-settings.json'] if not skip_atlases else ['manifest.json','boss-mapping.json','build-result.json']
 sealed+= [r['package_path'] for r in files]
 sealed+= ['original-inputs.json']
 sealed+= ['runtime/'+r['file'] for r in m['runtime_helpers']]
 sealed+= ['runtime/Attach-Full-Preview.ps1','Attach at main menu.cmd']
 current_sources={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}
 if current_sources!=source_hashes:raise ValueError('Generator source changed during this build; candidate is unsealed. Rebuild after source changes finish.')
 save(out/'build-provenance.json',dict(format=2,build_id=BUILD_ID,seed=seed,python=sys.executable,include_viola_ai=include_viola_ai,source_snapshot_stable=True,package_hashes={name:sha(out/name) for name in sorted(set(sealed))},source_hashes=source_hashes))
 save(out/'checksums.json',{p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file() and p.name!='checksums.json'})
 print('BUILD COMPLETE',json.dumps(result),flush=True);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--seed',required=True);p.add_argument('--output',required=True);p.add_argument('--skip-atlases',action='store_true');p.add_argument('--include-viola-ai',action='store_true');p.add_argument('--include-neith-experimental',action='store_true');p.add_argument('--settings');a=p.parse_args()
 try:result=generate(a.seed,a.output,a.skip_atlases,a.include_viola_ai,json.loads(Path(a.settings).read_text()) if a.settings else None,a.include_neith_experimental)
 except ExperimentalBossUnavailable as ex:print('BUILD BLOCKED: '+str(ex),file=sys.stderr);sys.exit(2)
 if result.get('installable'):
  from build_cleanup import cleanup_after_build
  print('Build retained. Automatic build deletion is disabled in the tester edition.',flush=True)
