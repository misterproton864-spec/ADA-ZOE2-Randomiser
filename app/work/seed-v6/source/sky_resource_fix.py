import portable_paths as _portable
"""Allow Sky's native Narita texture through the cinematic resource filter."""
import json,struct,subprocess,hashlib
from pathlib import Path
from archive_tools import L,sha,save
IMAGE=0x140000000;ENTRY=0x14008a9c0;LOAD_STAGE=0x141542708;TEXTURE=0xf72f58d3
STOLEN=bytes.fromhex('488b0511984b01')
def code(image,cave,stage_address=None):
 b=bytearray(bytes.fromhex('9c50 84c9 0f85'));fix=[len(b)];b+=bytes(4)
 b+=b'\x81\xfa'+struct.pack('<I',TEXTURE)+bytes.fromhex('0f85');fix.append(len(b));b+=bytes(4)
 b+=b'\x48\xb8'+struct.pack('<Q',stage_address if stage_address is not None else image+LOAD_STAGE-IMAGE)
 b+=bytes.fromhex('8138')+b'vc03'+bytes.fromhex('0f85');fix.append(len(b));b+=bytes(4)
 b+=bytes.fromhex('80780400 0f85');fix.append(len(b));b+=bytes(4)
 b+=bytes.fromhex('589d b801000000 c3');fallback=len(b)
 b+=bytes.fromhex('589d 488b05')+struct.pack('<i',image+0x15441d8-(cave+len(b)+9))
 b+=b'\xe9'+struct.pack('<i',image+ENTRY-IMAGE+7-(cave+len(b)+5))
 for p in fix:struct.pack_into('<i',b,p,fallback-p-4)
 return bytes(b)
def build(out):
 out=Path(out);runtime=out/'runtime';runtime.mkdir(parents=True,exist_ok=True)
 sample=code(IMAGE,IMAGE+0x20000000)
 source=(L/'FakeAnubisDamageAdapter.cs').read_text().replace('FakeAnubisDamageAdapter','SkyResourceAdapter').replace('const long Factory=0x14784ac54;','const long Factory='+hex(ENTRY)+';')
 a=source.index(' static readonly byte[] Stolen=');b=source.index('\n',a)
 source=source[:a]+' static readonly byte[] Stolen={'+','.join(hex(x) for x in STOLEN)+'};'+source[b:]
 a=source.index(' public static byte[] BuildCave(');b=source.index(' public static byte[] BuildRedirect(',a)
 body=' static readonly byte[] Payload={'+','.join(hex(x) for x in sample)+'};\n'
 # Relocate only the loading-stage absolute address and the two RIP-relative
 # native continuations. All intra-cave branches remain position independent.
 stagepos=sample.index(b'\x48\xb8')+2;loadpos=len(sample)-9
 body+=' public static byte[] BuildCave(long image,long cave) {byte[] b=(byte[])Payload.Clone();'
 body+='Buffer.BlockCopy(BitConverter.GetBytes(image+0x1542708),0,b,'+str(stagepos)+',8);'
 body+='Buffer.BlockCopy(Rel32(image+0x15441d8,cave+'+str(loadpos+4)+'),0,b,'+str(loadpos)+',4);'
 body+='Buffer.BlockCopy(Rel32(image+Factory-ImageBase+7,cave+b.Length),0,b,b.Length-4,4);return b;}\n'
 source=source[:a]+body+source[b:]
 a=source.index(' static void SelfTest(');b=source.index(' static IntPtr AllocateNearby',a)
 source=source[:a]+''' static void SelfTest(string folder) {
 Directory.CreateDirectory(folder);foreach(long image in new long[]{ImageBase,0x180000000,0x7ff600000000}) {
 long cave=image+0x20000000;byte[] bytes=BuildCave(image,cave),redirect=BuildRedirect(image,cave);
 if(redirect.Length!=7||cave+bytes.Length+BitConverter.ToInt32(bytes,bytes.Length-4)!=image+Factory-ImageBase+7)throw new Exception("Continuation differs");
 File.WriteAllBytes(Path.Combine(folder,"sky-"+image.ToString("x")+".bin"),bytes);
 }Console.WriteLine("Sky resource filter generated at three image bases; no game opened.");
 }
'''+source[b:]
 source=source.replace('Runtime Fake Anubis normal-damage adapter active','Runtime Sky Narita resource correction active').replace('Damage bytes differ or adapter already active','Resource-filter entry differs or correction already attached')
 path=runtime/'SkyResourceAdapter.cs';path.write_text(source)
 subprocess.run([_portable.compiler(),'/nologo','/platform:x64','/optimize+','/out:'+str(path.with_suffix('.exe')),str(path)],check=True)
 fixtures=out/'verification/sky-filter';fixtures.mkdir(parents=True,exist_ok=True)
 subprocess.run([str(path.with_suffix('.exe')),'--self-test',str(fixtures)],check=True)
 for image in (IMAGE,0x180000000,0x7ff600000000):assert (fixtures/f'sky-{image:x}.bin').read_bytes()==code(image,image+0x20000000)
 proof=dict(scope='Nonresident f72f58d3.tex only, exact loading stage vc03',entry=hex(ENTRY),file='SkyResourceAdapter.exe',sha256=sha(path.with_suffix('.exe')),image_bases_verified=3,gameplay_verified=False)
 save(out/'verification/sky-filter-build.json',proof);return proof
