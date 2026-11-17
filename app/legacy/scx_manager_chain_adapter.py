import portable_paths as _portable
"""Append a narrowly scoped manager-init procedure without moving original SCX bytes.
Development adapter only. Archive integration and gameplay are not validated.
"""
import struct,hashlib
from scx_bytecode import instructions,LENGTHS
from scx_call_arguments import call_arguments
MANAGER_TYPES={0x869acfd7:40,0xdffe6d2f:40,0x5525676a:32,0xffff90db:32,0xf69f7524:31,0xffff9c3f:31,0x228def80:41,0x3beb9bf3:41,0xd1efc2e5:43,0xffff31a9:43,0x7d6e9d45:42,0x17fa9160:42}
MANAGER_HASHES=set(MANAGER_TYPES)
def append_manager_chain(data,call_offset,expected_hash,additional_hashes):
 original=bytes(data);ins={p:(op,raw) for p,op,raw in instructions(original)}
 if call_offset not in ins or ins[call_offset][0]!=0x88:raise ValueError('Expected native call')
 if struct.unpack_from('<I',original,call_offset+1)[0]!=expected_hash:raise ValueError('Source hash mismatch')
 hashes=[expected_hash,*additional_hashes]
 if any(h not in MANAGER_HASHES for h in hashes):raise ValueError('Unverified manager command')
 if len({MANAGER_TYPES[h] for h in hashes})!=len(hashes):raise ValueError('Duplicate manager type')
 args=call_arguments(original,call_offset)
 if len(args)!=2 or args[0]['kind']!=0xdd or args[1]['kind']!=0xc0 or args[1]['value']!=6:
  raise ValueError('Only the verified n-option capacity6 frame is supported')
 frame=original[call_offset-10:call_offset]
 if frame!=bytes.fromhex('dd80b0c0060000008402'):raise ValueError('Nonstandard manager frame')
 # Native preprocessor stops at8e; this appended procedure has no declarations
 # or string/data pointers. Interpreter87 and88 resolve offsets/hashes at runtime.
 target=len(original);tail=b''.join(frame+b'\x88'+struct.pack('<I',h) for h in hashes)+b'\x89'
 patched=bytearray(original);patched[call_offset:call_offset+5]=b'\x87'+struct.pack('<I',target);patched.extend(tail)
 assert patched[:call_offset]==original[:call_offset]
 assert patched[call_offset+5:len(original)]==original[call_offset+5:]
 return bytes(patched),dict(source_sha256=hashlib.sha256(original).hexdigest(),source_call=call_offset,original_hash=f'{expected_hash:08x}',procedure_entry=target,procedure_end=len(patched),commands=[f'{h:08x}' for h in hashes],source_offsets_preserved=True,original_data_preserved=True,preprocessor_declarations_added=False,gameplay_verified=False,archive_integrated=False)
def appended_instructions(data,entry,end):
 p=entry
 while p<end:
  op=data[p];n=LENGTHS.get(op,1)
  if p+n>end:raise ValueError('Truncated appended instruction')
  yield p,op,data[p:p+n];p+=n
 if p!=end:raise ValueError('Invalid procedure range')
