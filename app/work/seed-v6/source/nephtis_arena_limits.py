import portable_paths as _portable
"""Disable pinned scripted side/ceiling clamps in vc01 and fa01 boss tests.

Native setters 145202260/145203bd0/145204630 enable the global arena
clamp at 141535930. The existing cfca814c handler is a bare RET. Keeping
the argument frames and instruction widths preserves all procedure addresses.
Static HZT geometry and floor collision are deliberately retained.
"""
import hashlib
import struct
from scx_bytecode import native_calls

STAGE='vc01'
FILE='17303f25.scx'
SOURCE_SHA='06f8f044f6febce5c5e83c6e5601804612e4de02fde14996c667b2d1056adc7c'
NOOP=0xcfca814c
SITES=((8769,0xffffefbf,'ceiling'),(8797,0xfffff885,'x sides'),(8825,0xffffc409,'z sides'))
PROFILES={STAGE:dict(file=FILE,sha256=SOURCE_SHA,sites=SITES),
 'fa01':dict(file='cd0ea7e2.scx',sha256='147a7f2e95f16af06c6a0c1ff793f316b5eff6df93587c969f69bc89013d9db2',
  sites=((9138,0xffffc409,'z sides'),(9166,0xfffff885,'x sides'),(9187,0xffffefbf,'ceiling')))}

def apply(stage,name,data,original):
    if stage not in PROFILES:return data,None
    profile=PROFILES[stage]
    if name!=profile['file'] or hashlib.sha256(original).hexdigest()!=profile['sha256']:
        raise ValueError(stage+' arena source differs')
    calls=dict(native_calls(original));result=bytearray(data);edits=[]
    for offset,command,role in profile['sites']:
        before=b'\x88'+struct.pack('<I',command)
        if calls.get(offset)!=command or original[offset:offset+5]!=before or data[offset:offset+5]!=before:
            raise ValueError(stage+' arena limit setup differs: '+role)
        after=b'\x88'+struct.pack('<I',NOOP)
        result[offset:offset+5]=after
        edits.append(dict(offset=offset,before=before.hex(),after=after.hex(),role=role))
    return bytes(result),dict(stage=stage,file=name,edits=edits,
        scripted_side_and_ceiling_limits_disabled=True,static_collision_preserved=True,
        native_clamp_flags_not_enabled=True,
        visible_energy_barriers_verified=False,gameplay_verified=False)

def verify_prefix(stage,name,original,after,report):
    """Derive the permitted edits independently of the manifest's edit list."""
    if report is None:return set()  # Older packages retain their original limits.
    if stage not in PROFILES:
        if report:raise ValueError('Arena limit change outside pinned arenas')
        return set()
    expected,proof=apply(stage,name,original,original)
    if report!=proof:raise ValueError('Arena limit report differs')
    allowed=set()
    for offset,_,_ in PROFILES[stage]['sites']:
        if after[offset:offset+5]!=expected[offset:offset+5]:
            raise ValueError(stage+' arena limit remains enabled')
        allowed.update(range(offset,offset+5))
    return allowed
