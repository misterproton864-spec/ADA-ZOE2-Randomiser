import portable_paths as _portable
"""Read SCX instruction boundaries using Zoe2Mars.exe FUN1455417e0's scan.
No script execution or mutation. Opcode88 native calls need no adjacent argc opcode:
control can return from a preceding opcode87 procedure with its arguments set.
"""
import struct
LENGTHS={0x84:2,0x85:5,0x86:5,0x87:5,0x88:5,0xb1:5,0xb2:5,0xb3:5,0xc0:5,0xc1:5,0xc2:5,0xc3:5,0xc5:5,0x8c:6,0x8d:8}
def instructions(data):
 p=0
 while p<len(data):
  op=data[p]
  if op==0x8e:
   yield p,op,data[p:p+1]
   return
  n=LENGTHS.get(op,1)
  if p+n>len(data):raise ValueError('Truncated SCX instruction at '+hex(p))
  yield p,op,data[p:p+n]
  p+=n
 raise ValueError('SCX lacks instruction/data boundary opcode8e')
def native_calls(data):
 return [(p,struct.unpack_from('<I',raw,1)[0]) for p,op,raw in instructions(data) if op==0x88]
def declarations(data):
 return [(p,raw[1],struct.unpack_from('<I',raw,2)[0],struct.unpack_from('<H',raw,6)[0] if op==0x8d else 0) for p,op,raw in instructions(data) if op in [0x8c,0x8d]]
