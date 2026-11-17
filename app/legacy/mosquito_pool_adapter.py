import portable_paths as _portable
"""Swarm-specific SCX setup and ENE bounds; archive integration is separate."""
import struct
from scx_bytecode import instructions
from scx_call_arguments import call_arguments
from scx_manager_chain_adapter import MANAGER_TYPES

MOSQUITO_TYPE = 10
MOSQUITO_COMMAND = 0x1ffa5693

def validate_tracking_records(data):
    if len(data) < 32:
        raise ValueError('Truncated ENE header')
    count = struct.unpack_from('<H', data, 2)[0]
    start = struct.unpack_from('<I', data, 4)[0]
    if start < 32 or start + count*112 > len(data):
        raise ValueError('Invalid ENE record bounds')
    rows = []
    for record in range(count):
        matches = [slot for slot in range(4)
                   if data[start+record*112+48+slot*8] == MOSQUITO_TYPE]
        # Allocation counts one per record; population visits every matching
        # slot, including zero-count slots. Two matches overflow native storage.
        if len(matches) > 1:
            raise ValueError('Multiple Mosquito slots exceed native tracking allocation')
        if matches:
            slot = matches[0]
            amount = data[start+record*112+49+slot*8]
            rows.append(dict(record=record, slot=slot, count=amount,
                             native_budget=amount*6 if amount else 400))
    if len(rows) > 255:
        raise ValueError('Mosquito tracking count exceeds native byte capacity')
    return rows

def setup_frame(profile):
    """Emit six literal arguments from an audited original setup profile."""
    if len(profile) != 6 or any(type(v) is not int for v in profile):
        raise ValueError('Six integer swarm setup arguments required')
    if not 1 <= profile[0] <= 255 or any(not 0 <= v <= 255 for v in profile[1:]):
        raise ValueError('Swarm setup exceeds reviewed capacity or byte parameters')
    frame = b''.join(b'\x80\xb0\xc0'+struct.pack('<I', v) for v in profile)
    return frame+b'\x84\x06\x88'+struct.pack('<I', MOSQUITO_COMMAND)

def normal_setup_frame(command, capacity=6):
    if command not in MANAGER_TYPES:
        raise ValueError('Unknown normal enemy factory')
    if type(capacity) is not int or not 1 <= capacity <= 12:
        raise ValueError('Unverified normal pool capacity')
    return b'\xdd\x80\xb0\xc0'+struct.pack('<I',capacity)+b'\x84\x02\x88'+struct.pack('<I',command)

def replace_setup(data, offset, expected_command, replacement_frame):
    """Consume the original frame, then invoke a differently shaped factory.

    The registered fffff75a no-op uses native dispatch's normal argument cleanup,
    as in the existing boss adapter. Original instruction/data offsets stay fixed.
    """
    original = bytes(data)
    if expected_command not in MANAGER_TYPES and expected_command != MOSQUITO_COMMAND:
        raise ValueError('Expected an audited enemy setup command')
    ins = {p:(op, raw) for p, op, raw in instructions(original)}
    if ins.get(offset) != (0x88, b'\x88'+struct.pack('<I', expected_command)):
        raise ValueError('Unexpected source setup call')
    # Some original normal factories inherit a frame through a procedure call.
    # Keep that dispatch intact via the no-op rather than guessing its arguments.
    candidate = replacement_frame+b'\x8e'
    calls = [(p, raw) for p, op, raw in instructions(candidate) if op == 0x88]
    if len(calls) != 1:
        raise ValueError('A single enemy factory frame is required')
    target = int.from_bytes(calls[0][1][1:], 'little')
    args = call_arguments(candidate, calls[0][0])
    if target == MOSQUITO_COMMAND:
        if any(a['kind'] != 0xc0 for a in args) or setup_frame([a['value'] for a in args]) != replacement_frame:
            raise ValueError('Unexpected swarm setup instructions')
    elif target in MANAGER_TYPES:
        if len(args) != 2 or args[0]['kind'] != 0xdd or args[1]['kind'] != 0xc0 or normal_setup_frame(target,args[1]['value']) != replacement_frame:
            raise ValueError('Unexpected normal pool setup instructions')
    else:
        raise ValueError('Unverified destination factory')
    entry = len(original)
    tail = b'\x88\x5a\xf7\xff\xff'+replacement_frame+b'\x89'
    result = bytearray(original)
    result[offset:offset+5] = b'\x87'+struct.pack('<I', entry)
    result.extend(tail)
    return bytes(result), dict(source_call=offset, procedure_entry=entry,
        procedure_end=len(result), original_offsets_preserved=True,
        original_frame_consumed=True, destination_command=f'{target:08x}', gameplay_verified=False)
