import portable_paths as _portable
"""Conservative finite swarm candidates; source/target actor objectives stay native."""
import hashlib,struct
from collections import Counter
from native_seed_rules import REGULAR_STAGES,REGULAR_TYPES
from scx_bytecode import native_calls
from scx_call_arguments import UnresolvedArguments
from regular_selectors import triples
from randomizer_settings import weighted_enemy

COMMAND=0x1ffa5693
PROTECTED_STAGES=frozenset(('ba01','fr01c'))
MAX_AUTHORED_COUNT=6
MAX_STAGE_BUDGET=72

def ene_records(data):
 if len(data)<32:raise ValueError('Truncated swarm ENE')
 count=struct.unpack_from('<H',data,2)[0];base=struct.unpack_from('<I',data,4)[0]
 if base<32 or base+count*112>len(data):raise ValueError('Invalid swarm ENE bounds')
 return count,base

def eligibility(stage,row,files,selectors):
 referenced=set();unresolved=False;factories=0
 for name,data in files.items():
  if not name.endswith('.scx'):continue
  for offset,command in native_calls(data):
   factories+=int(command==COMMAND)
   if command not in selectors:continue
   try:
    for group,typ,ordinal in triples(data,offset,command):
     if group['kind']!=0xc0 or typ['kind']!=0xc0 or group['value'] in (None,0,0xffffffff):unresolved=True
     else:referenced.add(group['value'])
   except UnresolvedArguments:unresolved=True
 ene={name:(data,*ene_records(data)) for name,data in files.items() if name.endswith('.ene')}
 eligible=[];excluded=[]
 for slot in row['slots']:
  if slot['original_type'] not in REGULAR_TYPES:continue
  data,count,base=ene[slot['file']];record=slot['record'];index=slot['slot'];p=base+record*112
  if record>=count or index>3 or slot['offset']!=p+48+index*8:raise ValueError('Swarm source slot/layout differs')
  if data[slot['offset']:slot['offset']+3]!=bytes((slot['original_type'],slot['count'],slot['level'])):raise ValueError('Swarm source identity/count/level differs')
  group=struct.unpack_from('<I',data,p+0x58)[0];flags=struct.unpack_from('<H',data,p+0x50)[0]
  if group!=slot['script_group_id']:raise ValueError('Swarm source group differs')
  native=[r for r in range(count) if any(data[base+r*112+48+j*8]==10 for j in range(4))]
  reasons=[]
  if stage not in REGULAR_STAGES or stage in PROTECTED_STAGES:reasons.append('Mission/regression boundary remains protected')
  if not factories:reasons.append('No resident native swarm factory')
  if unresolved:reasons.append('Computed/global actor references remain protected')
  if group in referenced:reasons.append('Group requires individual enemy actor references')
  if not native or record<=min(native):reasons.append('Original ambient tracking row must remain first')
  if record in native:reasons.append('Record already contains a native swarm')
  if len(native)>=255:reasons.append('Native tracking row limit reached')
  if not 1<=slot['count']<=MAX_AUTHORED_COUNT:reasons.append('Finite swarm requires positive count within limit')
  if flags not in (0,1):reasons.append('Unqualified swarm spawn/recycling flags')
  # A runtime rule must not also match an original swarm in an alternate layout.
  for other,other_count,other_base in ene.values():
   if record>=other_count:continue
   q=other_base+record*112
   if (struct.unpack_from('<I',other,q+0x58)[0]==group and
       other[q+48+index*8:q+50+index*8]==bytes((10,slot['count']))):
    reasons.append('Rule is ambiguous with an original swarm in another layout');break
  spec=dict(slot,initial_budget=slot['count']*6,native_record_flags=flags,
   native_tracking_records=len(native),
   source_file_sha256=hashlib.sha256(data).hexdigest())
  if reasons:excluded.append(dict(spec,reasons=sorted(set(reasons))))
  else:eligible.append(spec)
 return dict(stage=stage,eligible=eligible,excluded=excluded,
  reasons=dict(Counter(reason for spec in excluded for reason in spec['reasons'])),
  resident_factory_sites=factories,gameplay_verified=False)

