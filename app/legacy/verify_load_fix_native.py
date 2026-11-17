import portable_paths as _portable
import sys,struct,json,random
from pathlib import Path
root=Path.cwd();sys.path=[p for p in sys.path if p and Path(p).resolve()!=root]
import ctypes
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong,ctypes.c_ulong];k.VirtualAlloc.restype=ctypes.c_void_p
k.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong]
a=k.VirtualAlloc(None,0x10000,0x3000,0x40);assert a
folder=root/'Load-Fix-Verification';checks=0
exe=Path(str(_portable.game() / 'Zoe2Mars.exe')).read_bytes()
p=struct.unpack_from('<I',exe,60)[0];ns=struct.unpack_from('<H',exe,p+6)[0];os=struct.unpack_from('<H',exe,p+20)[0];sections=[struct.unpack_from('<IIII',exe,p+24+os+40*i+8) for i in range(ns)]
def raw(va):return next(r+va-0x140000000-v for vs,v,s,r in sections if v<=va-0x140000000<v+s)
def put(off,data):ctypes.memmove(a+off,bytes(data),len(data))
def ck(v):
 global checks
 assert v;checks+=1
try:
 ck(exe[raw(0x144caac30):raw(0x144caac30)+5]==bytes.fromhex('5641564157'))
 ck(exe[raw(0x1462ddcc6):raw(0x1462ddcc6)+7]==bytes.fromhex('488b05839626fb'))
 music=bytearray((folder/'music-cave.bin').read_bytes());struct.pack_into('<i',music,len(music)-4,0x1000-len(music));put(0,music)
 put(0x1000,bytes.fromhex('89d0415f415e5ec3'))
 fn=ctypes.WINFUNCTYPE(ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32)(a)
 mapping={int(k):v for k,v in json.loads((root/'music-sector-remap.json').read_text()).items()}
 rng=random.Random(7331);values=list(mapping)+list(mapping.values())+[0,0xffffffff,22,1202]+[rng.randrange(0x40000000) for _ in range(1000)]
 for v in values:ck(fn(None,v)==mapping.get(v,v))
 # Run the original native bank-table search with the remapped EDX.
 # The native search begins after the security-cookie prologue. Replace its
 # failure exit with a test sentinel and its success continuation with ESI.
 lookup=bytearray(exe[raw(0x144caac4e):raw(0x144caacb8)])
 failure=0x144caacb3-0x144caac4e
 lookup[failure:failure+5]=b'\xe9'+struct.pack('<i',0x3500-(0x3000+failure+5))
 put(0x3000,lookup);put(0x3000+len(lookup),bytes.fromhex('89f0415f415e5ec3'))
 put(0x3500,bytes.fromhex('b8ffffffff415f415e5ec3'))
 struct.pack_into('<i',music,len(music)-4,0x3000-len(music));put(0,music)
 obj=ctypes.create_string_buffer(0x2400)
 for moved,original in mapping.items():
  ctypes.memset(ctypes.addressof(obj),0,len(obj));struct.pack_into('<I',obj,0x1670,1)
  struct.pack_into('<10i',obj,0x1674,original,*([-1]*9))
  ck(fn(obj,moved)==original)
 # Guard: replay the captured original setter when actor exists, return when absent.
 code=bytearray((folder/'nephtis-callback-cave.bin').read_bytes());off=0x4000
 struct.pack_into('<i',code,3,0x5000-(off+7));struct.pack_into('<i',code,len(code)-4,0x5100-(off+len(code)));put(off,code)
 put(0x5100,exe[raw(0x1462ddccd):raw(0x1462ddccd)+7])
 # Wrapper sets carry and records flags after the call; both paths must preserve it.
 put(0x5200,b'\xf9\xe8'+struct.pack('<i',0x4000-(0x5200+6))+bytes.fromhex('9c58c3'))
 guard=ctypes.WINFUNCTYPE(ctypes.c_uint64,ctypes.c_void_p,ctypes.c_uint32)(a+0x5200)
 actor=ctypes.create_string_buffer(0x2000)
 for ptr in [0,ctypes.addressof(actor)]:
  put(0x5000,struct.pack('<Q',ptr))
  for callback in [0,1925,1847,0xffffffff]:
   struct.pack_into('<I',actor,0x15b0,0x11223344);struct.pack_into('<I',actor,0x163c,72641)
   ck(guard(None,callback)&1==1)
   ck(struct.unpack_from('<I',actor,0x15b0)[0]==(callback if ptr else 0x11223344))
   ck(struct.unpack_from('<I',actor,0x163c)[0]==72641)
 report=dict(passed=True,checks=checks,music_mappings=len(mapping),actual_native_bank_lookup_cases=len(mapping),captured_crash_null_actor_tested=True,original_nephtis_setter_preserved=True,replacement_completion_untouched=True,gameplay_verified=False)
 (folder/'native-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
finally:k.VirtualFree(a,0,0x8000)
