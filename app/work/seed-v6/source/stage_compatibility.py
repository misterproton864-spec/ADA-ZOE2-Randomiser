import portable_paths as _portable
"""Narrow enemy/section exclusions supported by captured initialization faults."""
import struct
from scx_bytecode import native_calls,instructions,LENGTHS
from scx_manager_chain_adapter import appended_instructions,MANAGER_TYPES

NARITA=31;NOOP=0xfffff75a
FLEET_SCRIPT='ecf4abd1.scx'
FLEET_NATIVE_SIZE=113296
FLEET_NARITA_CALLS={113306,113392,113504}

def fleet_setup_calls(files,topology):
    """Include legacy tails reached by relative jumps, absent from adapter metadata.

    Original SCX scanning stops at 8e before the data/string region. The pinned
    fleet script has further executable procedures after its original file end.
    Opcode85 uses an offset relative to the opcode; opcode87 uses an absolute
    procedure offset. Decode tails on instruction boundaries, never raw patterns.
    """
    data=files[FLEET_SCRIPT];main=list(instructions(data))
    assert main[-1][0]==85663 and len(data)>=FLEET_NATIVE_SIZE
    calls=dict(native_calls(data));pending=[(FLEET_NATIVE_SIZE,dict(legacy_file_end=True))];ranges={};origins={}
    def discover(rows):
        for p,op,raw in rows:
            if op not in (0x85,0x87):continue
            target=(p+struct.unpack_from('<i',raw,1)[0] if op==0x85 else struct.unpack_from('<I',raw,1)[0])
            if FLEET_NATIVE_SIZE<=target<len(data):
                pending.append((target,dict(source=p,opcode=hex(op))))
    discover(main)
    for adapter in topology['adapters']:
        if adapter['file']==FLEET_SCRIPT:
            entry,end=adapter['procedure_entry'],adapter['procedure_end']
            rows=list(appended_instructions(data,entry,end))
            assert rows[-1][1]==0x89
            ranges[entry]=end;origins[entry]=dict(adapter_metadata=True)
            calls.update((p,int.from_bytes(raw[1:],'little')) for p,op,raw in rows if op==0x88)
            discover(rows)
    seen=set()
    while pending:
        entry,origin=pending.pop()
        if entry in seen:continue
        seen.add(entry);rows=[];p=entry
        while p<min(len(data),entry+1024):
            op=data[p];n=LENGTHS.get(op,1)
            assert p+n<=len(data) and op not in (0x8c,0x8d,0x8e),('Unexpected fleet tail',p,op)
            rows.append((p,op,data[p:p+n]));p+=n
            if op==0x89:break
        assert rows and rows[-1][1]==0x89,('Unterminated fleet tail',entry)
        ranges[entry]=p;origins[entry]=origin
        calls.update((p,int.from_bytes(raw[1:],'little')) for p,op,raw in rows if op==0x88)
        discover(rows)
    assert {13219:113440}=={v['source']:k for k,v in origins.items() if 'source' in v},origins
    for p in FLEET_NARITA_CALLS:
        assert calls.get(p) in (0xf69f7524,NOOP),('Fleet initialization layout changed',p)
    return calls,[dict(entry=entry,end=end,**origins[entry]) for entry,end in sorted(ranges.items())]

def regular_pool(stage,pools):
    excluded={10}
    if stage=='af01g':excluded.add(NARITA)
    return sorted(set(pools)-excluded)

def suppress_incompatible_pools(stage,files,topology):
    if stage!='af01g':return []
    calls,ranges=fleet_setup_calls(files,topology);edits=[]
    candidate=bytearray(files[FLEET_SCRIPT])
    for offset,command in sorted(calls.items()):
        if MANAGER_TYPES.get(command)!=NARITA:continue
        assert candidate[offset:offset+5]==b'\x88'+struct.pack('<I',command)
        struct.pack_into('<I',candidate,offset+1,NOOP)
        edits.append(dict(stage=stage,file=FLEET_SCRIPT,offset=offset,original_command=f'{command:08x}',replacement_command=f'{NOOP:08x}',reason='Captured Narita initialization failure; scan includes relative-jump legacy tails'))
    files[FLEET_SCRIPT]=bytes(candidate)
    remaining,_=fleet_setup_calls(files,topology)
    assert not any(MANAGER_TYPES.get(command)==NARITA for command in remaining.values())
    assert all(remaining[p]==NOOP for p in FLEET_NARITA_CALLS)
    return edits
