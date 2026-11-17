import portable_paths as _portable
"""Remap both species and ordinal when weighted types share a native pool."""
import struct
from actor_reference_adapter import EXTERNAL_TO_ENE,ENE_TO_EXTERNAL,OPTION_TARGET_COMMANDS
from scx_call_arguments import call_arguments,UnresolvedArguments

def triples(data,offset,command):
 args=call_arguments(data,offset)
 if command in OPTION_TARGET_COMMANDS:
  result=[]
  for i,a in enumerate(args):
   if a['kind']==0xd4:
    if i+3>=len(args):raise UnresolvedArguments('Truncated actor option')
    result.append(args[i+1:i+4])
  return result
 if len(args)<3:raise UnresolvedArguments('Truncated actor selector')
 return [args[:3]]

def ordinal(slots,group,source,number,mapping):
 variants={}
 for s in slots:
  if s['script_group_id']==group and s['original_type'] in ENE_TO_EXTERNAL:
   variants.setdefault(s['file'],[]).append(s)
 answers=set()
 for entries in variants.values():
  old=[]
  for s in sorted(entries,key=lambda r:(r['record'],r['slot'])):old.extend([s['original_type']]*s['count'])
  matches=[i for i,t in enumerate(old) if t==source]
  if number>=len(matches):continue
  index=matches[number];target=mapping.get(source,source)
  answers.add(sum(mapping.get(t,t)==target for t in old[:index]))
 if not answers:raise UnresolvedArguments('Selector original actor absent from authored group '+str(group))
 if len(answers)!=1:raise UnresolvedArguments('Alternate ENE layouts disagree on mapped actor ordinal')
 return answers.pop()

def patch(data,sites,mapping,slots):
 source=bytes(data);result=bytearray(source);edits=[]
 for site in sites:
  for group_arg,type_arg,ordinal_arg in triples(source,site['offset'],site['command']):
   if type_arg['kind']!=0xc0 or type_arg['offset'] is None:raise UnresolvedArguments('Computed enemy selector type')
   old=type_arg['value'];typ=EXTERNAL_TO_ENE.get(old,old)
   if typ not in mapping:continue
   target=mapping[typ];new=ENE_TO_EXTERNAL[target] if old in EXTERNAL_TO_ENE else target
   # A merged destination changes the ordinal even when this source's own
   # type happens to remain unchanged (e.g. Raptor -> Mummyhead beside one).
   merged=any(t!=typ and mapping.get(t,t)==target for t in {s['original_type'] for s in slots if s['original_type'] in ENE_TO_EXTERNAL})
   if merged:
    if group_arg['kind']!=0xc0 or ordinal_arg['kind']!=0xc0 or ordinal_arg['offset'] is None:raise UnresolvedArguments('Merged pool selector requires literal group and ordinal')
    number=ordinal(slots,group_arg['value'],typ,ordinal_arg['value'],mapping)
   else:number=ordinal_arg['value']
   for arg,value,kind in ((type_arg,new,'enemy_selector'),(ordinal_arg,number,'enemy_selector_ordinal')):
    if value==arg['value']:continue
    p=arg['offset'];before=source[p:p+4];after=struct.pack('<I',value)
    if result[p:p+4] not in (before,after):raise UnresolvedArguments('Overlapping selector rewrites disagree')
    result[p:p+4]=after
    if not any(e['offset']==p for e in edits):edits.append(dict(offset=p,before=before.hex(),after=after.hex(),kind=kind,group=group_arg['value'],source_type=typ,original_ordinal=ordinal_arg['value'],target_type=target,target_ordinal=number))
 return bytes(result),edits
