import portable_paths as _portable
"""Verified story spawn contracts. Decoding does not authorize replacement."""
import struct
from scx_call_arguments import call_arguments,UnresolvedArguments
NEPHTIS_STORY=0xffff367b
class UnsupportedBossContract(ValueError):pass
def decode_nephtis_story(data,offset):
 args=call_arguments(data,offset)
 if len(args)<6:raise UnsupportedBossContract('Nephtis requires six base arguments')
 if any(a['kind']!=0xc0 or a['value'] is None for a in args[:2]):
  raise UnsupportedBossContract('Actor identifier/type must be literal integers')
 if args[1]['value']!=11:raise UnsupportedBossContract('Expected original Nephtis actor type 11')
 result=dict(actor_id=args[0]['value'],actor_type=11,phase=7,phase_option_present=False,script_callback=None,arguments=args,coordinate_values=[])
 for arg in args[2:6]:
  result['coordinate_values'].append(struct.unpack('<f',struct.pack('<I',arg['value']))[0] if arg['kind']==0xc1 and arg['value'] is not None else None)
 i=6;seen=set()
 while i<len(args):
  tag=args[i]['kind']
  if tag not in (0xdf,0xe3) or tag in seen or i+1>=len(args):
   raise UnsupportedBossContract('Unsupported/duplicate Nephtis option')
  seen.add(tag);value=args[i+1]
  if tag==0xdf:
   if value['kind']!=0xc5 or value['value'] is None:raise UnsupportedBossContract('Expected script callback offset')
   result['script_callback']=value['value']
  else:
   if value['kind']!=0xc0 or value['value'] not in range(8):raise UnsupportedBossContract('Unsupported phase')
   result['phase']=value['value'];result['phase_option_present']=True
  i+=2
 result['native_health_multiplier']=0.5 if result['phase']==3 else 1.0
 result['replacement_ready']=False
 return result

ARDJET_STORY=0xfffedd53
INHERT_STORY={0xdfedfdb4:0,0xbfd9f8ec:1}
def decode_story_boss(data,offset,command):
 if command==NEPHTIS_STORY:return decode_nephtis_story(data,offset)
 if command in ANUBIS_STORY:return decode_anubis_story(data,offset,command)
 if command==VIC_VIPER_STORY:return decode_vic_viper_story(data,offset)
 if command in LATE_ANUBIS_STORY:return decode_late_anubis_story(data,offset,command)
 if command not in (ARDJET_STORY,*INHERT_STORY):raise UnsupportedBossContract('Unverified boss creation command')
 args=call_arguments(data,offset);expected=9 if command==ARDJET_STORY else 7
 if len(args)!=expected and not (command in INHERT_STORY and len(args)==14):raise UnsupportedBossContract('Unexpected boss argument count')
 if any(x['kind']!=0xc0 or x['value'] is None for x in args[:2]):raise UnsupportedBossContract('Actor identity/variant must be literal integers')
 for arg in args[2:6]:
  if arg['kind'] not in (0xc0,0xc1):raise UnsupportedBossContract('Unverified coordinate expression')
 callbacks=args[6:9] if command==ARDJET_STORY else args[6:7]
 if any(x['kind']!=0xc5 or x['value'] is None for x in callbacks):raise UnsupportedBossContract('Expected script callback offsets')
 if command==ARDJET_STORY:
  variant=args[1]['value']
  if variant not in (0,1):raise UnsupportedBossContract('Unverified Ardjet variant')
  return dict(boss='Ardjet',actor_id=args[0]['value'],actor_type=14,variant=variant,variant_explicit=True,script_callbacks=[dict(offset=x['value'],argument_offset=x['offset'],actor_field=hex(field),purpose_verified=False) for x,field in zip(callbacks,[0x1480,0x1484,0x1488])],arguments=args,replacement_ready=False)
 if args[1]['value']!=12:raise UnsupportedBossContract('Expected Inhert actor type 12')
 bounds=None
 if len(args)==14:
  import math
  if args[7]['kind']!=0xd1:raise UnsupportedBossContract('Expected Inhert movement bounds option')
  bounds=[]
  for arg in args[8:14]:
   if arg['kind'] not in (0xc0,0xc1) or arg['value'] is None:raise UnsupportedBossContract('Bounds must be literal numbers')
   value=struct.unpack('<f' if arg['kind']==0xc1 else '<i',struct.pack('<I',arg['value']))[0]
   if not math.isfinite(value):raise UnsupportedBossContract('Nonfinite bounds')
   bounds.append(value)
  if any(bounds[i]>=bounds[i+3] for i in range(3)):raise UnsupportedBossContract('Inverted or empty bounds')
 return dict(boss='Inhert',actor_id=args[0]['value'],actor_type=12,variant=INHERT_STORY[command],source_initial_health_ratio=0.5 if INHERT_STORY[command] else 1.0,script_callbacks=[dict(offset=callbacks[0]['value'],argument_offset=callbacks[0]['offset'],actor_field=hex(0x14f0),purpose_verified=False)],arguments=args,arena_bounds=bounds,replacement_ready=False)

