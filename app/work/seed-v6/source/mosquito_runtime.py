import portable_paths as _portable
"""Finite swarm pending-count postfix. Native aggregation executes exactly once."""
import ctypes,hashlib,itertools,json,os,struct,subprocess
from pathlib import Path
from archive_tools import L,sha,save
from valley_viper import coff_image,EXE_SHA
IMAGE=0x140000000;ENTRY=0x1405a8290;NATIVE=0x14817f120
STAGE=0x141535830;ENE_TABLE=0x14154c098;ENE_COUNT=0x14154c094
NATIVE_SHA='bb8fb31949506b8818d929e7f018e33febd927f1d3164bc963c12efd50acf43d'
C_CODE='/* Original native aggregation runs first.\n * Only exact, finite, newly selected non-ambient swarms gain pending counts.\n * Original swarm records, callbacks, HP and scripts are never changed here. */\ntypedef unsigned char u8;\ntypedef unsigned short u16;\ntypedef unsigned int u32;\ntypedef unsigned long long u64;\ntypedef struct {char stage[8];u16 record;u8 slot,count;u32 group;} Rule;\ntypedef struct {u64 stage,ene_table,ene_count;u32 enabled,count;\n u32 passes,rows_fixed,rejected,pad;Rule rules[64];} Config;\n#define B(p,o) (*(u8*)((u8*)(p)+(o)))\n#define H(p,o) (*(u16*)((u8*)(p)+(o)))\n#define I(p,o) (*(u32*)((u8*)(p)+(o)))\n#define P(p,o) (*(u64*)((u8*)(p)+(o)))\nstatic int stage_match(const char*a,const char*b){\n for(u32 i=0;i<8;i++){if(a[i]!=b[i])return 0;if(!a[i])return 1;}return 0;\n}\nvoid swarm_pending(void*manager,Config*c){\n if(!c->enabled||c->count>64||!c->stage||!c->ene_table||!c->ene_count)return;\n u64 base=*(u64*)c->ene_table;u16 records=*(u16*)c->ene_count;\n if(!base||!records||records>4096)return;\n u8 count=B(manager,0x90);u64 table=P(manager,0x98);if(!table)return;\n for(u32 i=1;i<count;i++){\n  void*t=(void*)(table+i*32);u64 record=P(t,0),slot=P(t,8);\n  for(u32 j=0;j<c->count;j++){\n   Rule*r=&c->rules[j];\n   if(!stage_match((const char*)c->stage,r->stage)||r->record>=records||r->slot>3||!r->count||r->count>6)continue;\n   if(record!=base+(u64)r->record*112||slot!=record+48+(u64)r->slot*8)continue;\n   if(I(record,0x58)!=r->group||B(slot,0)!=10||B(slot,1)!=r->count)continue;\n   // Negative is inactive; bit2000 recycles particles and is not a finite replacement.\n   if(H(record,0x50)&0xa000)continue;\n   u16 initial=H(t,0x14),pending=H(t,0x16);\n   if(initial!=(u16)r->count*6||pending>initial){c->rejected++;continue;}\n   if(pending){I(record,0x60)+=pending;B(t,0x1b)&=0xfe;c->rows_fixed++;}\n   break;\n  }\n }\n c->passes++;\n}\n'

def executable_bytes():
 data=Path(str(_portable.game() / 'Zoe2Mars.exe')).read_bytes()
 if hashlib.sha256(data).hexdigest()!=EXE_SHA:raise ValueError('Unsupported Mosquito executable')
 pe=struct.unpack_from('<I',data,60)[0];st=pe+24+struct.unpack_from('<H',data,pe+20)[0]
 sections=[struct.unpack_from('<IIII',data,st+40*i+8) for i in range(struct.unpack_from('<H',data,pe+6)[0])]
 def read(address,n):
  at=next(r+address-IMAGE-v for vs,v,rs,r in sections if v<=address-IMAGE<v+rs)
  return data[at:at+n]
 stolen=read(ENTRY,5);native=read(NATIVE,90)
 if stolen[0]!=0xe9 or ENTRY+5+struct.unpack_from('<i',stolen,1)[0]!=NATIVE:raise ValueError('Mosquito thunk differs')
 if hashlib.sha256(native).hexdigest()!=NATIVE_SHA:raise ValueError('Mosquito native aggregation differs')
 return stolen,native

