import portable_paths as _portable
"""Scoped experimental Valley controller, compiled without game-file patches.

The original post-update and native ground AI still execute. Success remains
the native HP/death animation/164c callback path; this helper never calls it.
"""
import hashlib,json,os,struct,subprocess
from pathlib import Path
from archive_tools import L,sha,save
IMAGE=0x140000000;ENTRY=0x140772d10;NATIVE=0x1498ed480
STAGE=0x141535830;PLAYER=0x14156d710;VTABLE=0x140d8a0c8;GROUND=0x14076c410
EXE_SHA='b96c63f680712651d92933d896ec65aeb95788c19857dd7114526cf7ccdc3b92'
C_CODE=r'''
typedef unsigned char u8; typedef unsigned short u16;
typedef unsigned int u32; typedef unsigned long long u64;
typedef struct {u64 stage,player,vtable,ground;u32 actor_id,enabled;u64 tracked;
 u32 serial,spawns,blocks,tethers,recoveries,pad;} Config;
#define U32(a,o) (*(u32*)((u8*)(a)+(o)))
#define U64(a,o) (*(u64*)((u8*)(a)+(o)))
#define F(a,o) (*(float*)((u8*)(a)+(o)))
static int finite(float f){union{float f;u32 u;}x;x.f=f;return (x.u&0x7fffffff)<0x7f800000;}
static int flight(u32 s){return s==2||s==14||(s>=37&&s<=40);}
static void request(void*a,u32 state){
 if(U64(a,0x12c8))((void(*)(void*,u32))U64(a,0x12c8))(a,U32(a,0x12a4));
 U64(a,0x12c8)=0;((u8*)a)[0x129c]=1;U32(a,0x12a4)=state;U32(a,0xbec)|=4;
}
static void body(void*a){
 u64 m=U64(a,0x80),p=U64(a,0x1458),mc=U64(a,0x88),pc=U64(a,0x14a0);
 if(!m||!p||!mc||!pc)return;
 *(u16*)(m+0xea)&=0xfffe;*(u16*)(p+0xea)|=1;
 *(u32*)(mc+0x10)&=~2u;*(u32*)(pc+0x10)|=2;
 U32(a,0xbe8)&=~4u;U32(a,0x14a8)=~0u;
}
void valley_tick(void*a,Config*c,u32 post){
 const char*s=(const char*)c->stage;
 if(!c->enabled||s[0]!='c'||s[1]!='y'||s[2]!='0'||s[3]!='2'||s[4])return;
 if(U64(a,0)!=c->vtable||U32(a,0x78)!=c->actor_id||((u8*)a)[0x9b]!=13)return;
 // Never change damage, death state, native callbacks or cinematic actors.
 if((int)U32(a,0xc20)<=0||U32(a,0x12a0)==13||U32(a,0x12a4)==13||
    (U64(a,0x1450)&0x70000000))return;
 void*p=*(void**)c->player;if(!p)return;
 float px=F(p,0x980),py=F(p,0x984),pz=F(p,0x988);
 float x=F(a,0x980),y=F(a,0x984),z=F(a,0x988);
 if(!finite(px)||!finite(py)||!finite(pz)||!finite(x)||!finite(y)||!finite(z))return;
 int first=!post&&(c->tracked!=(u64)a||c->serial!=U32(a,8));
 if(first){c->tracked=(u64)a;c->serial=U32(a,8);c->spawns++;request(a,0);}
 // Native phase two is the humanoid combat controller; bit200 protects the
 // original Mars phase-one story transition. Bit1 chooses the close bias.
 U64(a,0x1658)=c->ground;U32(a,0x15d4)=(U32(a,0x15d4)&~0x202u)|1;
 if(U32(a,0xbe8)&4){body(a);c->recoveries++;request(a,0);}
 if(flight(U32(a,0x12a4))||flight(U32(a,0x12a0))){request(a,0);c->blocks++;}
 float dx=x-px,dz=z-pz,dy=y-py,d2=dx*dx+dz*dz;
 if(first||d2>422500.0f||dy>180.0f||dy< -180.0f){
  if(first){dx=F(p,0x970);dz=F(p,0x978);d2=dx*dx+dz*dz;
   if(!finite(d2)||d2<0.001f){dx=0;dz=1;d2=1;}
  }
  float radius=first?360.0f:600.0f;
  if(d2>0.001f){float scale=radius/__builtin_sqrtf(d2);x=px+dx*scale;z=pz+dz*scale;}
  else{x=px;z=pz+radius;}
  y=first?py:(dy>160?py+160:(dy< -160?py-160:y));
  F(a,0x980)=x;F(a,0x984)=y;F(a,0x988)=z;
  F(a,0xb60)=x;F(a,0xb64)=y;F(a,0xb68)=z;
  F(a,0x1720)=x;F(a,0x1724)=y;F(a,0x1728)=z;
  F(a,0xaa0)=0;F(a,0xaa4)=0;F(a,0xaa8)=0;c->tethers++;
 }
 // Constrain the native movement destination as well as actual separation.
 dx=F(a,0x1550)-px;dy=F(a,0x1554)-py;dz=F(a,0x1558)-pz;d2=dx*dx+dz*dz;
 if(finite(d2)&&finite(dy)&&(d2>422500||dy>180||dy< -180)){
  F(a,0x1550)=x;F(a,0x1554)=y;F(a,0x1558)=z;
 }
}
'''

