import portable_paths as _portable
"""Prepare supplemental Raptor pools after ordinary enemy hash replacements.

Ba01 has three independent common-manager branches. Branch-local checks are
required because a Raptor declaration elsewhere in the script is insufficient.
"""
import struct
from scx_bytecode import native_calls
from scx_manager_chain_adapter import appended_instructions,MANAGER_TYPES
from scx_respawn_pool_adapter import append_respawn_pool

def prepare_respawn_dependency(scripts,existing_adapters):
 capacity=0;types=set()
 for key,b in scripts.items():
  calls=native_calls(b)
  if key in existing_adapters:
   a=existing_adapters[key];calls.extend((q,int.from_bytes(raw[1:],'little')) for q,op,raw in appended_instructions(b,a['procedure_entry'],a['procedure_end']) if op==0x88)
  for q,h in calls:
   t=MANAGER_TYPES.get(h)
   if t is None:continue
   types.add(t)
   if t in (32,43):
    frame=b[q-10:q]
    if len(frame)!=10 or frame[:4]!=b'\xdd\x80\xb0\xc0' or frame[-2:]!=b'\x84\x02':raise ValueError('Unresolved respawn-source manager capacity: '+key+' '+hex(q))
    n=struct.unpack_from('<I',frame,4)[0]
    if n not in range(1,13):raise ValueError('Unverified respawn-source capacity')
    capacity+=n
 if not types & {32,43}:return {},{}
 capacity=max(6,capacity)
 if 'ef1d2ddf.scx' in scripts:
  if any(h in MANAGER_TYPES for other,body in scripts.items() if other!='ef1d2ddf.scx' for _,h in native_calls(body)):raise ValueError('ba01 pool topology changed: unexpected manager script')
  key='ef1d2ddf.scx';b=scripts[key]
  calls=dict(native_calls(b))
  sites=(3799,3814,4733,6299)
  if any(q not in calls or calls[q] not in MANAGER_TYPES for q in sites):raise ValueError('ba01 pool topology changed')
  typed={q:MANAGER_TYPES[calls[q]] for q in sites}
  if len(set(typed[q] for q in sites[1:]))!=1 or typed[3799]==typed[3814]:
   raise ValueError('ba01 pool branch type mapping changed')
  if {q for q,h in calls.items() if h in MANAGER_TYPES}!=set(sites):
   raise ValueError('ba01 unclassified manager site')
  targets=[]
  if 40 not in (typed[3799],typed[3814]):
   targets.extend([q for q in (3799,3814) if typed[q] in (32,43)][:1])
  targets.extend(q for q in (4733,6299) if typed[q] in (32,43))
  if not targets:return {},{}
  adapters=[]
  for q in targets:
   # These four source sites were checked against the immutable archive and
   # enumerated as three distinct common-manager branches.
   b,adapter=append_respawn_pool(b,q,calls[q],capacity,allow_existing_raptor=True)
   adapters.append(adapter)
  adapters[0]['additional_procedures']=adapters[1:]
  return {key:b},{key:adapters[0]}
 if 40 in types:return {},{}
 for key,b in scripts.items():
  for q,h in native_calls(b):
   if h not in MANAGER_TYPES:continue
   try:patched,adapter=append_respawn_pool(b,q,h,capacity)
   except ValueError:continue
   return {key:patched},{key:adapter}
 raise ValueError('No verified manager frame for supplementary Raptor pool')
