import portable_paths as _portable
"""Hash-checked local proximity fixes; game files are never patched here."""
import hashlib,json,shutil
from pathlib import Path
STORE=Path(__file__).resolve().parents[1]/'runtime-fixes/proximity-v6'
CONTRACT={'version': '6.4.15-local.23-aumaan-heal-gate', 'contracts': [{'name': 'FakeAumaanReachAdapter', 'stage': 'shuffled combat actors', 'bindings': [['am01g', 4294781001], ['am01g', 4294912100], ['ba02', 4294915707], ['ba03', 4294959705], ['ca02', 4294892883], ['cs01', 4294959705], ['cy02', 4294915707], ['ef01', 4294915707], ['ef02g', 4294892883], ['fa01', 4294959705], ['fr02', 4294932111], ['fr04g', 4294959705], ['vc01', 4294915707], ['vs_ba02', 4294915707], ['vs_ca02', 4294892883], ['vs_cs01', 4294959705], ['vs_cy02', 4294915707], ['vs_ef01', 4294915707], ['vs_ef02', 4294892883], ['vs_vc01', 4294915707], ['vs_wn01', 2146269963], ['wn01', 2146269963]], 'native_arena': 'am02', 'native_original_called_once': True, 'gameplay_verified': False, 'healing_states': [20, 21, 24], 'shared_motion_states': [22, 23], 'tick_entry': 432, 'heal_gate_entry': 0, 'hooks': [{'entry': '0x1404f4c90', 'offset': 0, 'stolen': 'e9abd22a07'}, {'entry': '0x14778e180', 'offset': 512, 'stolen': '4889742420'}, {'entry': '0x147790550', 'offset': 1024, 'stolen': '4889e048895808'}, {'entry': '0x147791970', 'offset': 1536, 'stolen': '48895c2410'}, {'entry': '0x147792e00', 'offset': 2048, 'stolen': '534883ec40'}, {'entry': '0x147794150', 'offset': 2560, 'stolen': '48895c2418'}], 'exe_sha256': '08f43180e1de0fad7d46477225982539eb0fff140a19b78fa623516763d1a23f', 'tick_sha256': 'd29b446ad19c47cb7cba7b87c984d5ac961806e251dcfa956ac5a9e9ff262f21'}], 'source_sha256': '83795a1cf0e93c085a689805acefd75ff26f5bf19e5ea8cd184e7474cc5813c3'}
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
