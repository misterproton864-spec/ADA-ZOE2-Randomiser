import portable_paths as _portable
"""Restore regular wave shuffling in scripted missions; retain native objectives."""
import hashlib,json,struct
from archive_tools import L
from mixed_boss_catalog import payloads
from scx_bytecode import native_calls
from scx_manager_chain_adapter import MANAGER_TYPES
from actor_reference_adapter import patch_references
from ene_pool_storage import extend_pool_storage
from mosquito_pool_adapter import normal_setup_frame,validate_tracking_records

STAGES=('vc02','vc03','fc01','mf01','mf01c','mf02','am01f')
COMMON=0xffffedb9;NOOP=0xfffff75a

def restore(seed,archive,updates,aliases,weights=None,levels=False):
 from randomizer_settings import enemy_weights,weighted_enemy,enemy_level
 weights=enemy_weights(weights)
 plan=json.loads((L/'Full-Rerandomisation-v2/enemy-shuffle-plan.json').read_text())
 specs={r['type']:r for r in json.loads((L/'enemy-assets.json').read_text()).values()}
 selectors={int(h,16) for h in json.loads((L/'type-selector-command-catalog.json').read_text())['commands']}
 logs=[];reports=[]
 def rank(domain,k):return hashlib.sha256((seed+'\0'+domain+'\0'+str(k)).encode()).digest()
 for stage in STAGES:
  row=next(r for r in plan['stages'] if r['stage']==stage);stock=payloads(archive,stage)
  files=updates.setdefault(stage,stock.copy())
  assert all(files.get(k)==v for k,v in stock.items()),('Mission no longer native baseline',stage)
  pools={MANAGER_TYPES[h] for n,b in stock.items() if n.endswith('.scx') for p,h in native_calls(b) if h in MANAGER_TYPES}
  pools=pools-{10};pools=pools or {40,41}
  origins=sorted({r['original_type'] for r in row['slots']},key=lambda t:rank('mission-source/'+stage,t))
  mapping={t:weighted_enemy(seed,stage,'mission-source/'+str(t),pools,weights) for t in origins}
  for slot in row['slots']:
   name=slot['file'];b=bytearray(files[name]);p=slot['offset']
   assert b[p:p+3]==bytes([slot['original_type'],slot['count'],slot['level']])
   b[p]=mapping[slot['original_type']];b[p+2]=enemy_level(seed,stage,name+'/'+str(slot['record'])+'/'+str(slot['slot']),slot['level'],levels);files[name]=bytes(b)
   logs.append(dict(stage=stage,file=name,record=slot['record'],slot=slot['slot'],group=slot['script_group_id'],enemy=b[p],count=slot['count'],original_level=slot['level'],level=b[p+2]))
  storage=[];adapters=[];selector_edits=[];suppressed=[]
  for name,data in stock.items():
   if name.endswith('.ene'):
    validate_tracking_records(files[name]);files[name],r=extend_pool_storage(files[name],6);storage.append(dict(file=name,**r))
   if not name.endswith('.scx'):continue
   refs=[dict(offset=p,command=h) for p,h in native_calls(data) if h in selectors]
   patched,edits=patch_references(data,refs,mapping);b=bytearray(patched)
   selector_edits.extend(dict(file=name,**e) for e in edits)
   for p,h in native_calls(data):
    if h not in MANAGER_TYPES:continue
    b[p:p+5]=b'\x88'+struct.pack('<I',NOOP);suppressed.append(dict(file=name,offset=p,command=f'{h:08x}'))
   for p,h in native_calls(data):
    if h!=COMMON:continue
    entry=len(b);b.extend(b'\x88'+struct.pack('<I',COMMON))
    for typ in sorted(pools):b.extend(normal_setup_frame(int(specs[typ]['command'],16)))
    b.extend(b'\x80\xb0\xc5'+struct.pack('<I',p+5)+b'\x89')
    b[p:p+5]=b'\x85'+struct.pack('<I',entry-p)
    adapters.append(dict(file=name,source_call=p,procedure_entry=entry,procedure_end=len(b),pool_types=sorted(pools)))
   files[name]=bytes(b)+bytes((-len(b))%16)
  assert adapters,stage
  imported=[]
  for typ in sorted(pools):
   spec=specs[typ];donor=spec['donor'];source=payloads(archive,donor)
   names=[r['hash'] for r in spec['files']]
   names+= [n[:-4]+'.cvz' for n in names if n.endswith('.mdz') and n[:-4]+'.cvz' in source]
   for name in names:
    if name in files:continue
    files[name]=source[name];imported.append(name)
    if name.endswith('.tex'):
     for label in ('main','small'):
      for suffix in ('.dat','.tbl'):aliases[label]['@'+stage+'_'+name[:8]+suffix]='@'+donor+'_'+name[:8]+suffix
  reports.append(dict(stage=stage,pools=sorted(pools),mapping=mapping,adapters=adapters,selector_edits=selector_edits,
   suppressed_pool_setups=suppressed,storage=storage,imports=imported,counts_and_levels_preserved=not levels,counts_preserved=True,levels_randomised=levels,
   native_scripted_spider_retained=True,objective_callbacks_preserved=True,gameplay_verified=False))
 return logs,reports
