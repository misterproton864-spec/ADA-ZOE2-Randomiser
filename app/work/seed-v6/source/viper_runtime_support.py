import portable_paths as _portable
"""One checked Viper controller and coordinated native-death fixes."""
import hashlib,json,shutil
from pathlib import Path
STORE=Path(__file__).resolve().parents[1]/'runtime-fixes/viper-v8'
CONTRACT={'format': 1, 'component': 'viper-combat-experimental-8', 'name': 'ViperCombatAdapter.exe', 'exe_sha256': '88a8469dee81244c17c553fd6d32c3531853c37fcd50ce0624b97a84a581507b', 'compiled_code_sha256': 'ab29f7818f2a09cfc15096e78270bf0b6cfb4c1224cb617ce581efc5dcc9b00c', 'source_sha256': 'da72dcee4995f4e4973f3fa510a06b95b5c7df89a778011bbcc8856f614812a8', 'config_size': 3656, 'source_bindings': [{'stage': 'ca02', 'actor': 4294892883, 'close': True, 'recover': False}, {'stage': 'ba02', 'actor': 4294915707, 'close': False, 'recover': False}, {'stage': 'ba03', 'actor': 4294959705, 'close': False, 'recover': True}, {'stage': 'cy02', 'actor': 4294915707, 'close': True, 'recover': False}, {'stage': 'vc01', 'actor': 4294915707, 'close': True, 'recover': False}, {'stage': 'ef01', 'actor': 4294915707, 'close': False, 'recover': False}, {'stage': 'ef02g', 'actor': 4294892883, 'close': False, 'recover': False}, {'stage': 'fr02', 'actor': 4294932111, 'close': False, 'recover': True}, {'stage': 'cs01', 'actor': 4294959705, 'close': False, 'recover': True}, {'stage': 'fa01', 'actor': 4294959705, 'close': False, 'recover': True}, {'stage': 'fr04g', 'actor': 4294959705, 'close': False, 'recover': True}, {'stage': 'am01g', 'actor': 4294781001, 'close': False, 'recover': False}, {'stage': 'am01g', 'actor': 4294912100, 'close': False, 'recover': False}, {'stage': 'am02', 'actor': 3757126974, 'close': False, 'recover': True}, {'stage': 'vs_am02', 'actor': 3757126974, 'close': False, 'recover': True}, {'stage': 'vs_cs01', 'actor': 4294959705, 'close': False, 'recover': True}, {'stage': 'vs_ef02', 'actor': 4294892883, 'close': False, 'recover': False}, {'stage': 'vs_ef01', 'actor': 4294915707, 'close': False, 'recover': False}, {'stage': 'vs_vc01', 'actor': 4294915707, 'close': True, 'recover': False}, {'stage': 'vs_cy02', 'actor': 4294915707, 'close': True, 'recover': False}, {'stage': 'vs_wn01', 'actor': 2146269963, 'close': False, 'recover': True}, {'stage': 'vs_ba02', 'actor': 4294915707, 'close': False, 'recover': False}, {'stage': 'vs_ca02', 'actor': 4294892883, 'close': True, 'recover': False}], 'hooks': [{'entry': '0x140772d10', 'cave_offset': 0, 'stolen': 'e96ba71709'}, {'entry': '0x1498eb385', 'cave_offset': 512, 'stolen': 'f783d415000000020000'}, {'entry': '0x14980fa08', 'cave_offset': 1024, 'stolen': '8b05ee5dd2f70b05e45dd2f7'}, {'entry': '0x14980fa87', 'cave_offset': 1536, 'stolen': '8b8350140000'}], 'relocation_cases': 9, 'native_original_mars_unchanged': True, 'arena_exclusions': [], 'gameplay_verified': False, 'movement_policy': 'Native locomotion and transformation; initialise once; no helper position writes or repeated ground-state reset', 'long_range_in_indoor_arenas': True}
HELPERS=frozenset(('ViperCombatAdapter.exe',))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def install(package):
 p=Path(package);name=CONTRACT['name'];source=STORE/name
 if sha(source)!=CONTRACT['exe_sha256']:raise ValueError('Viper controller binary differs')
 shutil.copy2(source,p/'runtime'/name)
 (p/'viper-combat-contract.json').write_text(json.dumps(CONTRACT,indent=2)+'\n',encoding='utf-8')
 return CONTRACT
def verify(package,manifest,rows=None):
 p=Path(package)
 if manifest.get('viper_combat_fixes')!=CONTRACT or json.loads((p/'viper-combat-contract.json').read_text())!=CONTRACT:raise ValueError('Viper combat support contract missing or altered')
 declared={r['file']:r['sha256'] for r in manifest['runtime_helpers']}
 if declared.get(CONTRACT['name'])!=CONTRACT['exe_sha256'] or sha(p/'runtime'/CONTRACT['name'])!=CONTRACT['exe_sha256']:raise ValueError('Missing or altered Viper combat helper')
 if any(n in declared for n in ('ArdjetViperReachAdapter.exe','ValleyViperAdapter.exe')):raise ValueError('Conflicting legacy Viper update hook')
 bindings={(r['stage'],r['actor']) for r in CONTRACT['source_bindings']};checked=[]
 walled={'ba02','ef01','ef02g','vs_ba02','vs_ef01','vs_ef02'}
 if {r['stage'] for r in CONTRACT['source_bindings'] if not r['close'] and not r['recover']} - {'am01g'}!=walled:
  raise ValueError('Walled long-range Vic Viper binding policy differs')
 side=manifest.get('side_modes') or {}
 sequence=(side.get('boss_sequence') or {}).get('encounters',[])
 extra=(side.get('extra_missions') or {}).get('boss_battle')
 targets=list(manifest.get('boss_changes',[]) if rows is None else rows)+list(sequence)+([extra] if extra else [])
 for row in targets:
  if row['stage']=='wn01':continue
  for site in row['sites']:
   if site.get('replacement_identity',row['identity'])!='Vic Viper':continue
   if (row['stage'],site['source_actor_id']) not in bindings:raise ValueError('Viper source actor is not covered by the native fixes: '+row['stage'])
   if any(phase['actor_id']!=site['source_actor_id'] for phase in site['phases']):raise ValueError('Unexpected additional Viper phase identity')
   checked.append(dict(stage=row['stage'],actor_id=site['source_actor_id'],callback=site['source_completion_callback']))
 return dict(passed=True,source_bindings_checked=checked,arena_exclusions=[],gameplay_verified=False)
