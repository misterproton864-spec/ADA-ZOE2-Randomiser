import portable_paths as _portable
"""Experimental native boss-to-boss emitters; retains source callback addresses.
No foreign AI, actor-command, arena or progression compatibility is implied.
"""
import hashlib,struct
from boss_spawn_contracts import (decode_story_boss,NEPHTIS_STORY,ARDJET_STORY,
 VIC_VIPER_STORY,INHERT_STORY,ANUBIS_STORY,LATE_ANUBIS_STORY)
from scx_bytecode import instructions
from scx_first_boss_handoff import literal,native,procedure,NEPHTIS_CONFIG,TRANSITION_EFFECT

def completion(contract):
 if 'script_callback' in contract:return contract['script_callback']
 callbacks=contract['script_callbacks']
 return callbacks[0]['offset'] if callbacks else None

def coordinates(contract,command):
 return contract['arguments'][1:5] if command==VIC_VIPER_STORY else contract['arguments'][2:6]

def emit_spawn(command,template,identity,coords,callback,noop,arena_bounds=None):
 """Only supported literal/native option frames; no donor script pointers escape."""
 c=decode_story_boss(template['data'],template['offset'],command)
 from boss_donor_initialisation import donor_table,REGISTRATIONS
 table_setup,_=donor_table(template['data'],command)
 if arena_bounds is not None and command not in INHERT_STORY:raise ValueError('Inhert bounds cannot be applied to another boss factory')
 xyz=[coords] if isinstance(coords,bytes) else [literal(a['kind'],a['value']) for a in coords]
 def spawn(args):
  argc=len(args)+(3 if isinstance(coords,bytes) else 0)
  return table_setup+b''.join(args)+bytes([0x84,argc,0x88])+struct.pack('<I',command)
 if command==NEPHTIS_STORY:
  return native(NEPHTIS_CONFIG,[literal(0xc0,11)])+spawn(
   [literal(0xc0,identity),literal(0xc0,11)]+xyz+[b'\xdf',literal(0xc5,callback),b'\xe3',literal(0xc0,3)])
 if command==ARDJET_STORY:
  if c['variant']!=0:raise ValueError('Protected infected Ardjet cannot be a destination')
  return spawn([literal(0xc0,identity),literal(0xc0,0)]+xyz+
   [literal(0xc5,callback),literal(0xc5,noop),literal(0xc5,noop)])
 if command==VIC_VIPER_STORY:
  return spawn([literal(0xc0,identity)]+xyz+[literal(0xc0,c['source_maximum_health']),b'\xdf',literal(0xc5,callback)])
 if command in INHERT_STORY:
  options=[]
  if arena_bounds is not None:
   import math
   if len(arena_bounds)!=6 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in arena_bounds):raise ValueError('Six finite Inhert bounds required')
   if any(arena_bounds[i]>=arena_bounds[i+3] for i in range(3)):raise ValueError('Inverted or empty Inhert bounds')
   options=[b'\xd1']+[literal(0xc1,struct.unpack('<I',struct.pack('<f',v))[0]) for v in arena_bounds]
  return spawn([literal(0xc0,identity),literal(0xc0,12)]+xyz+[literal(0xc5,callback)]+options)
 if command in ANUBIS_STORY:
  opts=[]
  if c['encounter_counter_limit'] is not None:opts=[b'\xdd',literal(0xc0,c['encounter_counter_limit'])]
  setup=native(REGISTRATIONS[command],[literal(0xc0,9)]) if command in REGISTRATIONS else b''
  return setup+spawn([literal(0xc0,identity),literal(0xc0,9)]+xyz+opts+[b'\xd4',literal(0xc5,callback)])
 if command in LATE_ANUBIS_STORY:
  option=c['source_option']
  if command==0xef9a96d8 and option['value']!=0:raise ValueError('Cinematic Aumaan spawn is not a battle destination')
  setup=native(0x019506a4,[literal(0xc0,c['actor_type'])]) if command==0xef9a96d8 else b''
  return setup+spawn([literal(0xc0,identity),literal(0xc0,c['actor_type'])]+xyz+
   [bytes([int(option['tag'],16)]),literal(0xc0,option['value']),b'\xd4',literal(0xc5,callback)])
 raise ValueError('Unsupported destination factory')

