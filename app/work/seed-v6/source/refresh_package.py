import portable_paths as _portable
"""Refresh audio and metadata without rebuilding a byte-identical archive/atlas."""
import ast,sys,json,subprocess,hashlib
from pathlib import Path
import seed_builder as sb
from archive_tools import *
from installer_support import allow_new_files
def audio_refresh(out):
 out=Path(out).resolve();m=json.loads((out/'manifest.json').read_text());seed=m['seed'];directory=out.parent
 source=Path(sb.__file__).read_text();fn=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='generate');chosen=[];active=False
 for node in fn.body:
  if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='audio':active=True
  if active and isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='m':break
  if active:chosen.append(node)
 exec(compile(ast.Module(body=chosen,type_ignores=[]),str(sb.__file__),'exec'),dict(vars(sb),out=out,directory=directory,seed=seed))
 seal(out,True)
def seal(out,installable=False):
 out=Path(out).resolve();m=json.loads((out/'manifest.json').read_text());seed=m['seed']
 m['beyond_the_bounds']=json.loads((out/'audio/beyond-the-bounds.json').read_text());m['beyond_the_bounds'].update(included=True,in_music_pool=True)
 m['music_track_shuffle']['beyond_the_bounds_asset_identified']=True
 m['fallback_sections']={k:v for k,v in m['fallback_sections'].items() if k not in sb.ORDER}
 enemy=json.loads((out/'enemy-mapping.json').read_text())
 if 'historical_enemy_topology' not in m:m['historical_enemy_topology']=m.pop('enemy_changes')
 m['enemy_changes']=[dict(stage=s,assignments=[r for r in enemy if r['stage']==s],current_mapping_manifest='enemy-mapping.json') for s in sorted({r['stage'] for r in enemy})]
 m['historical_boss_identity_policy']=m.pop('boss_identity_policy',m.get('historical_boss_identity_policy'))
 m['boss_mapping_policy']='Per distinct story encounter; compatible bag exhaustion before repeats';m['linked_identity_mapping']={};m['boss_mapping_is_permutation']=False
 m['beyond_the_bounds_asset_identified']=True;m['preview_ready_for_install']=installable;m['full_requirements_complete']=False;m['archive_changes']=True
 m['seed_scope']['protected']=m['fallback_sections'];m['seed_scope']['full_campaign_reroll_complete']=False
 from metatron_manifest import manifest as metatron_manifest
 save(out/'metatron-counter-manifest.json',metatron_manifest(seed))
 capture=(W/'progression-v4/source/CaptureEncounter.cs').read_text().replace('var snapshot=Obj("utc",','var snapshot=Obj("candidate_seed",'+json.dumps(seed)+',"archive_sha256",'+json.dumps(m['patched_sha256'])+',"utc",')
 (out/'CaptureEncounter.cs').write_text(capture);subprocess.run([sb.CSC,'/nologo','/platform:x64','/optimize+','/r:System.Web.Extensions.dll','/out:'+str(out/'CaptureEncounter.exe'),str(out/'CaptureEncounter.cs')],check=True)
 subprocess.run([str(out/'CaptureEncounter.exe'),'--self-test'],check=True)
 for h in m['runtime_helpers']:h['sha256']=sha(out/'runtime'/h['file'])
 (out/'Install-preview.ps1').write_text(allow_new_files((V5/'Install-preview.ps1').read_text()))
 if installable:
  old=json.loads((out/'installation-plan.json').read_text());rows=[r for r in old['files'] if not r['relative_path'].startswith('sound/')]
  rows+=json.loads((out.parent/'reports/audio-install-files.json').read_text())
  for r in rows:
   p=sb.GAME/r['relative_path'];r['expected_before_sha256']=sha(p) if p.exists() else None
  save(out/'installation-plan.json',dict(old,files=rows))
  m['atlases']=[dict(file=r['package_path'],sha256=r['patched_sha256']) for r in rows if r['relative_path'].startswith('atlas/')]
 save(out/'manifest.json',m)
 hashes={k:hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest() for k,v in dict(enemies=enemy,bosses=sb.boss_schedule(seed),subweapons=json.loads((out/'subweapon-mapping.json').read_text())['mapping'],music=m['music_track_shuffle']['track_mapping']).items()}
 # JSON object keys become strings in the archived subweapon map. Normalize
 # to integer keys, matching the builder's deterministic canonical input.
 weapons={int(k):v for k,v in json.loads((out/'subweapon-mapping.json').read_text())['mapping'].items()};hashes['subweapons']=hashlib.sha256(json.dumps(weapons,sort_keys=True).encode()).hexdigest()
 result=dict(seed=seed,archive_sha256=m['patched_sha256'],category_manifest_hashes=hashes,gameplay_verified=False,package=str(out),build_id='seed-v6.2-btb',installable=installable,protected_sections=m['fallback_sections'])
 save(out/'build-result.json',result);save(out/'checksums.json',{p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file() and p.name!='checksums.json'})
 print('SEALED',seed,m['patched_sha256'],'Beyond the Bounds pool size',len(m['music_track_shuffle']['track_mapping']))
if __name__=='__main__':
 if sys.argv[1]=='audio':audio_refresh(sys.argv[2])
 else:seal(sys.argv[2],(Path(sys.argv[2])/'installation-plan.json').exists())
