import portable_paths as _portable
"""Relocatable SCX support for Nephtis replacements, based on the passed ca02 test.
Caller supplies arena placements; only the snowy placement has gameplay evidence.
No installation or boss/phase replacement is performed by this module.
"""
import hashlib,math,struct
from scx_first_boss_handoff import literal,native,procedure
POLE_MODEL='fc01_grab_pole.mdz'
POLE_ASSETS=('389b56cb.tex','91da1b63.mdz')
SNOW_POLES=((-14500.,1000.,11000.),(-12000.,1000.,10500.),(-9500.,1000.,11000.),(-9000.,1000.,13500.),(-9500.,1000.,15500.),(-14500.,1000.,15500.),(-15000.,1000.,13500.),(-15000.,1000.,17000.))
SNOW_CUBE=(-12000.,1000.,16000.)
def address(value):
 if type(value)!=int or not 0<=value<=0xffffffff:raise ValueError('SCX address/identifier outside uint32')
 return value
def position(xyz):
 if len(xyz)!=3 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e7 for v in xyz):raise ValueError('Expected three finite arena coordinates')
 return tuple(float(v) for v in xyz)
def fp(v):return literal(0xc1,struct.unpack('<I',struct.pack('<f',v))[0])
def actor_ids(seed,stage,slot,count,reserved=()):
 if not isinstance(seed,str) or not seed or not isinstance(stage,str) or not stage or not isinstance(slot,str) or not slot:raise ValueError('Seed, stage and slot must be nonempty strings')
 if type(count)!=int or not 1<=count<=64:raise ValueError('Unsupported support actor count')
 used={address(v) for v in reserved};result=[];counter=0
 while len(result)<count:
  key='\0'.join(('zoe2-support-v1',seed,stage,slot,str(counter))).encode();counter+=1
  value=int.from_bytes(hashlib.sha256(key).digest()[:4],'little')
  if value not in used and value not in (0,0xffffffff):used.add(value);result.append(value)
 return result
def pole_wrapper(entry,continuation,positions,identifiers):
 address(entry);address(continuation);positions=tuple(position(x) for x in positions);identifiers=tuple(address(x) for x in identifiers)
 if not 1<=len(positions)<=32 or len(positions)!=len(identifiers) or len(set(identifiers))!=len(identifiers):raise ValueError('One unique actor identifier per pole required')
 config=native(0x911f0cb1,[literal(0xc0,v) for v in (0x91da1b63,80,6000,800)])
 def emit(string):
  calls=[]
  for xyz,ident in zip(positions,identifiers):
   args=[literal(0xc0,ident),bytes((0x80,0xb0,0xc2))+struct.pack('<I',address(string))]+[fp(v) for v in xyz]+[literal(0xc0,0)]*3
   calls.append(native(0xffffea2c,args))
  return config+b''.join(calls)+procedure(continuation)+b'\x89'
 string=address(entry+len(emit(0)));body=emit(string);data=body+POLE_MODEL.encode()+b'\0';address(entry+len(data))
 return data,dict(entry=entry,code_end=string,string_offset=string,continuation=continuation,actor_ids=list(identifiers),positions=list(positions),assets=list(POLE_ASSETS))
def gauntlet_cube(entry,continuation,xyz,identifier):
 address(entry);address(continuation);address(identifier);xyz=position(xyz)
 args=[literal(0xc0,identifier),b'\xdc',literal(0xc0,0xc75c22fb),b'\xe3',literal(0xc0,0),b'\xd6',literal(0xc5,0),b'\xe5',literal(0xc0,500),b'\xdf']+[fp(v) for v in xyz]
 pickup=address(entry+len(native(0x2be4b123,args))+6);args[6]=literal(0xc5,pickup)
 body=native(0x2be4b123,args)+procedure(continuation)+b'\x89'
 reward=literal(0xc0,1)+literal(0xc0,3)+b'\x8b\xb3'+struct.pack('<I',0x774d00ea)+b'\x89';data=body+reward;address(entry+len(data))
 return data,dict(entry=entry,pickup_callback=pickup,continuation=continuation,actor_id=identifier,position=xyz,reward_index=3,retains_healing=True)
def append_nephtis_support(original,redirect,expected_target,seed,stage,slot,poles,cube,reserved_ids=()):
 """Wrap an existing verified boss procedure; offsets and prior callbacks stay intact."""
 original=bytes(original);address(redirect);address(expected_target)
 if redirect+5>len(original) or expected_target>=len(original) or original[redirect:redirect+5]!=procedure(expected_target):raise ValueError('Existing boss procedure does not match')
 ids=actor_ids(seed,stage,slot,len(poles)+1,reserved_ids)
 # Reject accidental aliases even when the caller omitted an existing actor ID.
 if any(struct.pack('<I',ident) in original for ident in ids):raise ValueError('Support identifier appears in original script; supply all reserved actor IDs')
 cube_body,cube_info=gauntlet_cube(len(original),expected_target,cube,ids[-1])
 pole_body,pole_info=pole_wrapper(len(original)+len(cube_body),len(original),poles,ids[:-1])
 result=bytearray(original);result[redirect:redirect+5]=procedure(pole_info['entry']);result.extend(cube_body+pole_body)
 return bytes(result),dict(format=1,source_sha256=hashlib.sha256(original).hexdigest(),output_sha256=hashlib.sha256(result).hexdigest(),redirect=redirect,boss_continuation=expected_target,cube=cube_info,poles=pole_info,arena_placement_gameplay_verified=False,full_health_runtime_adapter_required=True)