def rules(selected):
 keys=sorted({(r['stage'],r['record'],r['slot'],r['count'],r['script_group_id']) for r in selected})
 if not keys or len(keys)>64:raise ValueError('Finite swarm rule count outside bounds')
 if any(len(s.encode('ascii'))>=8 or not 0<=rec<4096 or not 0<=slot<4 or not 1<=n<=6 for s,rec,slot,n,g in keys):raise ValueError('Invalid finite swarm rule')
 return b''.join(struct.pack('<8sHBBI',s.encode('ascii'),rec,slot,n,g) for s,rec,slot,n,g in keys)

def config(image,bindings):
 return struct.pack('<QQQIIIIII',image+STAGE-IMAGE,image+ENE_TABLE-IMAGE,image+ENE_COUNT-IMAGE,1,len(bindings)//16,0,0,0,0)+bindings+bytes(1024-len(bindings))

def wrapper(image,cave,entry):
 # Entry RSP is 8 modulo16. Push one nonvolatile register and reserve shadow space.
 return (bytes.fromhex('53 4883ec20 4889cb 48b8')+struct.pack('<Q',image+NATIVE-IMAGE)+
  bytes.fromhex('ffd0 4889d9 48ba')+struct.pack('<Q',cave+0x8000)+bytes.fromhex('48b8')+
  struct.pack('<Q',cave+0x1000+entry)+bytes.fromhex('ffd0 4883c420 5b c3'))

def selftest(tick,entry,native):
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.VirtualAlloc.restype=ctypes.c_void_p
 k.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_uint32];k.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32]
 memory=k.VirtualAlloc(None,0xa000,0x3000,0x40)
 if not memory:raise OSError('Cannot allocate native swarm fixture')
 cases=0
 try:
  ctypes.memmove(memory+0x1000,tick,len(tick));ctypes.memmove(memory+0x9000,native,len(native))
  # Relocate the real shipping wrapper to execute the pinned native bytes locally.
  wrapped=wrapper(IMAGE,memory,entry).replace(struct.pack('<Q',NATIVE),struct.pack('<Q',memory+0x9000))
  ctypes.memmove(memory,wrapped,len(wrapped))
  fn=ctypes.WINFUNCTYPE(None,ctypes.c_void_p)(memory)
  original=ctypes.WINFUNCTYPE(None,ctypes.c_void_p)(memory+0x9000)
  for stage,pending,live,group_ok,budget_ok,flags,typ in itertools.product(('ca01','ca01x','ca00','cy02','vc01','wn01'),(0,1,6,12,13),(0,1,6),(False,True),(False,True),(0,1,0x8000,0x2000),(10,40)):
   manager=ctypes.create_string_buffer(0x100);table=ctypes.create_string_buffer(64);records=ctypes.create_string_buffer(224)
   cfg=ctypes.create_string_buffer(1072);text=ctypes.create_string_buffer(stage.encode()+b'\0')
   base=ctypes.addressof(records);record=base+112;slot=record+48;pp=ctypes.c_void_p(base);count=ctypes.c_ushort(2)
   manager[0x90]=b'\x02';struct.pack_into('<Q',manager,0x98,ctypes.addressof(table))
   struct.pack_into('<QQ',table,32,record,slot);struct.pack_into('<HH',table,32+0x14,12 if budget_ok else 18,pending)
   table[32+0x1a]=bytes((live,));table[32+0x1b]=b'\xa8'
   struct.pack_into('<H',records,112+0x50,flags);struct.pack_into('<H',records,112+0x52,0x1234)
   struct.pack_into('<I',records,112+0x58,123 if group_ok else 124);records[112+48]=bytes((typ,));records[112+49]=b'\x02'
   struct.pack_into('<QQQII',cfg,0,ctypes.addressof(text),ctypes.addressof(pp),ctypes.addressof(count),1,1)
   struct.pack_into('<8sHBBI',cfg,48,b'ca01',1,0,2,123)
   # Compute native-only expectation, then reset for one full wrapper invocation.
   original(ctypes.addressof(manager));before_records=bytes(records);before_table=bytes(table)
   struct.pack_into('<I',records,112+0x60,0);table[32+0x1b]=b'\xa8'
   ctypes.memmove(memory+0x8000,bytes(cfg),1072);fn(ctypes.addressof(manager))
   qualified=stage=='ca01' and group_ok and budget_ok and flags in (0,1) and pending<=12 and typ==10
   expected=bytearray(before_records);expected_table=bytearray(before_table)
   if qualified and pending:
    struct.pack_into('<I',expected,112+0x60,live+pending);expected_table[32+0x1b]&=0xfe
   if bytes(records)!=bytes(expected) or bytes(table)!=bytes(expected_table):raise ValueError('Native swarm wrapper fixture failed')
   cases+=1
  return dict(passed=True,cases=cases,shipping_wrapper_executed=True,original_aggregation_exactly_once=True,
   compiled_tick_sha256=hashlib.sha256(tick).hexdigest(),native_aggregation_sha256=NATIVE_SHA,
   game_process_opened=False,gameplay_verified=False)
 finally:k.VirtualFree(memory,0,0x8000)