def coff_image(data,entry_symbol='valley_tick'):
 """Link only local .text/.rdata REL32 constants; reject external references."""
 machine,n,_,sympos,nsym,opt,_=struct.unpack_from('<HHIIIHH',data)
 if machine!=0x8664:raise ValueError('Expected AMD64 object')
 strings=data[sympos+18*nsym:];symbols={};i=0
 while i<nsym:
  p=sympos+i*18;name=data[p:p+8]
  if name[:4]==bytes(4):at=struct.unpack_from('<I',name,4)[0];name=strings[at:].split(b'\0')[0]
  symbols[i]=(name.rstrip(b'\0').decode(),*struct.unpack_from('<Ih',data,p+8))
  i+=1+data[p+17]
 sections={};image=bytearray()
 for i in range(n):
  p=20+opt+i*40;name=data[p:p+8].split(b'\0')[0].decode()
  size,raw,reloc=struct.unpack_from('<III',data,p+16);nr=struct.unpack_from('<H',data,p+32)[0]
  if name not in ('.text','.rdata'):continue
  image.extend(bytes((-len(image))%16));base=len(image);image.extend(data[raw:raw+size])
  sections[i+1]=(base,size,reloc,nr)
 for number,(base,size,reloc,nr) in sections.items():
  for i in range(nr):
   at,symbol,kind=struct.unpack_from('<IIH',data,reloc+i*10)
   name,value,target_section=symbols[symbol]
   if kind not in range(4,10) or target_section not in sections:raise ValueError('Unqualified COFF reference: '+name)
   addend=struct.unpack_from('<i',image,base+at)[0]
   struct.pack_into('<i',image,base+at,sections[target_section][0]+value+addend-(base+at+4+(kind-4)))
 entry=next(sections[sec][0]+v for name,v,sec in symbols.values() if name==entry_symbol)
 return bytes(image),entry

def wrapper(image,cave,entry):
 # Native post-update takes RCX only and returns void. Preserve RBX, stack
 # alignment and shadow space; run scoped checks before and after original AI.
 b=bytes.fromhex('53 4883ec40 4889cb 48ba')+struct.pack('<Q',cave+0x8000)
 b+=bytes.fromhex('4531c0 48b8')+struct.pack('<Q',cave+0x1000+entry)+bytes.fromhex('ffd0 4889d9 48b8')
 b+=struct.pack('<Q',image+NATIVE-IMAGE)+bytes.fromhex('ffd0 4889d9 48ba')+struct.pack('<Q',cave+0x8000)
 b+=bytes.fromhex('41b801000000 48b8')+struct.pack('<Q',cave+0x1000+entry)+bytes.fromhex('ffd0 4883c440 5b c3')
 return b

