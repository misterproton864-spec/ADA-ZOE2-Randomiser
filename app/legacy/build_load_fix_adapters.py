import portable_paths as _portable
import json,struct,sys
from mixed_install_transaction import sha
from pathlib import Path
root=Path.cwd();source=(root/'FakeAnubisDamageAdapter.cs').read_text()
rows=json.loads((root/'music-bank-address-audit.json').read_text())['rows']
audit=json.loads((root/'music-bank-address-audit.json').read_text())
archive=Path(sys.argv[1]) if len(sys.argv)>1 else root/'Full-Randomiser-Preview-v1.2-Randomised-Boss-Fix/STAGE.DAT'
assert audit['modified_stage_sha256']==sha(archive),'Re-audit music sectors after changing STAGE.DAT'
mp={}
for r in rows:
 a,b=r['modified_sector'],r['original_sector']
 if a!=b:
  assert a not in mp or mp[a]==b;mp[a]=b
out=root/'Load-Fix-Verification';out.mkdir(exist_ok=True)
(root/'music-sector-remap.json').write_text(json.dumps(mp,indent=2))
(root/'music-sector-source.json').write_text(json.dumps(dict(archive_sha256=audit['modified_stage_sha256'],mapping_sha256=sha(root/'music-sector-remap.json'),mapping_count=len(mp)),indent=2))

def create(name,entry,stolen,body,test):
 s=source.replace('FakeAnubisDamageAdapter',name).replace('0x14784ac54',hex(entry))
 a=s.index(' static readonly byte[] Stolen=');b=s.index('\n',a)
 s=s[:a]+' static readonly byte[] Stolen={'+','.join(hex(x) for x in stolen)+'};'+s[b:]
 a=s.index(' public static byte[] BuildCave(');b=s.index(' public static byte[] BuildRedirect(',a)
 s=s[:a]+body+s[b:]
 a=s.index(' static void SelfTest(');b=s.index(' static IntPtr AllocateNearby',a)
 s=s[:a]+test+s[b:]
 s=s.replace('Damage bytes differ or adapter already active','Hook bytes differ or adapter already active').replace('Runtime Fake Anubis normal-damage adapter active for PID','Runtime '+name+' active for PID')
 (root/(name+'.cs')).write_text(s)

body=''' public static byte[] BuildTransform() {
  List<byte> b=new List<byte>();
  // Restore original archive-sector IDs before the PC bank lookup table.
'''
for a,b in sorted(mp.items()):
 body+='  Add(b,0x81,0xfa);b.AddRange(BitConverter.GetBytes((uint)'+str(a)+'));Add(b,0x75,0x06,0xba);b.AddRange(BitConverter.GetBytes((uint)'+str(b)+'));Add(b,0xc3);\n'
body+='  Add(b,0xc3);return b.ToArray();\n }\n'
# Each matched branch uses RET in transform; change RET to a JMP to shared epilogue in cave.
body+=''' public static byte[] BuildCave(long image,long cave) {
  List<byte> b=new List<byte>();Add(b,0x9c);
'''
for a,c in sorted(mp.items()):
 body+='  Add(b,0x81,0xfa);b.AddRange(BitConverter.GetBytes((uint)'+str(a)+'));Add(b,0x75,0x0a,0xba);b.AddRange(BitConverter.GetBytes((uint)'+str(c)+'));Add(b,0xe9);b.AddRange(new byte[4]);\n'
body+='''  int end=b.Count;
  for(int i=1;i<end;i+=18) { byte[] rel=BitConverter.GetBytes(end-(i+18));for(int j=0;j<4;j++)b[i+14+j]=rel[j]; }
  Add(b,0x9d);b.AddRange(Stolen);Add(b,0xe9);b.AddRange(Rel32(image+Factory-ImageBase+Stolen.Length,cave+b.Count+4));return b.ToArray();
 }
'''
test=''' static void SelfTest(string folder) {
  Directory.CreateDirectory(folder);
  File.WriteAllBytes(Path.Combine(folder,"music-transform.bin"),BuildTransform());
  foreach(long image in new long[]{ImageBase,0x180000000,0x7ff600000000}) {
   long cave=image+0x20000000;byte[] code=BuildCave(image,cave);BuildRedirect(image,cave);
   if(cave+code.Length+BitConverter.ToInt32(code,code.Length-4)!=image+Factory-ImageBase+Stolen.Length)throw new Exception("Continuation");
  }
  File.WriteAllBytes(Path.Combine(folder,"music-cave.bin"),BuildCave(ImageBase,ImageBase+0x20000000));
  Console.WriteLine("Music sector remap generated at three image bases.");
 }
'''
create('MusicSectorAdapter',0x144caac30,bytes.fromhex('5641564157'),body,test)
body=''' public static byte[] BuildCave(long image,long cave) {
  List<byte> b=new List<byte>();
  Add(b,0x48,0x8b,0x05);b.AddRange(Rel32(image+0x1547350,cave+7));
  // A post-cutscene Nephtis-only dialogue callback has no recipient when she is replaced.
  // Preserve the native setter when she exists and leave the replacement's completion alone.
  Add(b,0x9c,0x48,0x85,0xc0,0x75,0x02,0x9d,0xc3,0x9d,0xe9);
  b.AddRange(Rel32(image+Factory-ImageBase+Stolen.Length,cave+b.Count+4));return b.ToArray();
 }
'''
test=''' static void SelfTest(string folder) {
  Directory.CreateDirectory(folder);
  foreach(long image in new long[]{ImageBase,0x180000000,0x7ff600000000}) {
   long cave=image+0x20000000;byte[] code=BuildCave(image,cave);BuildRedirect(image,cave);
   if(cave+7+BitConverter.ToInt32(code,3)!=image+0x1547350)throw new Exception("Actor pointer");
   if(cave+code.Length+BitConverter.ToInt32(code,code.Length-4)!=image+Factory-ImageBase+Stolen.Length)throw new Exception("Continuation");
  }
  File.WriteAllBytes(Path.Combine(folder,"nephtis-callback-cave.bin"),BuildCave(ImageBase,ImageBase+0x20000000));
  Console.WriteLine("Nephtis dialogue callback guard generated at three image bases.");
 }
'''
create('NephtisDialogueAdapter',0x1462ddcc6,bytes.fromhex('488b05839626fb'),body,test)
print('Prepared adapters; music mappings',len(mp))
