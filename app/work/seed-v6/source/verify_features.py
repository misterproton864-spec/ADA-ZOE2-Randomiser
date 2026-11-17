import portable_paths as _portable
"""Read back generated output independently of the emitters."""
import json,struct,hashlib
from pathlib import Path
from archive_tools import Archive,VAN,L,sha
from mixed_boss_catalog import payloads
from ada_gameplay import objects,fnv
from scx_bytecode import native_calls
from scx_call_arguments import call_arguments

def verify(package,write_report=True):
 p=Path(package);m=json.loads((p/'manifest.json').read_text());a=Archive(p/'STAGE.DAT');stock=Archive(VAN)
 bosschecks=[];variant_used={}
 for r in json.loads((p/'boss-mapping.json').read_text()):
  resources=payloads(a,r['stage']);b=resources[r['file']]
  for asset in r['assets']['files']:assert hashlib.sha256(resources[asset['name']]).hexdigest()==asset['sha256']
  if r['variant']=='Compressed-space Anubis':assert '827e775a.cvz' in resources
  if r['variant']=='Aumaan Anubis':assert '4c8c71d9.cvz' in resources
  if r['identity']=='Anubis':
   used=variant_used.setdefault('Anubis',set())
   selected=m.get('settings',{}).get('enabled_bosses')
   size=len([n for n in selected if 'Anubis' in n]) if selected is not None else 5
   if len(used)==size:used.clear()
   assert r['variant'] not in used;used.add(r['variant'])
  for site in r['sites']:
   for phase in site['phases']:
    frag=b[phase['entry']:phase['end']]+b'\x8e';command=int(phase['command'],16)
    off=next(off for off,h in native_calls(frag) if h==command)
    args=call_arguments(frag,off)
    callbacks=[arg['value'] for arg in args if arg['kind']==0xc5]
    assert phase['callback'] in callbacks and all(0<=q<len(b) for q in callbacks)
    if r['variant']=='Viola AI (full rescue fight)':
     c=site['viola_callbacks'];assert command==0xfffedd53 and args[1]['value']==1
     assert [x['value'] for x in args[-3:]]==[phase['callback'],c['mid_callback'],c['failure_callback']]
    bosschecks.append(dict(stage=r['stage'],variant=r['variant'],command=phase['command']))
 # Protect story AI-removal/Zakat code, allowing the separately requested
 # subweapon ownership/reward literals recorded by the reward generator.
 protected=[]
 weapons=json.loads((p/'subweapon-mapping.json').read_text())['files']
 for stage in ('ef02g','af02'):
  old=payloads(stock,stage);new=payloads(a,stage);assert old.keys()==new.keys()
  allowed={}
  for w in (w for w in weapons if w['stage']==stage):allowed.setdefault(w['file'],set()).update(range(w['offset'],w['offset']+4))
  for name,b in old.items():assert len(b)==len(new[name]) and all(v==new[name][i] or i in allowed.get(name,set()) for i,v in enumerate(b)),(stage,name)
  protected.append(stage)
 mission=[]
 for r in m.get('scripted_mission_randomisation',[]):
  old=payloads(stock,r['stage']);new=payloads(a,r['stage']);allowed={}
  for w in (w for w in weapons if w['stage']==r['stage']):allowed.setdefault(w['file'],set()).update(range(w['offset'],w['offset']+4))
  for e in r['selector_edits']:allowed.setdefault(e['file'],set()).update(range(e['offset'],e['offset']+4))
  for e in r['suppressed_pool_setups']:allowed.setdefault(e['file'],set()).update(range(e['offset'],e['offset']+5))
  for e in r['adapters']:allowed.setdefault(e['file'],set()).update(range(e['source_call'],e['source_call']+5))
  for name,b in old.items():
   if not name.endswith('.scx'):continue
   assert all(v==new[name][i] or i in allowed.get(name,set()) for i,v in enumerate(b)),(r['stage'],name)
  mission.append(r['stage'])
 assert len(mission)==7
 # Independent fleet check: older metadata covered only the middle legacy tail.
 # Audit the complete appended code area and the active relative-jump tail.
 from scx_bytecode import LENGTHS
 fleet=payloads(a,'af01g')['ecf4abd1.scx'];fleet_calls=dict(native_calls(fleet));q=113296
 while q<len(fleet):
  op=fleet[q];n=LENGTHS.get(op,1);assert q+n<=len(fleet)
  if op==0x88:fleet_calls[q]=struct.unpack_from('<I',fleet,q+1)[0]
  q+=n
 for q in (113306,113392,113504):
  assert fleet[q:q+5]==bytes.fromhex('885af7ffff'),('Fleet Narita setup remains',q)
 assert not ({0xf69f7524,0xffff9c3f}&set(fleet_calls.values()))
 assert {0x869acfd7,0x228def80}<=set(fleet_calls.values())
 for q,target in ((13219,113440),):
  assert fleet[q]==0x85 and q+struct.unpack_from('<i',fleet,q+1)[0]==target
 fleet_enemies={r['enemy'] for r in json.loads((p/'enemy-mapping.json').read_text()) if r['stage']=='af01g' and not r.get('protected')}
 assert fleet_enemies and fleet_enemies<={40,41}
 from verify_voice import verify as verify_voice
 voice_checks=verify_voice(p)
 for h in m['runtime_helpers']:assert sha(p/'runtime'/h['file'])==h['sha256']
 assert len(m['runtime_helpers'])==15 and not any(h['file']=='SkyResourceAdapter.exe' for h in m['runtime_helpers'])
 assert {'FakeAnubisDamageAdapter.exe','FakeAnubisDamageTableAdapter.exe','AumaanArenaGuard.exe'}<={h['file'] for h in m['runtime_helpers']}
 from validate_boss_spawns import validate as validate_boss_spawns
 boss_validation=validate_boss_spawns(p)
 if write_report:
  (p/'verification').mkdir(exist_ok=True)
  (p/'verification/boss-spawn-validation.json').write_text(json.dumps(boss_validation,indent=2)+'\n',encoding='utf-8')
 return dict(boss_spawn_validation_required=True,boss_spawn_validator_version=boss_validation['validator_version'],boss_spawn_phases_checked=boss_validation['spawn_phases_checked'],boss_phase_checks=bosschecks,protected_native_story_stages=protected,mission_script_prefixes_checked=mission,fleet_entry_narita_setups_removed=3,fleet_relative_jump_paths_checked=1,fleet_randomised_pool=[40,41],**voice_checks,gameplay_verified=False)