def append_mixed_handoff(data,sites,profile,digest,suppress_nephtis_pole_visuals=False,guard_source_fades=False):
 original=bytes(data)
 if hashlib.sha256(original).hexdigest()!=digest:raise ValueError('Source hash mismatch')
 if not sites:raise ValueError('No source sites')
 if len({s['offset'] for s in sites})!=len(sites):raise ValueError('Duplicate source sites')
 if profile['protected']:raise ValueError('Protected destination')
 boundaries={p:(op,raw) for p,op,raw in instructions(original)}
 supported={NEPHTIS_STORY,ARDJET_STORY,VIC_VIPER_STORY,*INHERT_STORY,*ANUBIS_STORY,*LATE_ANUBIS_STORY}
 combat_sites=set()
 for offset,(op,raw) in boundaries.items():
  if op!=0x88:continue
  command=struct.unpack_from('<I',raw,1)[0]
  if command not in supported:continue
  contract=decode_story_boss(original,offset,command)
  if completion(contract) is None:continue
  if command==ARDJET_STORY and contract['variant']!=0:continue
  if command==0xef9a96d8 and contract['source_option']['value']==1:continue
  combat_sites.add(offset)
 if {s['offset'] for s in sites}!=combat_sites:raise ValueError('All source combat phases must be converted together')
 result=bytearray(original);reports=[];visual_overrides=[];registration_overrides=[]
 from boss_donor_initialisation import REGISTRATIONS
 destination_commands={t['command'] for t in profile['templates']}
 if len(destination_commands)==1 and next(iter(destination_commands)) in REGISTRATIONS:
  desired=REGISTRATIONS[next(iter(destination_commands))]
  for p,(op,raw) in boundaries.items():
   if op==0x88 and struct.unpack_from('<I',raw,1)[0] in REGISTRATIONS.values() and struct.unpack_from('<I',raw,1)[0]!=desired:
    previous=struct.unpack_from('<I',raw,1)[0];result[p+1:p+5]=struct.pack('<I',desired)
    registration_overrides.append(dict(offset=p,original_command=f'{previous:08x}',replacement_command=f'{desired:08x}',reason='Prevent a conflicting type-9 boss class from registering before the replacement'))
 # These are animated held-pole visuals, not genuine throwable props. Their
 # update reads the original Nephtis global directly. Keep the source scenes
 # and native argument frames, but stop creating these visuals in a foreign
 # boss encounter. A verified registered RET stub consumes the same native
 # dispatch path without introducing another actor.
 if suppress_nephtis_pole_visuals and profile['boss']!='Nephtis' and all(s['command']==NEPHTIS_STORY for s in sites):
  for p,(op,raw) in boundaries.items():
   if op==0x88 and struct.unpack_from('<I',raw,1)[0]==0x8b45e88f:
    result[p+1:p+5]=struct.pack('<I',0xfffff75a)
    visual_overrides.append(dict(offset=p,original_command='8b45e88f',replacement_command='fffff75a',reason='Source animated pole reads Nephtis-only global actor pointer'))
 for site in sorted(sites,key=lambda s:s['offset']):
  offset,command=site['offset'],site['command']
  if offset not in boundaries or boundaries[offset][0]!=0x88 or struct.unpack_from('<I',original,offset+1)[0]!=command:
   raise ValueError('Source native instruction mismatch')
  source=decode_story_boss(original,offset,command)
  if command==ARDJET_STORY and source['variant']!=0:raise ValueError('Protected source')
  callback=completion(source)
  if callback is None or callback not in boundaries:raise ValueError('Source has no literal completion callback')
  if command==0xef9a96d8 and source['source_option']['value']==1:raise ValueError('Preserve Aumaan cinematic source')
  coords=coordinates(source,command)
  if coords[0]['offset'] is None or coords[-1]['offset'] is None:raise ValueError('Coordinate frame bounds unresolved')
  coord_bytes=original[coords[0]['offset']-3:coords[-1]['offset']+4]
  allowed={0x80,0x81,0x8a,0xb0,0xb1,0xb2,0xb3,0xc0,0xc1,0xc2,0xc3,0xc5,*range(0x90,0x9c),*range(0xa0,0xa8)}
  if any(op not in allowed for _,op,_ in list(instructions(coord_bytes+b'\x8e'))[:-1]):raise ValueError('Coordinate expression has unsupported side effects')
  # A single source fight gets every combat phase of the destination encounter.
  # Multi-spawn sources retain their native phase scheduling and use the corresponding donor phase.
  templates=profile['templates'] if len(sites)==1 else [profile['templates'][min(site.get('phase_index',len(reports)),len(profile['templates'])-1)]]
  # All Nephtis donors are normalized to the same autonomous full-health
  # combat mode. Multiple donor story spawns must not become duplicate rounds
  # in a single source encounter with one set of throwable support objects.
  if len(sites)==1 and all(t['command']==NEPHTIS_STORY for t in templates):
   templates=templates[:1]
  entry=len(result);noop=entry;result.extend(b'\x89');phase_reports=[]
  source_finish=callback
  fade_guard=None
  if guard_source_fades:
   from scx_completion_initialisation import fade_guard_source
   fade_guard=fade_guard_source(original,callback)
  if command==ARDJET_STORY or fade_guard:
   source_finish=len(result)
   if fade_guard:result.extend(fade_guard['bytes'])
   result.extend(procedure(callback))
   if command==ARDJET_STORY:result.extend(native(TRANSITION_EFFECT,[]))
   result.extend(b'\x89')
  next_callback=source_finish
  for index,template in reversed(list(enumerate(templates))):
   phase_entry=len(result)
   identity=source['actor_id'] if index==0 else int.from_bytes(hashlib.sha256(
    (digest+'\0'+profile['encounter']+'\0'+str(offset)+'\0'+str(index)).encode()).digest()[:4],'little')
   if index and struct.pack('<I',identity) in original:raise ValueError('Additional phase actor identity collision')
   code=emit_spawn(template['command'],template,identity,coord_bytes,next_callback,noop,profile.get('arena_bounds'))
   result.extend(code+b'\x89')
   phase_reports.insert(0,dict(entry=phase_entry,end=len(result),command=f"{template['command']:08x}",
    actor_id=identity,callback=next_callback,donor_offset=template['offset']))
   next_callback=phase_entry
  wrapper=len(result)
  result.extend(procedure(next_callback))
  if command==ARDJET_STORY:
   start=source['script_callbacks'][1]['offset']
   if start not in boundaries:raise ValueError('Ardjet start callback boundary mismatch')
   result.extend(procedure(start))
  result.extend(b'\x89');result[offset:offset+5]=procedure(wrapper)
  reports.append(dict(source_call=offset,source_command=f'{command:08x}',source_actor_id=source['actor_id'],
   source_completion_callback=callback,source_completion_bridge=source_finish,
   completion_fade_guard=None if fade_guard is None else {k:v for k,v in fade_guard.items() if k!='bytes'},
   procedure_entry=wrapper,noop_entry=noop,phases=phase_reports,
   coordinates=[dict(kind=a['kind'],value=a['value']) for a in coords],coordinate_expression_bytes=coord_bytes.hex()))
 changed={i for s in sites for i in range(s['offset'],s['offset']+5)}
 changed.update(i for row in visual_overrides for i in range(row['offset']+1,row['offset']+5))
 changed.update(i for row in registration_overrides for i in range(row['offset']+1,row['offset']+5))
 if any(a!=b for i,(a,b) in enumerate(zip(original,result)) if i not in changed):raise ValueError('Unrelated source bytes changed')
 return bytes(result),dict(destination_encounter=profile['encounter'],destination_boss=profile['boss'],sites=reports,
  source_sha256=digest,output_sha256=hashlib.sha256(result).hexdigest(),
  original_prefix_preserved=True,source_visual_overrides=visual_overrides,source_registration_overrides=registration_overrides,foreign_ai_verified=False,source_completion_gameplay_verified=False,
  phase_actor_lifetime_verified=False,arena_verified=False,ready_for_install=False,installed=False)
