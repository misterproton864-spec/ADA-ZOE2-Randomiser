import portable_paths as _portable
"""BAHRAM ba01: native secondary actors retained; self-contained regular pools."""
import hashlib,struct
from opening_enemies import asset_set
from mixed_boss_catalog import payloads
from scx_bytecode import native_calls
from scx_manager_chain_adapter import MANAGER_TYPES
from actor_reference_adapter import selector_arguments,ENE_TO_EXTERNAL
from randomizer_settings import weighted_enemy,enemy_level
from ene_pool_storage import extend_pool_storage

STAGE='ba01';SCRIPT='ef1d2ddf.scx';SITES=(3814,4733,6299)

def prepare(seed,stock,row,weights,levels,selectors,stage=STAGE,script=SCRIPT,sites=SITES,force_different=False):
 original=payloads(stock,stage);files=original.copy();edits=[];logs=[]
 groups=sorted({s['script_group_id'] for s in row['slots'] if s['original_type']==40})
 pool=[41,42] if force_different else [40,41,42]
 assignments={g:weighted_enemy(seed,stage,'ship-group/'+str(g),pool,weights) for g in groups}
 required={t for t in assignments.values() if t!=40};assets={};donors={};commands={};aliases={'main':{},'small':{}}
 for typ in sorted(required):
  selected,donor,command=asset_set(stock,typ);assets.update(selected);commands[typ]=command;donors[typ]=donor
  for label in aliases:
   for n in selected:
    if n.endswith('.tex'):
      for suffix in ('.dat','.tbl'):aliases[label]['@'+stage+'_'+n[:8]+suffix]='@'+donor+'_'+n[:8]+suffix
 def edit(name,p,before,after,kind):
  if before!=after:edits.append(dict(stage=stage,file=name,offset=p,before=before.hex(),after=after.hex(),kind=kind))
 for slot in row['slots']:
  if slot['original_type'] not in (32,40):continue
  name=slot['file'];p=slot['offset'];b=bytearray(files[name]);typ=slot['original_type']
  if b[p:p+3]!=bytes((typ,slot['count'],slot['level'])):raise ValueError('Ship ENE baseline differs')
  target=assignments[slot['script_group_id']] if typ==40 else typ
  level=enemy_level(seed,stage,name+'/'+str(p),slot['level'],levels)
  edit(name,p,bytes((typ,)),bytes((target,)),'enemy_type');edit(name,p+2,bytes((slot['level'],)),bytes((level,)),'enemy_level')
  b[p]=target;b[p+2]=level;files[name]=bytes(b)
  logs.append(dict(stage=stage,file=name,record=slot['record'],slot=slot['slot'],offset=p,group=slot['script_group_id'],enemy=target,original_type=typ,count=slot['count'],original_level=slot['level'],level=level,native_pool=[32,40],replacement_pool=[40,41,42],protected_identity=typ==32))
 source=original[script];script_body=bytearray(source);selector_edits=[];adapters=[]
 for p,h in native_calls(source):
  if h not in selectors:continue
  for item in selector_arguments(source,p,h):
   if item['type'] not in (1,40):continue
   group=item['encounter_id']
   if group not in assignments:raise ValueError('Ship selector group is not authored')
   target=assignments[group];value=ENE_TO_EXTERNAL[target] if item['type']==1 else target;q=item['value_offset']
   after=struct.pack('<I',value);edit(script,q,source[q:q+4],after,'enemy_selector');script_body[q:q+4]=after
   selector_edits.append(dict(offset=q,group=group,source=item['type'],target=value,ordinal=item['ordinal']))
 for p in sites:
  if source[p:p+5]!=bytes.fromhex('88d7cf9a86') or source[p-10:p]!=bytes.fromhex('dd80b0c0030000008402'):raise ValueError('Ship branch initialization differs')
  # Original Raptor factory consumes the pending argument frame unchanged.
  # Preserve it for the native Mummyhead death/respawn path; add only the two
  # standalone destination classes, with their own complete argument frames.
  if required:
   entry=len(script_body);tail=source[p:p+5]
   for typ in sorted(required):tail+=source[p-10:p]+b'\x88'+struct.pack('<I',commands[typ])
   tail+=b'\x89';script_body[p:p+5]=b'\x87'+struct.pack('<I',entry);script_body.extend(tail)
   adapters.append(dict(source_call=p,entry=entry,end=len(script_body),capacity=3,types=[40]+sorted(required)))
 files[script]=bytes(script_body)+bytes((-len(script_body))%16) if required else bytes(script_body)
 storage=[]
 if required:
  for name,data in list(files.items()):
   if name.endswith('.ene'):
    files[name],report=extend_pool_storage(data,3);storage.append(dict(file=name,**report))
 imported={n:b for n,b in assets.items() if n not in original};files.update(imported)
 report=dict(stage=stage,group_mapping=assignments,donors=donors,selector_edits=selector_edits,adapters=adapters,storage=storage,
  files={n:hashlib.sha256(b).hexdigest() for n,b in imported.items()},native_secondary_actor_stream_preserved=True,
  native_mummyhead_identity_preserved=True,gameplay_verified=False,softlock_cause_proven=False)
 return files,edits,logs,report,aliases