def selftest(tick,entry,actor_id):
 import ctypes,itertools
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.VirtualAlloc.restype=ctypes.c_void_p;k.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_uint32]
 k.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32]
 mem=k.VirtualAlloc(None,len(tick)+4096,0x3000,0x40);assert mem
 cases=0
 try:
  ctypes.memmove(mem,tick,len(tick));fn=ctypes.WINFUNCTYPE(None,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint32)(mem+entry)
  for stage,state,hp,correct in itertools.product(('cy02','cy02x','vc01','wn01','ba02','ef01'),range(42),(0,100),(False,True)):
   actor=ctypes.create_string_buffer(0x2000);player=ctypes.create_string_buffer(0x2000);s=ctypes.create_string_buffer(stage.encode()+b'\0')
   pp=ctypes.c_void_p(ctypes.addressof(player));config=ctypes.create_string_buffer(72)
   struct.pack_into('<QQQQII',config,0,ctypes.addressof(s),ctypes.addressof(pp),VTABLE,GROUND,actor_id,1)
   struct.pack_into('<Q',actor,0,VTABLE);struct.pack_into('<I',actor,8,123)
   struct.pack_into('<I',actor,0x78,actor_id if correct else actor_id^1);actor[0x9b]=b'\x0d'
   struct.pack_into('<I',actor,0xc20,hp);struct.pack_into('<II',actor,0x12a0,state,state)
   struct.pack_into('<I',actor,0x164c,0x12345678);struct.pack_into('<I',actor,0x1430,0xabcdef)
   struct.pack_into('<I',actor,0x15d4,0x1221)
   struct.pack_into('<fff',actor,0x980,3000,2000,4000);struct.pack_into('<fff',actor,0x1550,8000,9000,10000)
   struct.pack_into('<fff',player,0x980,10,20,30);struct.pack_into('<f',player,0x978,1)
   before=bytes(actor);fn(ctypes.addressof(actor),ctypes.addressof(config),0)
   eligible=stage=='cy02' and correct and hp>0 and state!=13
   if not eligible:assert bytes(actor)==before
   else:
    x,y,z=struct.unpack_from('<fff',actor,0x980);assert abs(x-10)<.01 and abs(y-20)<.01 and abs(z-390)<.01
    assert struct.unpack_from('<Q',actor,0x1658)[0]==GROUND
    assert struct.unpack_from('<I',actor,0x15d4)[0]&0x203==1
    assert struct.unpack_from('<I',actor,0x12a4)[0]==0
    # Simulate a native AI request to enter aircraft mode after pre-update.
    struct.pack_into('<I',actor,0x12a4,39);fn(ctypes.addressof(actor),ctypes.addressof(config),1)
    assert struct.unpack_from('<I',actor,0x12a4)[0]==0
   assert struct.unpack_from('<I',actor,0xc20)[0]==hp
   assert struct.unpack_from('<I',actor,0x164c)[0]==0x12345678
   assert struct.unpack_from('<I',actor,0x1430)[0]==0xabcdef
   cases+=1
  return dict(passed=True,cases=cases,compiled_tick_sha256=hashlib.sha256(tick).hexdigest(),other_stages_and_actors_unchanged=True,
   hp_death_state_and_completion_callback_preserved=True,game_process_opened=False,gameplay_verified=False)
 finally:k.VirtualFree(mem,0,0x8000)

