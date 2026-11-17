"""Rewrite only exact, group-bound Extra Mission species literals.

This is a candidate script repair. The native `ffff7934` handler resolves an
actor by group and species, then dereferences the result without a null check.
The rewrite does not establish live combat or progression safety.
"""
import struct

from actor_reference_adapter import ENE_TO_EXTERNAL


def patch(data, group_types, mapping):
    source=bytes(data)
    result=bytearray(source)
    edits=[]
    for group,types in group_types.items():
        if len(types)!=1:
            raise ValueError('Extra Mission group has multiple source types')
        typ=next(iter(types))
        target=mapping.get(typ,typ)
        if target==typ:continue
        if typ not in ENE_TO_EXTERNAL or target not in ENE_TO_EXTERNAL:
            raise ValueError('Extra Mission species lacks external type code')
        group_bytes=struct.pack('<I',group)
        old=struct.pack('<I',ENE_TO_EXTERNAL[typ])
        new=struct.pack('<I',ENE_TO_EXTERNAL[target])
        # These exact opcode frames occur twice for each group in the five
        # qualified wave scripts. They bind the actor group to its external
        # species code; the game's lookup uses both values.
        frames=((b'\xc0'+group_bytes+b'\xf8\x80\xb0\xc0'+old+b'\xf9',9),
                (b'\xc0'+group_bytes+b'\xf9\x80\xb0\xc0'+old+b'\xfa',9))
        sites=[]
        for frame,offset in frames:
            cursor=0
            while (at:=source.find(frame,cursor))>=0:
                sites.append(at+offset)
                cursor=at+1
        if len(sites)!=2 or len(set(sites))!=2:
            raise ValueError('Extra Mission script pair count differs for group '+hex(group)+': '+str(sites))
        for at in sites:
            if source[at:at+4]!=old or result[at:at+4] not in (old,new):
                raise ValueError('Extra Mission script pair overlap for group '+hex(group))
            result[at:at+4]=new
            edits.append(dict(group=group,source_type=typ,target_type=target,
                              offset=at,before=old.hex(),after=new.hex()))
    allowed={i for edit in edits for i in range(edit['offset'],edit['offset']+4)}
    if any(i not in allowed for i,(before,after) in enumerate(zip(source,result)) if before!=after):
        raise ValueError('Unexpected Extra Mission script edit')
    return bytes(result),edits
