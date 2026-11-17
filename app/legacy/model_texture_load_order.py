import portable_paths as _portable
"""Register imported texture libraries before their first dependent MDZ."""
import struct

TEX = 0x1e5452
MDZ = 0x3b12fb

def order_model_textures(entries, decoded):
    entries = [list(e) for e in entries]
    offsets = sorted(e[2] for e in entries) + [len(decoded)]
    assert len(set(offsets)) == len(offsets)
    ends = dict(zip(offsets, offsets[1:]))
    blobs = {(e[0], e[1]): bytes(decoded[e[2]:ends[e[2]]]) for e in entries}
    assert len(blobs) == len(entries)
    ordered = []; emitted = set(); moves = []
    lookup = {(e[0], e[1]): e for e in entries}
    positions = {key: i for i, key in enumerate(lookup)}
    for e in entries:
        key = (e[0], e[1]); data = blobs[key]
        if e[0] == MDZ and len(data) >= 36 and data[0] & 0x10:
            dependency = (TEX, struct.unpack_from('<I', data, 32)[0])
            if dependency in lookup and dependency not in emitted:
                if positions[dependency] > positions[key]:
                    moves.append(dict(model=f'{e[1]:08x}.mdz',texture=f'{dependency[1]:08x}.tex'))
                ordered.append(lookup[dependency]); emitted.add(dependency)
        if key not in emitted:
            ordered.append(e); emitted.add(key)
    if not moves:
        return entries, bytearray(decoded), []
    result = bytearray()
    for e in ordered:
        key = (e[0], e[1]); e[2] = len(result); result.extend(blobs[key])
    assert len(result) == len(decoded)
    assert {(e[0],e[1]) for e in ordered} == set(blobs)
    return ordered, result, moves
