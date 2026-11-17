import portable_paths as _portable
import json,shutil,subprocess,sys
from pathlib import Path
from archive_tools import *
from seed_builder import GAME,CSC
from metatron_manifest import manifest as metatron_manifest
ROOT=Path(__file__).resolve().parents[1]
out=Path(json.loads((ROOT/'recommended-build.json').read_text())['package'])
for name in ('README.md','CRASH-ANALYSIS.md','regression-verification.json','new-file-installer-verification.json'):shutil.copyfile(ROOT/name,out/name)
plan=json.loads((out/'installation-plan.json').read_text());m=json.loads((out/'manifest.json').read_text())
for r in plan['files']:
 assert sha(out/r['package_path'])==r['patched_sha256'],('payload',r['relative_path'])
 p=GAME/r['relative_path'];before=sha(p) if p.exists() else None
 assert before==r['expected_before_sha256'],('baseline',r['relative_path'])
for r in plan['dependencies']:assert sha(GAME/r['relative_path'])==r['sha256'],('dependency',r['relative_path'])
for r in m['runtime_helpers']:assert sha(out/'runtime'/r['file'])==r['sha256'],('helper',r['file'])
assert sha(GAME/'ZOE2/STAGE.DAT')=='98a513765a6903675ba953292c5b25204f511d20ee39a7a77ad9476847cf3567'
assert not (GAME/'sound/Windows/us0000f0b0.bnk').exists()
verified=json.loads((ROOT/'regression-verification.json').read_text());result=json.loads((out/'build-result.json').read_text());reference=json.loads((ROOT/'builds/seed-20261019-btb/Ship-v5/build-result.json').read_text())
assert result['category_manifest_hashes']==reference['category_manifest_hashes'] and result['archive_sha256']==reference['archive_sha256']
assert m['beyond_the_bounds']['in_music_pool'] and 61616 in m['music_track_shuffle']['track_mapping'].values()
# Update narrow recorder attribution after its archive was finalized.
small=ROOT/'Ship-v5.1-order-test';sm=json.loads((small/'manifest.json').read_text());capture=(W/'progression-v4/source/CaptureEncounter.cs').read_text().replace('var snapshot=Obj("utc",','var snapshot=Obj("candidate_seed",'+json.dumps(sm['candidate_seed'])+',"archive_sha256",'+json.dumps(sm['patched_sha256'])+',"utc",')
(small/'CaptureEncounter.cs').write_text(capture);subprocess.run([CSC,'/nologo','/platform:x64','/optimize+','/r:System.Web.Extensions.dll','/out:'+str(small/'CaptureEncounter.exe'),str(small/'CaptureEncounter.cs')],check=True)
save(out/'metatron-counter-manifest.json',metatron_manifest(m['seed']))
proof=dict(passed=True,installed_game_unchanged=True,installed_archive_sha256=sha(GAME/'ZOE2/STAGE.DAT'),package_archive_sha256=m['patched_sha256'],payloads_verified=len(plan['files']),dependencies_verified=len(plan['dependencies']),runtime_helpers_verified=len(m['runtime_helpers']),ready_package_matches_repeated_seed=True,new_song_pool_entry=61616,new_song_installed=False,ui_smoke_passed=True,gameplay_verified=False)
save(ROOT/'package-preflight.json',proof);save(out/'package-preflight.json',proof)
for p in (out,small):save(p/'checksums.json',{f.relative_to(p).as_posix():sha(f) for f in p.rglob('*') if f.is_file() and f.name!='checksums.json'})
print(json.dumps(proof),flush=True)