def cs_source(tick,entry,stolen,bindings):
 sample=wrapper(IMAGE,IMAGE+0x20000000,entry)
 text=(L/'FakeAnubisDamageAdapter.cs').read_text().replace('FakeAnubisDamageAdapter','FiniteMosquitoAdapter')
 text=text.replace('const long Factory=0x14784ac54;','const long Factory='+hex(ENTRY)+';')
 a=text.index(' static readonly byte[] Stolen=');b=text.index('\n',a)
 text=text[:a]+' static readonly byte[] Stolen={'+','.join(map(str,stolen))+'};'+text[b:]
 a=text.index(' public static byte[] BuildCave(');b=text.index(' public static byte[] BuildRedirect(',a)
 payload=' static readonly byte[] Wrapper={'+','.join(map(str,sample))+'};\n static readonly byte[] Tick={'+','.join(map(str,tick))+'};\n'
 payload+=' public static byte[] BuildCave(long image,long cave){byte[] b=new byte[0x1000+Tick.Length];Buffer.BlockCopy(Wrapper,0,b,0,Wrapper.Length);'
 for old,replacement in ((IMAGE+0x20008000,'cave+0x8000'),(IMAGE+0x20001000+entry,'cave+0x1000+'+str(entry)),(NATIVE,'image+'+str(NATIVE-IMAGE))):
  pos=0
  while True:
   pos=sample.find(struct.pack('<Q',old),pos)
   if pos<0:break
   payload+=f'Buffer.BlockCopy(BitConverter.GetBytes({replacement}),0,b,{pos},8);';pos+=8
 payload+='Buffer.BlockCopy(Tick,0,b,0x1000,Tick.Length);return b;}\n'
 payload+=' public static byte[] Config(long image){byte[] b={'+','.join(map(str,config(IMAGE,bindings)))+'};'
 for at,value in ((0,STAGE),(8,ENE_TABLE),(16,ENE_COUNT)):
  payload+=f'Buffer.BlockCopy(BitConverter.GetBytes(image+{value-IMAGE}),0,b,{at},8);'
 payload+='return b;}\n'
 text=text[:a]+payload+text[b:]
 a=text.index(' static void SelfTest(');b=text.index(' static IntPtr AllocateNearby',a)
 text=text[:a]+''' static void SelfTest(string folder){Directory.CreateDirectory(folder);foreach(long image in new long[]{ImageBase,0x180000000,0x7ff600000000}){long cave=image+0x20000000;byte[] b=BuildCave(image,cave),c=Config(image),p=BuildRedirect(image,cave);if(c.Length!=1072||b.Length>=0x8000||image+Factory-ImageBase+5+BitConverter.ToInt32(p,1)!=cave)throw new Exception("Finite swarm payload bounds/redirect");for(int i=0;i<3;i++){long expected=image+new long[]{0x1535830,0x154c098,0x154c094}[i];if(BitConverter.ToInt64(c,i*8)!=expected)throw new Exception("Swarm ASLR config");}File.WriteAllBytes(Path.Combine(folder,"swarm-"+image.ToString("x")+".bin"),b);File.WriteAllBytes(Path.Combine(folder,"config-"+image.ToString("x")+".bin"),c);}Console.WriteLine("Finite swarm fixtures passed at three image bases; game not opened.");}
'''+text[b:]
 text=text.replace('new IntPtr(4096),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);','new IntPtr(0x9000),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);')
 menu='if(!Equal(Read(h,image+'+str(STAGE-IMAGE)+',7),System.Text.Encoding.ASCII.GetBytes("ntitle\\0")))throw new Exception("Finite swarm attachment requires the main menu before loading a save");'
 text=text.replace('   allocation=AllocateNearby(h,image);','   '+menu+'\n   allocation=AllocateNearby(h,image);')
 text=text.replace('Write(h,cave,code);if(','Write(h,cave,code);Write(h,cave+0x8000,Config(image));if(!Equal(Read(h,cave+0x8000,1072),Config(image)))throw new Exception("Swarm configuration readback failed");if(')
 text=text.replace('allocation,new IntPtr(4096),PAGE_EXECUTE_READ,','allocation,new IntPtr(0x8000),PAGE_EXECUTE_READ,')
 text=text.replace('   uint entryOld;','   '+menu+'\n   uint entryOld;')
 text=text.replace('Runtime Fake Anubis normal-damage adapter active','Runtime finite Mosquito pending-count adapter active')
 return text

