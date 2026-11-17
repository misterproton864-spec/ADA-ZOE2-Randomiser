import portable_paths as _portable
"""Remove vc01's two perimeter hazard groups, preserving floor/exit geometry.

HZT nodes 08f79722 (energy field, type 8) and c8f5929b (type 4) each
own four vertical quads. Native 146cff970 creates their actors from flags
at +0x36; 146d05970/146dbb5c0 create effects from the +0x3c quad count.
Clearing the actor type and setting native disabled bit 0x8000 prevents
creation and later script reactivation. Counts, polygon storage and the
HZ2 spatial index retain their original addresses and numbering.
"""
import hashlib
import struct

STAGE='vc01'
FILE='2690498c.hzt'
SOURCE_SHA='57c3d63701f913a80e1f4fbc1835c0ba25c0b0b0c0d5a95598255f7d7f681535'
GROUPS=((0x140,0x08f79722,0x18,0x11550),(0x190,0xc8f5929b,0x8014,0x113d0))

def apply(original):
    if hashlib.sha256(original).hexdigest()!=SOURCE_SHA:
        raise ValueError('Nephtis 3 perimeter source differs')
    result=bytearray(original);edits=[]
    for node,ident,flags,polygons in GROUPS:
        if (struct.unpack_from('<I',original,node+0x20)[0]!=ident
                or struct.unpack_from('<H',original,node+0x36)[0]!=flags
                or struct.unpack_from('<I',original,node+0x38)[0]!=polygons
                or struct.unpack_from('<I',original,node+0x3c)[0]!=4):
            raise ValueError('Nephtis 3 perimeter node differs')
        for offset,value in ((node+0x36,0x8010),):
            before=original[offset:offset+2];after=struct.pack('<H',value)
            result[offset:offset+2]=after
            edits.append(dict(offset=offset,before=before.hex(),after=after.hex()))
    result=bytes(result)
    return result,dict(file=FILE,source_sha256=SOURCE_SHA,
        output_sha256=hashlib.sha256(result).hexdigest(),edits=edits,
        perimeter_groups_disabled=[f'{g[1]:08x}' for g in GROUPS],
        perimeter_quads_disabled=8,energy_effect_creation_disabled=True,
        floor_and_exit_preserved=True,spatial_index_preserved=True,gameplay_verified=False)

def verify(original,after,report):
    expected,proof=apply(original)
    if after!=expected or report!=proof:
        raise ValueError('Nephtis 3 perimeter removal differs from pinned geometry')
    return True