ANUBIS_STORY={0xdfe3a990:'Bahram Anubis',0xef217f76:'Compressed-space Anubis',0xfa106dc5:'Fake Anubis'}
def decode_anubis_story(data,offset,command):
 if command not in ANUBIS_STORY:raise UnsupportedBossContract('Unverified Anubis creation command')
 args=call_arguments(data,offset)
 if len(args)<6:raise UnsupportedBossContract('Anubis requires six base arguments')
 if any(x['kind']!=0xc0 or x['value'] is None for x in args[:2]):raise UnsupportedBossContract('Actor identity/type must be literal integers')
 if args[1]['value']!=9:raise UnsupportedBossContract('Expected original Anubis actor type 9')
 if any(x['kind'] not in (0xc0,0xc1) or x['value'] is None for x in args[2:6]):raise UnsupportedBossContract('Unverified coordinate expression')
 result=dict(boss=ANUBIS_STORY[command],actor_id=args[0]['value'],actor_type=9,arguments=args,script_callbacks=[],encounter_counter_limit=None,replacement_ready=False)
 i=6;seen=set()
 while i<len(args):
  tag=args[i]['kind']
  if tag not in (0xd4,0xdd) or tag in seen or i+1>=len(args):raise UnsupportedBossContract('Unsupported/duplicate Anubis option')
  seen.add(tag);v=args[i+1]
  if tag==0xd4:
   if v['kind']!=0xc5 or v['value'] is None:raise UnsupportedBossContract('Expected script callback offset')
   field=0x13f4 if command==0xdfe3a990 else 0x163c
   result['script_callbacks'].append(dict(offset=v['value'],argument_offset=v['offset'],actor_field=hex(field),purpose_verified=True,purpose='Source encounter completion'))
  else:
   if command!=0xdfe3a990 or v['kind']!=0xc0 or v['value'] is None or v['value']<1:raise UnsupportedBossContract('Unverified Anubis counter option')
   result['encounter_counter_limit']=v['value']
  i+=2
 if not result['script_callbacks']:raise UnsupportedBossContract('No verified source completion callback')
 return result

VIC_VIPER_STORY=0x7fed7b0b
def decode_vic_viper_story(data,offset):
 args=call_arguments(data,offset)
 if len(args)!=8:raise UnsupportedBossContract('Unverified Vic Viper argument count')
 if args[0]['kind']!=0xc0 or args[0]['value'] is None:raise UnsupportedBossContract('Expected literal actor identifier')
 if any(x['kind'] not in (0xc0,0xc1) or x['value'] is None for x in args[1:5]):raise UnsupportedBossContract('Unverified Vic Viper position/heading')
 if args[5]['kind']!=0xc0 or args[5]['value'] is None or args[5]['value']<1:raise UnsupportedBossContract('Expected positive source maximum HP')
 if args[6]['kind']!=0xdf or args[7]['kind']!=0xc5 or args[7]['value'] is None:raise UnsupportedBossContract('Expected source p-option callback')
 return dict(boss='Vic Viper',actor_id=args[0]['value'],actor_type=13,actor_type_implicit=True,source_maximum_health=args[5]['value'],arguments=args,script_callbacks=[dict(offset=args[7]['value'],argument_offset=args[7]['offset'],actor_field='0x164c',purpose_verified=False)],replacement_ready=False)

LATE_ANUBIS_STORY={0xb7d9f1ad:dict(boss='Anubis (fr04g)',actor_type=9,field='0x13e4',option=0xdd),0xef9a96d8:dict(boss='Aumaan Anubis',actor_type=10,field='0x16a8',option=0xdf)}
def decode_late_anubis_story(data,offset,command):
 if command not in LATE_ANUBIS_STORY:raise UnsupportedBossContract('Unverified late Anubis factory')
 spec=LATE_ANUBIS_STORY[command];args=call_arguments(data,offset)
 if len(args)!=10:raise UnsupportedBossContract('Unverified late Anubis argument count')
 if any(x['kind']!=0xc0 or x['value'] is None for x in args[:2]) or args[1]['value']!=spec['actor_type']:raise UnsupportedBossContract('Incorrect source actor type')
 if any(x['kind'] not in (0xc0,0xc1) or x['value'] is None for x in args[2:6]):raise UnsupportedBossContract('Unverified source coordinates')
 if args[6]['kind']!=spec['option'] or args[7]['kind']!=0xc0 or args[7]['value'] is None:raise UnsupportedBossContract('Unverified source phase/counter option')
 value=args[7]['value']
 if command==0xb7d9f1ad and value<1:raise UnsupportedBossContract('Expected positive encounter counter limit')
 if command==0xef9a96d8 and value not in (0,1):raise UnsupportedBossContract('Only observed Aumaan phase options0/1 are verified')
 if args[8]['kind']!=0xd4 or args[9]['kind']!=0xc5 or args[9]['value'] is None:raise UnsupportedBossContract('Expected e-option source callback')
 return dict(boss=spec['boss'],actor_id=args[0]['value'],actor_type=spec['actor_type'],actor_type_namespace='native actor registration; separate from ENE enemy record types',source_option=dict(tag=hex(spec['option']),value=value),source_initial_health=1 if command==0xef9a96d8 and value==1 else (1000 if command==0xef9a96d8 else None),source_initial_state=25 if command==0xef9a96d8 and value==1 else (0 if command==0xef9a96d8 else None),arguments=args,script_callbacks=[dict(offset=args[9]['value'],argument_offset=args[9]['offset'],actor_field=spec['field'],purpose_verified=False)],replacement_ready=False)
