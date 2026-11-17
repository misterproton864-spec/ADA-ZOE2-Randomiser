import portable_paths as _portable
"""Hash-checked local proximity fixes; game files are never patched here."""
import hashlib,json,shutil
from pathlib import Path
STORE=Path(__file__).resolve().parents[1]/'runtime-fixes/proximity-v5'
CONTRACT={'version': '6.4.15-local.13-aumaan-recovery-experimental', 'contracts': [{'name': 'FakeAumaanReachAdapter', 'stage': 'shuffled combat actors', 'bindings': [['am01g', 4294781001], ['am01g', 4294912100], ['ba02', 4294915707], ['ba03', 4294959705], ['ca02', 4294892883], ['cs01', 4294959705], ['cy02', 4294915707], ['ef01', 4294915707], ['ef02g', 4294892883], ['fa01', 4294959705], ['fr02', 4294932111], ['fr04g', 4294959705], ['vc01', 4294915707], ['wn01', 2146269963]], 'native_arena': 'am02', 'native_original_called_once': True, 'gameplay_verified': False, 'healing_states': [20, 21, 24], 'shared_motion_states': [22, 23], 'tick_entry': 768, 'heal_gate_entry': 0, 'hooks': [{'entry': '0x1404f4c90', 'offset': 0, 'stolen': 'e9abd22a07'}, {'entry': '0x14778e180', 'offset': 512, 'stolen': '4889742420'}, {'entry': '0x147790550', 'offset': 1024, 'stolen': '4889e048895808'}, {'entry': '0x147791970', 'offset': 1536, 'stolen': '48895c2410'}, {'entry': '0x147792e00', 'offset': 2048, 'stolen': '534883ec40'}, {'entry': '0x147794150', 'offset': 2560, 'stolen': '48895c2418'}], 'exe_sha256': 'dacf4853db955d16aaedc68b3de77fe480d49b11cf0df67ee35ec4dc990e5d7e', 'tick_sha256': '44d96f75f3da0cea10a551a5a62510c1623734725e2a4c8d6c310a988215b8a2', 'recovery_policy': '90 sustained post updates; 300-unit offset from Jehuty; native trace candidate; 180-update success cooldown; 30-update failed retry'}], 'source_sha256': 'dc8ebf6552301c09205eabbabc947e5dacd72086e0e045e44f4ab4288767bb38'}
HELPERS=frozenset(c['name']+'.exe' for c in CONTRACT['contracts'])
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def install(package):
 p=Path(package);(p/'runtime').mkdir(exist_ok=True)
 for c in CONTRACT['contracts']:
  name=c['name']+'.exe';source=STORE/name
  if sha(source)!=c['exe_sha256']:raise ValueError('Local proximity helper changed: '+name)
  shutil.copy2(source,p/'runtime'/name)
 (p/'proximity-fix-contract.json').write_text(json.dumps(CONTRACT,indent=2)+'\n',encoding='utf-8')
 return CONTRACT

def verify(package,manifest):
 p=Path(package)
 if manifest.get('proximity_fixes')!=CONTRACT:raise ValueError('Proximity support contract missing or changed')
 if json.loads((p/'proximity-fix-contract.json').read_text(encoding='utf-8'))!=CONTRACT:raise ValueError('Packaged proximity contract differs')
 declared={h['file']:h['sha256'] for h in manifest['runtime_helpers']}
 for c in CONTRACT['contracts']:
  name=c['name']+'.exe'
  if declared.get(name)!=c['exe_sha256'] or sha(p/'runtime'/name)!=c['exe_sha256']:raise ValueError('Missing or altered proximity helper: '+name)
 return dict(passed=True,helpers=sorted(HELPERS),gameplay_verified=False)
