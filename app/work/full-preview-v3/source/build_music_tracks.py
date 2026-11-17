import portable_paths as _portable
"""Seeded whole-bank music selection at the native resolved-track boundary.

The game subsequently loads that bank, records its family at controller+108,
and generates both Play_Music and Set_State using that same family. No Wwise
event/media bytes are shuffled. Source cues and state indices are retained.
"""
import collections,ctypes,hashlib,json,re,struct,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LEGACY=Path(str(_portable.LEGACY))
GAME=Path(str(_portable.game()))
sys.path.insert(0,str(LEGACY/'research'))
from zoe2_archive import Archive
IMAGE=0x140000000;ENTRY=0x144caacb8
STOLEN=bytes.fromhex('48899c24b8000000')
SEED='full-music-2026-10-18-v3'

def code(mapping,cave,resume):
 b=bytearray(b'\x9c');ends=[]
 for src,dst in sorted(mapping.items()):
  b+=b'\x81\xfe'+struct.pack('<I',src)+b'\x75\x0a\xbe'+struct.pack('<I',dst)+b'\xe9'
  ends.append(len(b));b+=bytes(4)
 end=len(b)
 for p in ends:struct.pack_into('<i',b,p,end-(p+4))
 b+=b'\x9d'+STOLEN+b'\xe9';b+=struct.pack('<i',resume-(cave+len(b)+4))
 return bytes(b)

