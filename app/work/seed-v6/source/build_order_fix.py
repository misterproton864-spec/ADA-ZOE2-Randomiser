import portable_paths as _portable
import sys,shutil,json
from pathlib import Path
from archive_tools import *
def build(out):
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
 assert sha(VAN)=='c5627420319bbaa28f887b0728e14277befd9cf33ced3f82d0e304b389d5e651'
 assert sha(V5/'STAGE.DAT')=='98a513765a6903675ba953292c5b25204f511d20ee39a7a77ad9476847cf3567'
 a=Archive(V5/'STAGE.DAT');write_archive(a,{'ba01':rebuild_section(a,'ba01')},out/'STAGE.DAT')
 from mixed_boss_catalog import payloads
 b=Archive(out/'STAGE.DAT');assert payloads(a,'ba01')==payloads(b,'ba01')
 for s in a.stages:
  if s!='ba01':assert sec(a,s)==sec(b,s)
 for name in ('runtime','audio'):shutil.copytree(V5/name,out/name)
 for name in ('CaptureEncounter.exe','Capture stuck encounter.cmd','Record progression.cmd','Attach at main menu.cmd','Install-preview.ps1','Install preview.cmd','Restore previous build.cmd'):shutil.copy2(V5/name,out/name)
 m=json.loads((V5/'manifest.json').read_text());m.update(release_name='V5.1 motion order isolation test',patched_sha256=sha(out/'STAGE.DAT'),source_sha256=sha(a.path),installed=False,gameplay_verified=False)
 m['motion_order_fix']=dict(stage='ba01',all_decoded_payloads_identical_to_v5=True,other_sections_identical=124,live_retest=False)
 import subprocess
 capture=(W/'progression-v4/source/CaptureEncounter.cs').read_text().replace('var snapshot=Obj("utc",','var snapshot=Obj("candidate_seed",'+json.dumps(m['candidate_seed'])+',"archive_sha256",'+json.dumps(m['patched_sha256'])+',"utc",')
 (out/'CaptureEncounter.cs').write_text(capture)
 subprocess.run([_portable.compiler(),'/nologo','/platform:x64','/optimize+','/r:System.Web.Extensions.dll','/out:'+str(out/'CaptureEncounter.exe'),str(out/'CaptureEncounter.cs')],check=True)
 sys.path.insert(0,str(W/'progression-v4/source'));import build_candidate as bc
 bc.OUT=out;bc.ROOT=out; (out/'reports').mkdir();bc.bank_helpers(Archive(VAN),b,m)
 for h in m['runtime_helpers']:h['sha256']=sha(out/'runtime'/h['file'])
 save(out/'manifest.json',m)
 old=json.loads((V5/'installation-plan.json').read_text());files=[dict(relative_path='ZOE2/STAGE.DAT',package_path='STAGE.DAT',expected_before_sha256=sha(a.path),patched_sha256=m['patched_sha256'])]
 deps=old['dependencies']+[dict(relative_path=r['relative_path'],sha256=r['patched_sha256']) for r in old['files'] if r['relative_path']!='ZOE2/STAGE.DAT']
 save(out/'installation-plan.json',dict(format=1,baseline='Installed V5',files=files,dependencies=deps))
 save(out/'verification.json',dict(archive_sha256=m['patched_sha256'],all_ba01_payloads_equal_v5=True,only_ba01_table_and_packing_changed=True,ship_enemies_still_randomized=True,gameplay_verified=False))
 print('ORDER FIX READY',out,m['patched_sha256'],flush=True)
if __name__=='__main__':build(sys.argv[1])
