import portable_paths as _portable
import json,hashlib,shutil
from pathlib import Path
STORE=Path(__file__).resolve().parents[1]/"runtime-fixes/inhert-v1"
CONTRACT={'component': 'inhert-phase-one-1', 'helper': 'InhertPhaseAdapter.exe', 'exe_sha256': 'b6543d58b464e4b40e8d339b194389b106349985566c14be4f90af0b13b16ed3', 'source_sha256': 'eaff4ac9eed366ab76b51d56ce0362c0e00806086bbb0e9316c063151e65349e', 'native_stages': ['fr02', 'vs_fr02'], 'bindings': [{'stage': 'ca02', 'actor': 4294892883, 'close': True, 'recover': False}, {'stage': 'ba02', 'actor': 4294915707, 'close': False, 'recover': False}, {'stage': 'ba03', 'actor': 4294959705, 'close': False, 'recover': True}, {'stage': 'cy02', 'actor': 4294915707, 'close': True, 'recover': False}, {'stage': 'vc01', 'actor': 4294915707, 'close': True, 'recover': False}, {'stage': 'ef01', 'actor': 4294915707, 'close': False, 'recover': False}, {'stage': 'ef02g', 'actor': 4294892883, 'close': False, 'recover': False}, {'stage': 'cs01', 'actor': 4294959705, 'close': False, 'recover': True}, {'stage': 'fa01', 'actor': 4294959705, 'close': False, 'recover': True}, {'stage': 'fr04g', 'actor': 4294959705, 'close': False, 'recover': True}, {'stage': 'am01g', 'actor': 4294781001, 'close': False, 'recover': False}, {'stage': 'am01g', 'actor': 4294912100, 'close': False, 'recover': False}, {'stage': 'am02', 'actor': 3757126974, 'close': False, 'recover': True}, {'stage': 'vs_am02', 'actor': 3757126974, 'close': False, 'recover': True}, {'stage': 'vs_cs01', 'actor': 4294959705, 'close': False, 'recover': True}, {'stage': 'vs_ef02', 'actor': 4294892883, 'close': False, 'recover': False}, {'stage': 'vs_ef01', 'actor': 4294915707, 'close': False, 'recover': False}, {'stage': 'vs_vc01', 'actor': 4294915707, 'close': True, 'recover': False}, {'stage': 'vs_cy02', 'actor': 4294915707, 'close': True, 'recover': False}, {'stage': 'vs_wn01', 'actor': 2146269963, 'close': False, 'recover': True}, {'stage': 'vs_ba02', 'actor': 4294915707, 'close': False, 'recover': False}, {'stage': 'vs_ca02', 'actor': 4294892883, 'close': True, 'recover': False}, {'stage': 'wn01', 'actor': 2146269963}], 'threshold_gate': '0x146ad26b8', 'gameplay_verified': False}
HELPERS=frozenset((CONTRACT['helper'],))
def install(package):
 p=Path(package);name=CONTRACT['helper'];source=STORE/name
 if hashlib.sha256(source.read_bytes()).hexdigest()!=CONTRACT['exe_sha256']:raise ValueError('Inhert helper differs')
 shutil.copy2(source,p/'runtime'/name)
 (p/'inhert-phase-contract.json').write_text(json.dumps(CONTRACT,indent=2))
 return CONTRACT
def verify(package,manifest):
 p=Path(package);name=CONTRACT['helper']
 if manifest.get('inhert_phase_fixes')!=CONTRACT or json.loads((p/'inhert-phase-contract.json').read_text())!=CONTRACT:raise ValueError('Inhert phase guard contract differs')
 if hashlib.sha256((p/'runtime'/name).read_bytes()).hexdigest()!=CONTRACT['exe_sha256']:raise ValueError('Inhert phase guard binary differs')
 return dict(passed=True,gameplay_verified=False)