def select(seed,stage,candidates,weights,pool):
 chosen=[];occupied=set();budget=0;declined=[];perfile=Counter()
 order=sorted(candidates,key=lambda r:hashlib.sha256((str(seed)+'\0finite-swarm-order\0'+stage+'/'+r['file']+'/'+str(r['offset'])).encode()).digest())
 for spec in order:
  key=(spec['file'],spec['record'])
  if key in occupied:
   declined.append(dict(file=spec['file'],offset=spec['offset'],reason='One swarm per ENE record'));continue
  if spec['native_tracking_records']+perfile[spec['file']]>=255:
   declined.append(dict(file=spec['file'],offset=spec['offset'],reason='Native tracking row limit reached'));continue
  if budget+spec['initial_budget']>MAX_STAGE_BUDGET:
   declined.append(dict(file=spec['file'],offset=spec['offset'],reason='Finite swarm stage budget reached'));continue
  target=weighted_enemy(seed,stage,'finite-swarm/'+spec['file']+'/'+str(spec['offset']),sorted(set(pool)|{10}),weights)
  if target!=10:continue
  chosen.append(dict(spec));occupied.add(key);budget+=spec['initial_budget'];perfile[spec['file']]+=1
 return sorted(chosen,key=lambda r:(r['file'],r['offset'])),declined

def apply_selection(stage,original,updated,selected,edits,enemylog):
 """Merge the overlay into one source-relative edit, retaining ordinary selector maps."""
 for spec in selected:
  name=spec['file'];p=spec['offset'];before=original[name][p:p+1];body=bytearray(updated[name])
  old=next((r for r in edits if (r['stage'],r['file'],r['offset'])==(stage,name,p)),None)
  if old:
   if old['kind']!='enemy_type' or old['before']!=before.hex():raise ValueError('Swarm overlay overlaps another feature')
   edits.remove(old)
  edits.append(dict(stage=stage,file=name,offset=p,before=before.hex(),after='0a',kind='mosquito_type'))
  log=next((r for r in enemylog if (r['stage'],r['file'],r['offset'])==(stage,name,p)),None)
  if log is None:raise ValueError('Swarm replacement requires an audited base enemy mapping')
  log['base_enemy']=log['enemy'];log['enemy']=10;log['finite_swarm_budget']=spec['initial_budget']
  body[p]=10;updated[name]=bytes(body)
 return updated

def schedule(seed,stock,stages,enemylog,settings,selectors):
 """Recompute a deterministic global selection, including the optional minimum."""
 from mixed_boss_catalog import payloads
 from opening_enemies import STAGES,TARGETS
 from scx_manager_chain_adapter import MANAGER_TYPES
 enabled=settings['include_mosquito_experimental'] and settings['enemy_percentages']['Mosquito / swarm']>0
 reports=[];selected=[]
 if not enabled:return dict(format=1,enabled=False,selected=[],stages=[],minimum_requested=False,minimum_applied=False,gameplay_verified=False)
 logs={(r['stage'],r['file'],r['offset']):r for r in enemylog}
 candidates=[]
 for row in stages:
  stage=row['stage']
  if not any(r['stage']==stage for r in enemylog):continue
  files=payloads(stock,stage);report=eligibility(stage,row,files,selectors)
  eligible=[r for r in report['eligible'] if (stage,r['file'],r['offset']) in logs]
  report['eligible']=eligible
  pool=TARGETS if stage in STAGES else {MANAGER_TYPES[h] for n,b in files.items() if n.endswith('.scx') for _,h in native_calls(b) if h in MANAGER_TYPES}&{s['original_type'] for s in row['slots']}&REGULAR_TYPES
  chosen,declined=select(seed,stage,eligible,settings['enemy_percentages'],pool)
  report['declined']=declined;reports.append(report)
  selected.extend(dict(r,stage=stage) for r in chosen)
  candidates.extend(dict(r,stage=stage) for r in eligible)
 minimum=settings['ensure_mosquito_replacements'];forced=False
 if minimum and not selected:
  if not candidates:raise ValueError('Mosquito minimum requested, but no eligible finite-swarm group exists. No unsafe fallback was applied.')
  # Prefer a campaign pool with a single ENE layout over opening/demo alternatives.
  ranked=sorted(candidates,key=lambda r:(r['stage'] in STAGES,hashlib.sha256((str(seed)+'\0minimum-finite-swarm\0'+r['stage']+'/'+r['file']+'/'+str(r['offset'])).encode()).digest()))
  selected=[ranked[0]];forced=True
 selected.sort(key=lambda r:(r['stage'],r['file'],r['offset']))
 if len(selected)>64:raise ValueError('Finite swarm runtime rule limit exceeded')
 for report in reports:report['selected_slots']=sum(r['stage']==report['stage'] for r in selected)
 return dict(format=1,enabled=True,selected=selected,stages=reports,minimum_requested=minimum,minimum_applied=forced,
  max_new_particles_per_stage=MAX_STAGE_BUDGET,max_particles_per_group=MAX_AUTHORED_COUNT*6,
  original_native_particle_capacity_preserved=True,native_swarms_preserved=True,gameplay_verified=False)

def helpers(manifest):
 return {'FiniteMosquitoAdapter.exe'} if manifest.get('mosquito_replacements',{}).get('selected') else set()