def build():
 tree=ET.parse(GAME/'sound/Windows/SoundbanksInfo.xml')
 archive=Archive(GAME/'ZOE2/STAGE.DAT.zoe2-ca01-loader-v1.bak')
 bank_stages=collections.defaultdict(set)
 for stage in archive.stages:
  for group in archive.groups(stage):
   if group['folder']=='sound':
    for f in group['files']:bank_stages[(group['location']+f['offset'])//2048].add(stage)
 bosses={'ca02','ba02','ba03','wn01','cy02','vc01','ef01','ef02','ef02g','fr02','cs01','fa01','am01g','am02','fr04','fr04g','af02'}
 regular=set(r['stage'] for r in json.loads((ROOT/'Full-Preview-v3/manifest.json').read_text())['enemy_changes'])|{'tr02','vc03','ef03'}
 families={};ineligible=[]
 # Preserve title/hangar, special callbacks and native aliases. Alias pairs
 # have shared logical families and need a separate dual-bank adapter.
 protected={0x16,0x35e4,0xfa2e,0x20f11,0x20bfd,0x1bb76,0x136f3}
 for bank in tree.findall('.//SoundBanks/SoundBank'):
  path=bank.findtext('Path') or '';match=re.fullmatch(r'us([0-9a-f]{8})\.bnk',path)
  if not match:continue
  family=int(match.group(1),16);events={};category_paths=set()
  for e in bank.findall('./IncludedEvents/Event'):
   m=re.fullmatch(r'(Play_Music|Set_State)_([0-9a-f]+)_([0-9]+|None)',e.attrib.get('Name',''))
   if m and int(m.group(2),16)==family:
    events[(m.group(1),m.group(3))]=int(e.attrib['Id'])
    category_paths.add((e.attrib.get('ObjectPath','').split('\\')+['']*4)[3])
  if not events or not any(k[0]=='Play_Music' for k in events):continue
  stages=bank_stages[family]
  category='boss' if stages&bosses else 'battle' if stages&regular else 'exploration' if stages&{'vr01','cf01'} else None
  if family in protected or category is None:
   ineligible.append(dict(family=f'{family:06x}',stages=sorted(stages),reason='protected native callback/alias or menu/cutscene/unclassified'))
   continue
  assert (GAME/'sound/Windows'/path).is_file()
  families[family]=dict(bank=path,stages=sorted(stages),category=category,
   native_structure=sorted(category_paths),signature=sorted(events),events=events)
 buckets=collections.defaultdict(list)
 for f,row in families.items():buckets[(row['category'],tuple(row['native_structure']),tuple(row['signature']))].append(f)
 mapping={};rows=[]
 for key,items in sorted(buckets.items()):
  order=sorted(items,key=lambda f:hashlib.sha256((SEED+'\0'+str(f)).encode()).digest())
  if len(order)<2:
   ineligible.extend(dict(family=f'{f:06x}',reason='no category/state-compatible peer') for f in order);continue
  for i,src in enumerate(order):
   dst=order[(i+1)%len(order)];mapping[src]=dst
   assert families[src]['signature']==families[dst]['signature']
   rows.append(dict(source_family=f'{src:06x}',destination_family=f'{dst:06x}',
    source_bank=families[src]['bank'],destination_bank=families[dst]['bank'],category=key[0],
    source_stages=families[src]['stages'],destination_stages=families[dst]['stages'],
    play_and_state_signature=families[src]['signature']))
 assert len(mapping)>=10 and set(mapping)==set(mapping.values())
 # Match the stolen instruction directly against the supported executable.
 exe=(GAME/'Zoe2Mars.exe').read_bytes();digest=hashlib.sha256(exe).hexdigest()
 assert digest=='b96c63f680712651d92933d896ec65aeb95788c19857dd7114526cf7ccdc3b92'
 pe=struct.unpack_from('<I',exe,60)[0];table=pe+24+struct.unpack_from('<H',exe,pe+20)[0]
 sections=[struct.unpack_from('<IIII',exe,table+40*i+8) for i in range(struct.unpack_from('<H',exe,pe+6)[0])]
 raw=next(p+ENTRY-IMAGE-v for vs,v,n,p in sections if v<=ENTRY-IMAGE<v+n)
 assert exe[raw:raw+len(STOLEN)]==STOLEN
 runtime=ROOT/'Full-Preview-v3/runtime';runtime.mkdir(exist_ok=True)
 sample=code(mapping,IMAGE+0x20000000,ENTRY+len(STOLEN))
 source=(LEGACY/'FakeAnubisDamageAdapter.cs').read_text().replace('FakeAnubisDamageAdapter','MusicTrackAdapter')
 source=source.replace('const long Factory=0x14784ac54;','const long Factory='+hex(ENTRY)+';')
 a=source.index(' static readonly byte[] Stolen=');b=source.index('\n',a)
 source=source[:a]+' static readonly byte[] Stolen={'+','.join(hex(x) for x in STOLEN)+'};'+source[b:]
 a=source.index(' public static byte[] BuildCave(');b=source.index(' public static byte[] BuildRedirect(',a)
 payload=' static readonly byte[] Payload={'+','.join(hex(x) for x in sample)+'};\n'
 payload+=' public static byte[] BuildCave(long image,long cave) {byte[] b=(byte[])Payload.Clone();Buffer.BlockCopy(Rel32(image+Factory-ImageBase+Stolen.Length,cave+b.Length),0,b,b.Length-4,4);return b;}\n'
 source=source[:a]+payload+source[b:]
 a=source.index(' static void SelfTest(');b=source.index(' static IntPtr AllocateNearby',a)
 source=source[:a]+''' static void SelfTest(string folder) {
 Directory.CreateDirectory(folder);foreach(long image in new long[]{ImageBase,0x180000000,0x7ff600000000}) {
 long cave=image+0x20000000;byte[] b=BuildCave(image,cave),p=BuildRedirect(image,cave);
 if(image+Factory-ImageBase+5+BitConverter.ToInt32(p,1)!=cave)throw new Exception("Redirect mismatch");
 if(cave+b.Length+BitConverter.ToInt32(b,b.Length-4)!=image+Factory-ImageBase+Stolen.Length)throw new Exception("Continuation mismatch");
 File.WriteAllBytes(Path.Combine(folder,"music-track-"+image.ToString("x")+".bin"),b);
 }Console.WriteLine("Whole music-bank mapping generation passed at three image bases; no game opened.");
 }
'''+source[b:]
 source=source.replace('Runtime Fake Anubis normal-damage adapter active','Runtime seeded whole music-bank adapter active')
 source=source.replace('Damage bytes differ or adapter already active','Music track boundary bytes differ or adapter already active')
 (runtime/'MusicTrackAdapter.cs').write_text(source)
 subprocess.run([_portable.compiler(),'/nologo','/platform:x64','/optimize+','/out:'+str(runtime/'MusicTrackAdapter.exe'),str(runtime/'MusicTrackAdapter.cs')],check=True)
 fixtures=ROOT/'reports/music-track-fixtures';fixtures.mkdir(exist_ok=True)
 subprocess.run([str(runtime/'MusicTrackAdapter.exe'),'--self-test',str(fixtures)],check=True)
 for image in (IMAGE,0x180000000,0x7ff600000000):assert (fixtures/f'music-track-{image:x}.bin').read_bytes()==code(mapping,image+0x20000000,image+ENTRY-IMAGE+len(STOLEN))
 # Execute the exact generated transform plus stolen instruction in an isolated
 # Windows x64 stack frame. ESI is intentionally changed; RBX and the caller's
 # ESI are preserved by the enclosing native fixture.
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.VirtualAlloc.restype=ctypes.c_void_p
 k.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_uint32]
 k.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32]
 mem=k.VirtualAlloc(None,8192,0x3000,0x40);assert mem
 try:
  prefix=bytes.fromhex('56 4881ec00020000 89ce e9')+struct.pack('<i',0x100-(1+7+2+5))
  resume=bytes.fromhex('89f0 4881c400020000 5e c3')
  body=code(mapping,mem+0x100,mem+0x1800)
  ctypes.memmove(mem,prefix,len(prefix));ctypes.memmove(mem+0x100,body,len(body));ctypes.memmove(mem+0x1800,resume,len(resume))
  fn=ctypes.WINFUNCTYPE(ctypes.c_uint32,ctypes.c_uint32)(mem)
  values=set(range(1000))|set(mapping)|{0xffffffff,0x16,0x35e4,0xfa2e,0x20f11,0x20bfd}
  for v in values:assert fn(v)==mapping.get(v,v),hex(v)
 finally:k.VirtualFree(mem,0,0x8000)
 report=dict(seed=SEED,passed=True,track_mapping={str(k):v for k,v in mapping.items()},tracks=rows,
  unchanged=ineligible,native_checks=len(values),image_bases_verified=3,hook=hex(ENTRY),
  whole_bank_selection_implemented=True,original_events_and_media_unchanged=True,
  category_basis='Original stage membership; conservative inferred gameplay categories plus exact authored structure/state signatures.',
  both_play_and_state_use_native_controller_family=True,invalid_or_silent_donor_ids_detected=False,
  beyond_the_bounds_asset_identified=False,gameplay_verified=False,helper_sha256=hashlib.sha256((runtime/'MusicTrackAdapter.exe').read_bytes()).hexdigest())
 (ROOT/'reports/music-tracks-verification.json').write_text(json.dumps(report,indent=2)+'\n')
 print('PASS whole-bank seeded mapping:',len(mapping),'tracks;',len(values),'native checks; audible playback pending',flush=True)

if __name__=='__main__':build()
