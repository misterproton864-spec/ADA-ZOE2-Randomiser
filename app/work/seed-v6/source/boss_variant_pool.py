import portable_paths as _portable
"""Seeded native encounter variants, sharing their existing boss identity bag.

Native code evidence is saved in work/resource-v6.4/native. These are offline
validated experimental handoffs, not a claim of completed gameplay testing.
"""
import copy,hashlib,json
from archive_tools import L
from mixed_boss_catalog import payloads
from boss_spawn_contracts import decode_story_boss,ARDJET_STORY
from scx_first_boss_handoff import literal,native

ANUBIS_VARIANTS=(('ba03','Anubis 1'),('fr04g','Anubis 2'),
 ('cs01','Compressed-space Anubis'),('fa01','Fake Anubis'),('am02','Aumaan Anubis'))

def variant_profiles(archive,profiles,include_viola_ai=False):
 result={'Anubis':[], 'Ardjet':[]}
 for stage,label in ANUBIS_VARIANTS:
  p=copy.deepcopy(profiles[stage]);p.update(variant_label=label,boss_identity='Anubis')
  result['Anubis'].append(p)
 p=copy.deepcopy(profiles['ca02']);p.update(variant_label='Ardjet',boss_identity='Ardjet')
 result['Ardjet'].append(p)
 row=next(r for r in json.loads((L/'additional-verified-boss-contracts.json').read_text()) if r['stage']=='ef02g')
 data=payloads(archive,'ef02g')[row['file']]
 assert hashlib.sha256(data).hexdigest()==row['source_sha256']
 c=decode_story_boss(data,row['offset'],ARDJET_STORY);assert c['variant']==1
 p=dict(encounter='ef02g',boss='Ardjet',boss_identity='Ardjet',variant_label='Viola AI (full rescue fight)',
  asset_donor='ef02g',protected=False,full_viola_ai=True,
  templates=[dict(data=data,offset=row['offset'],command=ARDJET_STORY,file=row['file'],contract=c)])
 if include_viola_ai:result['Ardjet'].append(p)
 return result

def choose_profile(seed,allocation,profiles,variants,used_variants=None):
 identity=allocation['identity'];stage=allocation['stage']
 if identity in variants:
  used=set() if used_variants is None else used_variants.setdefault(identity,set())
  remaining=[v for v in variants[identity] if v['variant_label'] not in used]
  if not remaining:used.clear();remaining=variants[identity]
  p=min(remaining,key=lambda v:hashlib.sha256((seed+'\0boss-variant\0'+stage+'\0'+v['variant_label']).encode()).digest())
  used.add(p['variant_label'])
 else:
  p=profiles[{'Nephtis':'ba02','Vic Viper':'wn01','Inhert':'fr02'}[identity]]
 return copy.deepcopy(p)

def append_viola_callbacks(body,completion_callback):
 # Native infected Ardjet owns the grab mechanic, difficulty-scaled counter,
 # health and rescue detection. Never bypass success with an ordinary death.
 # ef02g success callback1277 uses the native 40-frame scheduler before its
 # story continuation. Give the native release animation the same interval.
 success=len(body);body.extend(native(0xffffb011,[literal(0xc0,40),literal(0xc5,completion_callback)])+b'\x89')
 resume=len(body);body.extend(native(0xffe438ce,[])+b'\x89')
 mid=len(body);body.extend(native(0xd1f9be9f,[literal(0xc5,resume)])+b'\x89')
 finish_failure=len(body);body.extend(native(0x90dfcb93,[])+b'\x89')
 failure=len(body);body.extend(native(0x144505ad,[]))
 body.extend(native(0xffcc3307,[literal(0xc0,n) for n in (0,0,0,0,500)]+[literal(0xc5,finish_failure)])+b'\x89')
 return (mid,failure),dict(success_callback=success,success_delay_frames=40,completion_callback=completion_callback,
  mid_callback=mid,resume_callback=resume,failure_callback=failure,
  finish_failure_callback=finish_failure,mid_resume_delayed_one_tick=False,native_recovery_scheduler=True,
  success='Source encounter completion after native AI counter reaches zero',
  failure='Native game-over init, fade, then game-over finish',
  counter_and_grab_native=True,gameplay_verified=False)