def build(out,selected):
 out=Path(out);runtime=out/'runtime';runtime.mkdir(exist_ok=True)
 bindings=rules(selected);stolen,native=executable_bytes()
 source=runtime/'finite-mosquito.c';source.write_text(C_CODE)
 obj=runtime/'finite-mosquito.obj';env=os.environ.copy()
 env.update(ZIG_LOCAL_CACHE_DIR=str(runtime/'swarm-cache'),ZIG_GLOBAL_CACHE_DIR=str(runtime/'swarm-global-cache'))
 import shutil
 shutil.copyfile(_portable.APP/'precompiled/finite-mosquito.obj',obj)
 tick,entry=coff_image(obj.read_bytes(),'swarm_pending')
 if len(tick)>=0x7000:raise ValueError('Swarm code exceeds allocation')
 tests=selftest(tick,entry,native);save(out/'finite-mosquito-tests.json',tests)
 cs=runtime/'FiniteMosquitoAdapter.cs';cs.write_text(cs_source(tick,entry,stolen,bindings))
 exe=runtime/'FiniteMosquitoAdapter.exe'
 subprocess.run([_portable.compiler(),'/nologo','/platform:x64','/optimize+','/out:'+str(exe),str(cs)],check=True)
 subprocess.run([str(exe),'--self-test',str(runtime/'swarm-fixtures')],check=True)
 proof=dict(helper=exe.name,helper_sha256=sha(exe),entry=hex(ENTRY),native=hex(NATIVE),stolen=stolen.hex(),
  tick_sha256=hashlib.sha256(tick).hexdigest(),tick_entry=entry,source_sha256=hashlib.sha256(C_CODE.encode()).hexdigest(),
  bindings_hex=bindings.hex(),rules=len(bindings)//16,native_particle_capacity_unchanged=True,
  native_callbacks_and_hp_untouched=True,tests=tests,gameplay_verified=False)
 save(out/'finite-mosquito-contract.json',proof)
 return proof

def verify(out,manifest):
 out=Path(out);selected=manifest['mosquito_replacements']['selected'];proof=json.loads((out/'finite-mosquito-contract.json').read_text())
 if proof!=manifest.get('finite_mosquito_runtime'):raise ValueError('Swarm runtime contract differs')
 bindings=rules(selected);stolen,native=executable_bytes()
 if proof['bindings_hex']!=bindings.hex() or proof['rules']!=len(bindings)//16 or proof['stolen']!=stolen.hex() or proof['entry']!=hex(ENTRY) or proof['native']!=hex(NATIVE):raise ValueError('Swarm runtime bindings differ')
 if (out/'runtime/finite-mosquito.c').read_text()!=C_CODE or proof['source_sha256']!=hashlib.sha256(C_CODE.encode()).hexdigest():raise ValueError('Swarm native source differs')
 tick,entry=coff_image((out/'runtime/finite-mosquito.obj').read_bytes(),'swarm_pending')
 if proof['tick_sha256']!=hashlib.sha256(tick).hexdigest() or proof['tick_entry']!=entry:raise ValueError('Swarm compiled payload differs')
 if (out/'runtime/FiniteMosquitoAdapter.cs').read_text()!=cs_source(tick,entry,stolen,bindings):raise ValueError('Swarm attachment source differs')
 exe=out/'runtime/FiniteMosquitoAdapter.exe'
 if sha(exe)!=proof['helper_sha256'] or tick not in exe.read_bytes():raise ValueError('Swarm executable payload differs')
 if proof['tests']!=json.loads((out/'finite-mosquito-tests.json').read_text()) or not proof['tests']['passed'] or proof['tests']['compiled_tick_sha256']!=proof['tick_sha256']:raise ValueError('Swarm native tests differ')
 return dict(passed=True,rules=proof['rules'],native_fixture_cases=proof['tests']['cases'],gameplay_verified=False)
