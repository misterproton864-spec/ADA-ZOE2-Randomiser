import portable_paths as _portable
"""Experimental supplementary Raptor pool adapter. No live installation.

Preserves original manager arguments and all original offsets. Runtime entry
coverage, capacity and gameplay require verification before installation.
"""
import struct,hashlib
from scx_bytecode import instructions,native_calls
from scx_call_arguments import call_arguments
from scx_manager_chain_adapter import MANAGER_TYPES
RAPTOR=0x869acfd7
def append_respawn_pool(data,call_offset,expected_hash,capacity,allow_existing_raptor=False):
 original=bytes(data);ins={p:(op,raw) for p,op,raw in instructions(original)}
 if expected_hash not in MANAGER_TYPES or MANAGER_TYPES[expected_hash]==40:raise ValueError('Expected non-Raptor manager')
 if call_offset not in ins or ins[call_offset][0]!=0x88:raise ValueError('Expected native call')
 if int.from_bytes(ins[call_offset][1][1:],'little')!=expected_hash:raise ValueError('Source manager hash mismatch')
 if not allow_existing_raptor and any(MANAGER_TYPES.get(h)==40 for _,h in native_calls(original)):raise ValueError('Existing Raptor manager in source script')
 args=call_arguments(original,call_offset)
 if len(args)!=2 or args[0]['kind']!=0xdd or args[1]['kind']!=0xc0 or args[1]['value'] not in range(1,13):raise ValueError('Unverified original capacity frame')
 n=args[1]['value'];frame=original[call_offset-10:call_offset]
 if frame!=b'\xdd\x80\xb0\xc0'+struct.pack('<I',n)+b'\x84\x02':raise ValueError('Nonstandard manager frame')
 if type(capacity) is not int or not 1<=capacity<=64:raise ValueError('Unsupported dependency capacity')
 dependency=b'\xdd\x80\xb0\xc0'+struct.pack('<I',capacity)+b'\x84\x02\x88'+struct.pack('<I',RAPTOR)
 entry=len(original);tail=frame+b'\x88'+struct.pack('<I',expected_hash)+dependency+b'\x89'
 patched=bytearray(original);patched[call_offset:call_offset+5]=b'\x87'+struct.pack('<I',entry);patched.extend(tail)
 assert patched[:call_offset]==original[:call_offset] and patched[call_offset+5:len(original)]==original[call_offset+5:]
 return bytes(patched),dict(source_sha256=hashlib.sha256(original).hexdigest(),source_call=call_offset,original_hash=f'{expected_hash:08x}',original_capacity=n,dependency_hash=f'{RAPTOR:08x}',dependency_capacity=capacity,procedure_entry=entry,procedure_end=len(patched),original_offsets_preserved=True,original_arguments_preserved=True,source_flow_coverage_verified=False,dependency_capacity_gameplay_verified=False,archive_integrated=False,installed=False,gameplay_verified=False)