def build(out,rows):
 out=Path(out);runtime=out/'runtime';runtime.mkdir(exist_ok=True)
 target=next((r for r in rows if r['stage']=='cy02' and r['identity']=='Vic Viper'),None)
 if target is None:raise ValueError('Valley helper requires a declared Vic Viper replacement')
 identity=target['sites'][0]['source_actor_id'];assert len(target['sites'])==1
 assert identity==0xffff367b and target['sites'][0]['source_completion_callback']==1181,'Valley must match the observed cy02 actor/callback'
 source=runtime/'valley-viper.c';source.write_text(C_CODE)
 env=os.environ.copy();env.update(ZIG_LOCAL_CACHE_DIR=str(runtime/'valley-cache'),ZIG_GLOBAL_CACHE_DIR=str(runtime/'valley-global-cache'))
 obj=runtime/'valley-viper.obj'
 subprocess.run([str(L/'tools/zig-windows-x86_64-0.13.0/zig.exe'),'cc','-target','x86_64-windows-gnu','-O2','-ffreestanding','-fno-stack-protector','-fno-asynchronous-unwind-tables','-fno-math-errno','-c',str(source),'-o',str(obj)],env=env,check=True)
 tick,entry=coff_image(obj.read_bytes());assert len(tick)<0x7000
 tests=selftest(tick,entry,identity);save(out/'valley-viper-tests.json',tests)
 exe=Path(str(_portable.game() / 'Zoe2Mars.exe')).read_bytes()
 assert hashlib.sha256(exe).hexdigest()==EXE_SHA
 pe=struct.unpack_from('<I',exe,60)[0];st=pe+24+struct.unpack_from('<H',exe,pe+20)[0]
 sections=[struct.unpack_from('<IIII',exe,st+40*i+8) for i in range(struct.unpack_from('<H',exe,pe+6)[0])]
 at=next(r+ENTRY-IMAGE-v for vs,v,rs,r in sections if v<=ENTRY-IMAGE<v+rs)
 stolen=exe[at:at+5];assert stolen[0]==0xe9 and ENTRY+5+struct.unpack_from('<i',stolen,1)[0]==NATIVE
 sample=wrapper(IMAGE,IMAGE+0x20000000,entry)
 text=(L/'FakeAnubisDamageAdapter.cs').read_text().replace('FakeAnubisDamageAdapter','ValleyViperAdapter')
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
 payload+=' public static byte[] Config(long image){List<byte>b=new List<byte>();'
 for value in (STAGE,PLAYER,VTABLE,GROUND):payload+=f'b.AddRange(BitConverter.GetBytes(image+{value-IMAGE}));'
 payload+=f'b.AddRange(BitConverter.GetBytes((uint){identity}));b.AddRange(BitConverter.GetBytes((uint)1));b.AddRange(new byte[32]);return b.ToArray();}}\n'
 text=text[:a]+payload+text[b:]
 a=text.index(' static void SelfTest(');b=text.index(' static IntPtr AllocateNearby',a)
 text=text[:a]+''' static void SelfTest(string folder){Directory.CreateDirectory(folder);foreach(long image in new long[]{ImageBase,0x180000000,0x7ff600000000}){long cave=image+0x20000000;byte[] b=BuildCave(image,cave);if(Config(image).Length!=72||b.Length>=0x8000)throw new Exception("Valley payload bounds");File.WriteAllBytes(Path.Combine(folder,"valley-"+image.ToString("x")+".bin"),b);}Console.WriteLine("Valley payload fixture only; game not opened.");}
'''+text[b:]
 text=text.replace('new IntPtr(4096),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);','new IntPtr(0x9000),MEM_COMMIT|MEM_RESERVE,PAGE_READWRITE);')
 text=text.replace('Write(h,cave,code);if(','Write(h,cave,code);Write(h,cave+0x8000,Config(image));if(!Equal(Read(h,cave+0x8000,72),Config(image)))throw new Exception("Valley configuration readback failed");if(')
 text=text.replace('allocation,new IntPtr(4096),PAGE_EXECUTE_READ,','allocation,new IntPtr(0x8000),PAGE_EXECUTE_READ,')
 text=text.replace('Runtime Fake Anubis normal-damage adapter active','Runtime Valley-only Vic Viper close-combat test adapter active')
 cs=runtime/'ValleyViperAdapter.cs';cs.write_text(text)
 subprocess.run([_portable.compiler(),'/nologo','/platform:x64','/optimize+','/out:'+str(runtime/'ValleyViperAdapter.exe'),str(cs)],check=True)
 proof=dict(stage='cy02',actor_id=identity,helper='ValleyViperAdapter.exe',helper_sha256=sha(runtime/'ValleyViperAdapter.exe'),
  native_original_post_update=hex(NATIVE),entry=hex(ENTRY),stolen=stolen.hex(),tick_sha256=hashlib.sha256(tick).hexdigest(),tick_entry=entry,
  source_sha256=hashlib.sha256(C_CODE.encode()).hexdigest(),spawn_distance=360,max_horizontal_distance=650,max_vertical_distance=180,
  blocked_flight_states=[2,14,37,38,39,40],native_ground_ai=hex(GROUND),native_death_and_callback_untouched=True,
  callback=target['sites'][0]['source_completion_callback'],gameplay_verified=False)
 proof['native_fixture']=tests
 save(out/'valley-viper-contract.json',proof)
 return tick,entry,proof

def verify(package,manifest,rows):
 p=Path(package);proof=json.loads((p/'valley-viper-contract.json').read_text())
 if proof!=manifest.get('valley_viper_test'):raise ValueError('Valley contract differs from manifest')
 target=next(r for r in rows if r['stage']=='cy02')
 if target['identity']!='Vic Viper' or len(target['sites'])!=1:raise ValueError('Unqualified Valley destination')
 site=target['sites'][0]
 if (proof['stage'],proof['actor_id'],proof['callback'])!=('cy02',site['source_actor_id'],site['source_completion_callback']):raise ValueError('Valley actor/callback binding differs')
 if (site['source_actor_id'],site['source_completion_callback'],site['source_call'])!=(0xffff367b,1181,3744):raise ValueError('Valley does not match the live cy02 source encounter')
 if (p/'runtime/valley-viper.c').read_text()!=C_CODE:raise ValueError('Valley native source differs')
 if proof['source_sha256']!=hashlib.sha256(C_CODE.encode()).hexdigest():raise ValueError('Valley source provenance differs')
 tick,entry=coff_image((p/'runtime/valley-viper.obj').read_bytes())
 if proof['tick_sha256']!=hashlib.sha256(tick).hexdigest() or proof['tick_entry']!=entry:raise ValueError('Valley compiled payload differs')
 exe=p/'runtime/ValleyViperAdapter.exe'
 if proof['helper_sha256']!=sha(exe) or tick not in exe.read_bytes():raise ValueError('Valley executable payload mismatch')
 tests=json.loads((p/'valley-viper-tests.json').read_text())
 if tests!=proof['native_fixture'] or not tests['passed'] or tests['compiled_tick_sha256']!=proof['tick_sha256']:raise ValueError('Valley fixture proof differs')
 return dict(passed=True,stage='cy02',actor_id=proof['actor_id'],fixture_cases=tests['cases'],gameplay_verified=False)
