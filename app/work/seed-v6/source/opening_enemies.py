import portable_paths as _portable
"""Opening Raptor-only pools: self-contained replacement managers and assets."""
import hashlib,json,struct
from archive_tools import L
from mixed_boss_catalog import payloads
from scx_bytecode import native_calls
from scx_manager_chain_adapter import MANAGER_TYPES
from actor_reference_adapter import patch_references
from randomizer_settings import ENEMIES,weighted_enemy,enemy_level

STAGES=frozenset(('ca00','cad1','ca01'))
TARGETS=frozenset((41,42))  # No respawn-manager or flying attachment dependency.

def target(seed,stage,weights):
    enabled=[t for t in TARGETS if any(v==t and weights[k]>0 for k,v in ENEMIES.items())]
    return weighted_enemy(seed,stage,'opening-replacement',enabled or [40],weights)

def asset_set(stock,typ):
    if typ==40:return {},None,None
    if typ not in TARGETS:raise ValueError('Unsupported opening enemy')
    spec=next(r for r in json.loads((L/'enemy-assets.json').read_text()).values() if r['type']==typ)
    donor=payloads(stock,spec['donor']);selected={}
    for row in spec['files']:
        body=donor[row['hash']]
        if hashlib.sha256(body).hexdigest()!=row['sha256']:raise ValueError('Opening donor hash differs')
        selected[row['hash']]=body
    for name in list(selected):
        if name.endswith('.mdz'):
            cvz=name[:-4]+'.cvz'
            if cvz in donor:selected[cvz]=donor[cvz]
            tex=f'{struct.unpack_from("<I",selected[name],32)[0]:08x}.tex'
            selected[tex]=donor[tex]
        if name.endswith('.mts'):
            from archive_tools import strcode32
            body=selected[name];p=struct.unpack_from('<I',body)[0]
            library=f'{strcode32(body[p:].split(bytes((0,)),1)[0].decode("ascii")):08x}.mtl'
            selected[library]=donor[library]
    return selected,spec['donor'],int(spec['command'],16)

def prepare(seed,stock,stage,row,weights,levels,selectors):
    typ=target(seed,stage,weights);original=payloads(stock,stage);files=original.copy();edits=[];logs=[]
    assets,donor,command=asset_set(stock,typ)
    def edit(name,offset,before,after,kind):
        if before!=after:edits.append(dict(stage=stage,file=name,offset=offset,before=before.hex(),after=after.hex(),kind=kind))
    setups=0
    for name,data in original.items():
        if not name.endswith('.scx'):continue
        calls=native_calls(data)
        patched,refs=patch_references(data,[dict(offset=p,command=h) for p,h in calls if h in selectors],{40:typ})
        for item in refs:
            p=item['offset'];edit(name,p,data[p:p+4],patched[p:p+4],'enemy_selector')
        b=bytearray(patched)
        for p,h in calls:
            if h not in MANAGER_TYPES:continue
            if MANAGER_TYPES[h]!=40:raise ValueError('Opening pool is no longer Raptor-only')
            setups+=1
            if command is not None:
                after=struct.pack('<I',command);edit(name,p+1,data[p+1:p+5],after,'opening_manager');b[p+1:p+5]=after
        files[name]=bytes(b)
    if not setups:raise ValueError('Opening manager setup not found')
    for slot in row['slots']:
        if slot['original_type']==10:continue
        if slot['original_type']!=40:raise ValueError('Opening native group differs')
        name=slot['file'];p=slot['offset'];b=bytearray(files[name])
        if b[p:p+3]!=bytes((40,slot['count'],slot['level'])):raise ValueError('Opening ENE source differs')
        level=enemy_level(seed,stage,name+'/'+str(p),slot['level'],levels)
        edit(name,p,bytes((40,)),bytes((typ,)),'enemy_type')
        edit(name,p+2,bytes((slot['level'],)),bytes((level,)),'enemy_level')
        b[p]=typ;b[p+2]=level;files[name]=bytes(b)
        logs.append(dict(stage=stage,file=name,record=slot['record'],slot=slot['slot'],offset=p,enemy=typ,
                         original_type=40,count=slot['count'],original_level=slot['level'],level=level,native_pool=[40],replacement_pool=sorted(TARGETS)))
    imported={n:b for n,b in assets.items() if n not in original};files.update(imported)
    report=dict(stage=stage,target=typ,donor=donor,manager_command=command,manager_calls=setups,
                files={n:hashlib.sha256(b).hexdigest() for n,b in imported.items()},gameplay_verified=False)
    aliases={label:{'@'+stage+'_'+n[:8]+suffix:'@'+donor+'_'+n[:8]+suffix
                   for n in assets if n.endswith('.tex') for suffix in ('.dat','.tbl')} for label in ('main','small')}
    return files,edits,logs,report,aliases
