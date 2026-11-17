import portable_paths as _portable
"""Map validated SCX enemy selectors alongside ENE type replacements."""
import struct,hashlib
from scx_call_arguments import call_arguments,UnresolvedArguments
EXTERNAL_TO_ENE={1:40,2:32,3:41,4:43,5:42,6:31}
ENE_TO_EXTERNAL={v:k for k,v in EXTERNAL_TO_ENE.items()}
OPTION_TARGET_COMMANDS={0xfffdc707,0xffffd372}
def selector_arguments(data,offset,command,binding=None):
 args=call_arguments(data,offset)
 if command in OPTION_TARGET_COMMANDS:
  markers=[i for i,arg in enumerate(args) if arg['kind']==0xd4]
  selected=[]
  for i in markers:
   if i+3>=len(args):raise UnresolvedArguments('Truncated actor option')
   selected.append(args[i+1:i+4])
 else:
  if len(args)<3:raise UnresolvedArguments('Truncated actor selector')
  selected=[args[:3]]
 result=[]
 for triple in selected:
  item=triple[1]
  if item['kind']==0xb1 and binding and item.get('reference')==binding['variable'] and item.get('read_offset') in binding['read_offsets']:
   if not binding['procedure_entry']<=offset<binding['procedure_end']:raise UnresolvedArguments('Bound variable used outside verified procedure')
   value=binding['source_value'];value_offset=None
  else:
   if item['kind']!=0xc0 or item['offset'] is None:raise UnresolvedArguments('Computed enemy selector type')
   value=item['value'];value_offset=item['offset']
  result.append(dict(type=value,value_offset=value_offset,encounter_id=triple[0]['value'],ordinal=triple[2]['value']))
 return result
def patch_references(data,sites,mapping,binding=None):
 original=bytes(data);patched=bytearray(data);edits=[]
 if binding:
  if hashlib.sha256(original).hexdigest()!=binding['source_sha256']:raise UnresolvedArguments('Indirect binding source hash mismatch')
  old=binding['source_value'];t=EXTERNAL_TO_ENE.get(old,old)
  if t in mapping and mapping[t]!=t:
   new=ENE_TO_EXTERNAL[mapping[t]] if old in EXTERNAL_TO_ENE else mapping[t]
   for caller in binding['callers']:
    p=caller['value_offset'];assert original[p-1]==0xc0 and struct.unpack_from('<I',original,p)[0]==old
    struct.pack_into('<I',patched,p,new)
    edits.append(dict(offset=p,original=old,replacement=new,command='verified procedure caller',encounter_id=None,ordinal=None))
 for site in sites:
  for item in selector_arguments(original,site['offset'],site['command'],binding):
   old=item['type'];t=EXTERNAL_TO_ENE.get(old,old)
   if t not in mapping or mapping[t]==t:continue
   new=ENE_TO_EXTERNAL[mapping[t]] if old in EXTERNAL_TO_ENE else mapping[t]
   p=item['value_offset']
   if p is None:
    if not binding:raise UnresolvedArguments('Indirect type lacks binding')
    continue
   assert struct.unpack_from('<I',original,p)[0]==old
   struct.pack_into('<I',patched,p,new)
   edits.append(dict(offset=p,original=old,replacement=new,command=f"{site['command']:08x}",encounter_id=item['encounter_id'],ordinal=item['ordinal']))
 allowed={p for e in edits for p in range(e['offset'],e['offset']+4)}
 assert all(i in allowed for i,(a,b) in enumerate(zip(original,patched)) if a!=b)
 return patched,edits
