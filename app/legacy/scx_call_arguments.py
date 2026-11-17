import portable_paths as _portable
"""Decode native argument provenance without executing SCX.
Computed values remain opaque. Cross-procedure/control-flow frames are rejected.
Stack effects follow the decompiled FUN14553ca70 interpreter.
"""
import struct
from scx_bytecode import instructions
class UnresolvedArguments(ValueError):pass
def call_arguments(data,call_offset):
 ins=list(instructions(data));index=next((i for i,x in enumerate(ins) if x[0]==call_offset),None)
 if index is None or ins[index][1]!=0x88:raise UnresolvedArguments('Not a native call')
 if index==0 or ins[index-1][1] not in (0x83,0x84):raise UnresolvedArguments('Non-adjacent argument frame')
 argc=1 if ins[index-1][1]==0x83 else ins[index-1][2][1]
 def opaque(op):return dict(kind=op,value=None,offset=None)
 def expression(cursor,depth=0):
  if cursor<0 or depth>100:raise UnresolvedArguments('Expression limit')
  p,op,raw=ins[cursor]
  if cursor>=2 and op in (0xc0,0xc1,0xc2,0xc3,0xc5) and ins[cursor-1][1]==0xb0 and ins[cursor-2][1]==0x80:
   return dict(kind=op,value=struct.unpack_from('<I',raw,1)[0],offset=p+1),cursor-3
  if cursor>=1 and op in (0xb1,0xb2,0xb3):
   prev=ins[cursor-1][1]
   if prev==0x80:return dict(kind=op,value=None,offset=None,reference=int.from_bytes(raw[1:],'little'),read_offset=p),cursor-2
   if prev==0x8a:
    _,end=expression(cursor-2,depth+1);return opaque(op),end
  if op==0x88:
   h=int.from_bytes(raw[1:],'little')
   # These two handlers consume their frame and overwrite the prior result slot.
   if h not in (0xb7f43ef4,0x79b9e779) or cursor<1 or ins[cursor-1][1] not in (0x83,0x84):
    raise UnresolvedArguments('Unverified native expression result')
   count=1 if ins[cursor-1][1]==0x83 else ins[cursor-1][2][1];end=cursor-2
   for _ in range(count):_,end=expression(end,depth+1)
   _,end=expression(end,depth+1)
   return opaque(0xc1),end
  if op==0x81:return dict(kind=0xc0,value=0,offset=None),cursor-1
  if 0xd0<=op<=0xe9 or 0xf0<=op<=0xf7:return opaque(op),cursor-1
  if op in (0x90,0x91):
   _,end=expression(cursor-1,depth+1);return opaque(op),end
  if 0x92<=op<=0x9b or 0xa0<=op<=0xa7:
   _,end=expression(cursor-1,depth+1);_,end=expression(end,depth+1);return opaque(op),end
  raise UnresolvedArguments('Unsupported expression at '+hex(p)+' opcode '+hex(op))
 cursor=index-2;args=[]
 for _ in range(argc):
  arg,cursor=expression(cursor);args.append(arg)
 args.reverse();return args
def literal_arguments(data,call_offset):
 args=call_arguments(data,call_offset)
 if any(x['value'] is None and x['kind'] not in range(0xd0,0xea) for x in args):
  raise UnresolvedArguments('Computed native argument')
 return args
