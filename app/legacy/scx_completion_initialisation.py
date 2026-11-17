import portable_paths as _portable
"""Conservative script-order audit for the shared transition fade object."""
from scx_bytecode import instructions,native_calls
from scx_call_arguments import call_arguments

FADE_CREATE=0x6197ab0b
FADE_USE=0xffcc3307

def fade_use_before_setup(data,entry):
    bypos={p:(op,raw) for p,op,raw in instructions(data)}
    pending=[(entry,(),False)];seen=set();unsafe=set()
    while pending:
        pc,stack,created=pending.pop();state=(pc,stack,created)
        if state in seen:continue
        if len(seen)>=20000 or len(stack)>32:raise ValueError('Completion initialisation traversal limit')
        seen.add(state)
        if pc not in bypos:raise ValueError('Invalid completion instruction target')
        op,raw=bypos[pc];nextpc=pc+len(raw)
        if op in (0x85,0x86):
            pending.append((pc+int.from_bytes(raw[1:],'little',signed=True),stack,created))
            if op==0x86:pending.append((nextpc,stack,created))
        elif op==0x87:pending.append((int.from_bytes(raw[1:],'little'),stack+(nextpc,),created))
        elif op==0x89:
            if stack:pending.append((stack[-1],stack[:-1],created))
        elif op==0x8e:raise ValueError('Completion flow reaches data boundary')
        else:
            if op==0x88:
                command=int.from_bytes(raw[1:],'little')
                if command==FADE_USE and not created:unsafe.add(pc)
                if command==FADE_CREATE:created=True
            pending.append((nextpc,stack,created))
    return sorted(unsafe)

def fade_guard_source(data,entry):
    unsafe=fade_use_before_setup(data,entry)
    if not unsafe:return None
    for offset,command in native_calls(data):
        if command!=FADE_CREATE:continue
        try:args=call_arguments(data,offset)
        except ValueError:continue
        # Reuse the source's own transparent initialization. No string pointers,
        # script callback pointers or computed expressions are copied.
        if len(args)==4 and all(a['kind']==0xc0 and a['value']==0 and a['offset'] is not None for a in args):
            start=args[0]['offset']-3
            return dict(source_call=offset,source_start=start,bytes=data[start:offset+5],unsafe_use_offsets=unsafe)
    raise ValueError('Unsafe transition fade has no verified source initialization frame')
