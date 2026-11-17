import portable_paths as _portable
import sys,struct,hashlib,json
from pathlib import Path
L=Path(str(_portable.LEGACY))
sys.path[:0]=[str(L),str(L/'research')]
from zoe2_archive import Archive,xor_words,strcode32
from campaign_enemy_preview import section
from cache_file_rebuilder import replace_group_files
W=Path(__file__).resolve().parents[2]
VAN=_portable.ORIGINALS/'ZOE2/STAGE.DAT'
V4=W/'progression-v4/Progression-v4';V5=W/'ship-v5/Ship-v5'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,o):Path(p).write_text(json.dumps(o,indent=2)+'\n',encoding='utf-8')
def sec(a,s):
 end=min((v for v in a.stages.values() if v>a.stages[s]),default=a.size)
 with a.path.open('rb') as f:f.seek(a.stages[s]);return f.read(end-a.stages[s])
def write_archive(a,blocks,out):
 stages=sorted(a.stages,key=a.stages.get);offsets={}
 with a.path.open('rb') as f,Path(out).open('xb') as o:
  o.write(f.read(a.stages[stages[0]]))
  for s in stages:offsets[s]=o.tell();o.write(blocks[s] if s in blocks else sec(a,s))
  f.seek(4);table=bytearray(xor_words(f.read(12+20*len(stages)),a.seed,a.seed^0xf0f0))
  for i in range(len(stages)):
   p=12+20*i;s=table[p:p+16].split(b'\0')[0].decode();assert offsets[s]%2048==0
   struct.pack_into('<I',table,p+16,offsets[s]//2048)
  o.seek(4);o.write(xor_words(table,a.seed,a.seed^0xf0f0))
def motion_order(groups,changes,a):
 moves=[]
 for ix,g in enumerate(groups):
  if g['folder'] not in ('cache','nocache','resident'):continue
  d=bytes(changes.get(ix,a.decode(g)));lookup={f['name']:f for f in g['files']};ordered=[];emitted=set()
  for f in g['files']:
   if f['name'].endswith('.mts'):
    b=d[f['offset']:f['offset']+f['size']];off=struct.unpack_from('<I',b)[0]
    lib=b[off:].split(b'\0',1)[0].decode('ascii');key=f'{strcode32(lib):08x}.mtl'
    if key in lookup and key not in emitted:
     ordered.append(lookup[key]);emitted.add(key);moves.append(dict(script=f['name'],library=key))
   if f['name'] not in emitted:ordered.append(f);emitted.add(f['name'])
  if [f['name'] for f in ordered]!=[f['name'] for f in g['files']]:
   # section() retains its original table entry order; pair a reordered table
   # separately below by replacing the group byte layout and file descriptors.
   result=bytearray();nf=[]
   for f in ordered:
    nf.append(dict(f,offset=len(result)));result.extend(d[f['offset']:f['offset']+f['size']])
   g['files']=nf;changes[ix]=result
 return moves
def rebuild_section(a,s,replacements=None,imports=None,order_motion=True,sound_imports=()):
 """Rebuild table entries explicitly so table order matches dependency order."""
 import campaign_enemy_preview as ce
 gs=a.groups(s);changes={}
 for ix,g in enumerate(gs):
  selected={f['name']:replacements[f['name']] for f in g['files'] if replacements and f['name'] in replacements}
  if selected:changes[ix]=replace_group_files(g,a.decode(g),selected)
 # ce.section checks names against original table order; reorder after packing
 # by wrapping its final texture-order pass. Imports are also handled here.
 import model_texture_load_order as mt
 original=mt.order_model_textures
 def combined(entries,decoded):
  entries,decoded,moves=original(entries,decoded)
  if not order_motion:return entries,decoded,moves
  ends=sorted(e[2] for e in entries)+[len(decoded)];endmap=dict(zip(ends,ends[1:]));blobs={(e[0],e[1]):bytes(decoded[e[2]:endmap[e[2]]]) for e in entries}
  lookup={(e[0],e[1]):e for e in entries};ordered=[];seen=set()
  for e in entries:
   k=(e[0],e[1])
   if e[0]==0x856a:
    b=blobs[k];off=struct.unpack_from('<I',b)[0];lib=b[off:].split(b'\0',1)[0].decode('ascii');dep=(0xed22c7,strcode32(lib))
    if dep in lookup and dep not in seen:ordered.append(lookup[dep]);seen.add(dep)
   if k not in seen:ordered.append(e);seen.add(k)
  out=bytearray()
  for e in ordered:k=(e[0],e[1]);e[2]=len(out);out.extend(blobs[k])
  return ordered,out,moves
 mt.order_model_textures=combined
 try:
  if imports:
   ci=next(i for i,g in enumerate(gs) if g['folder']=='cache');changes.setdefault(ci,bytearray(a.decode(gs[ci])))
  if order_motion:
   for i,g in enumerate(gs):
    if g['folder'] in ('cache','nocache'):changes.setdefault(i,bytearray(a.decode(g)))
  return ce.section(a,s,gs,changes,imports or [],sound_imports)
 finally:mt.order_model_textures=original
