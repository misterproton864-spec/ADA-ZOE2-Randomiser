import portable_paths as _portable
"""Experimental native boss-to-boss emitters; retains source callback addresses.
No foreign AI, actor-command, arena or progression compatibility is implied.
"""
import hashlib,struct
import boss_registration_fixes
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

def emit_spawn(command,template,identity,coords,callback,noop,arena_bounds=None,viola_callbacks=None):
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
  variant=c['variant']
  if variant not in (0,1):raise ValueError('Unknown Ardjet variant')
  if variant==1 and viola_callbacks is None:raise ValueError('Full Viola callback bridges required')
  mid,failure=viola_callbacks if variant==1 else (noop,noop)
  return spawn([literal(0xc0,identity),literal(0xc0,variant)]+xyz+
   [literal(0xc5,callback),literal(0xc5,mid),literal(0xc5,failure)])
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
  registration=0x019506a4 if command==0xef9a96d8 else REGISTRATIONS.get(command)
  setup=native(registration,[literal(0xc0,c['actor_type'])]) if registration else b''
  return setup+spawn([literal(0xc0,identity),literal(0xc0,c['actor_type'])]+xyz+
   [bytes([int(option['tag'],16)]),literal(0xc0,option['value']),b'\xd4',literal(0xc5,callback)])
 raise ValueError('Unsupported destination factory')

def append_mixed_handoff(data,sites,profile,digest,suppress_nephtis_pole_visuals=False,guard_source_fades=False,preserved_native_sites=(),site_profiles=None):
 original=bytes(data)
 if hashlib.sha256(original).hexdigest()!=digest:raise ValueError('Source hash mismatch')
 if not sites:raise ValueError('No source sites')
 if len({s['offset'] for s in sites})!=len(sites):raise ValueError('Duplicate source sites')
 if profile['protected']:raise ValueError('Protected destination')
 # A native infected-Ardjet assignment must retain its complete original
 # script, including player setup, recovery, success delay and story scenes.
 if profile.get('full_viola_ai') and len(sites)==1:
  site=sites[0]
  source=decode_story_boss(original,site['offset'],site['command'])
  donor=profile['templates'][0]
  if site['command']==ARDJET_STORY and source['variant']==1 and original==donor['data']:
   callback=completion(source)
   return original,dict(destination_encounter='ef02g',destination_boss='Ardjet',
    native_viola_preserved=True,source_sha256=digest,output_sha256=digest,
    original_prefix_preserved=True,source_visual_overrides=[],source_registration_overrides=[],
    sites=[dict(source_call=site['offset'],source_command=f'{ARDJET_STORY:08x}',
     source_actor_id=source['actor_id'],source_completion_callback=callback,
     source_completion_bridge=callback,phases=[],viola_callbacks=None)],
    foreign_ai_verified=False,source_completion_gameplay_verified=False,
    phase_actor_lifetime_verified=False,arena_verified=False,ready_for_install=False,installed=False)
 boundaries={p:(op,raw) for p,op,raw in instructions(original)}
 supported={NEPHTIS_STORY,ARDJET_STORY,VIC_VIPER_STORY,*INHERT_STORY,*ANUBIS_STORY,*LATE_ANUBIS_STORY}
 combat_sites=set()
 for offset,(op,raw) in boundaries.items():
  if op!=0x88:continue
  command=struct.unpack_from('<I',raw,1)[0]
  if command not in supported:continue
  contract=decode_story_boss(original,offset,command)
  if completion(contract) is None:continue
  if command==0xef9a96d8 and contract['source_option']['value']==1:continue
  combat_sites.add(offset)
 converted={s['offset'] for s in sites}
 preserved=set(preserved_native_sites)
 if converted|preserved!=combat_sites or converted&preserved:
  raise ValueError('Source combat phases must be converted or explicitly preserved')
 if preserved:
  if profile['boss']!='Ardjet' or len(converted)!=1 or len(preserved)!=1:
   raise ValueError('Partial boss conversion is limited to one Phobos Ardjet and one native clone')
  for offset in preserved:
   if boundaries[offset][0]!=0x88 or struct.unpack_from('<I',original,offset+1)[0]!=NEPHTIS_STORY:
    raise ValueError('Preserved Phobos clone must be a native Nephtis factory')
 if site_profiles is not None:
  if set(site_profiles)!={s['offset'] for s in sites} or any(p['protected'] for p in site_profiles.values()):
   raise ValueError('Every clone site needs one unprotected boss profile')
 profiles=site_profiles or {s['offset']:profile for s in sites}
 result=bytearray(original);reports=[];visual_overrides=[];registration_overrides=[];rescue_overrides=[]
 # A replacement ordinary boss must not install the native rescue observer.
 # It owns Jehuty's grab controller and retains an Ardjet-specific reference.
 rescue_host=any(s['command']==ARDJET_STORY and decode_story_boss(original,s['offset'],ARDJET_STORY)['variant']==1 for s in sites)
 if rescue_host and not any(p.get('full_viola_ai') for p in profiles.values()):
  for p,(op,raw) in boundaries.items():
   if op==0x88 and struct.unpack_from('<I',raw,1)[0]==0x23aa5aa0:
    result[p+1:p+5]=struct.pack('<I',0xfffff75a)
    rescue_overrides.append(dict(offset=p,original_command='23aa5aa0',replacement_command='fffff75a',reason='Ordinary defeat has no Viola rescue/grab observer'))
 from boss_donor_initialisation import REGISTRATIONS
 destination_commands={t['command'] for p in profiles.values() for t in p['templates']}
 registered={REGISTRATIONS[command] for command in destination_commands if command in REGISTRATIONS}
 if len(registered)==1:
  desired=next(iter(registered))
  for p,(op,raw) in boundaries.items():
   if op==0x88 and struct.unpack_from('<I',raw,1)[0] in REGISTRATIONS.values() and struct.unpack_from('<I',raw,1)[0]!=desired:
    previous=struct.unpack_from('<I',raw,1)[0];result[p+1:p+5]=struct.pack('<I',desired)
    registration_overrides.append(dict(offset=p,original_command=f'{previous:08x}',replacement_command=f'{desired:08x}',reason='Prevent a conflicting type-9 boss class from registering before the replacement'))
 # These are animated held-pole visuals, not genuine throwable props. Their
 # update reads the original Nephtis global directly. Keep the source scenes
 # and native argument frames, but stop creating these visuals in a foreign
 # boss encounter. A verified registered RET stub consumes the same native
 # dispatch path without introducing another actor.
 if suppress_nephtis_pole_visuals and all(p['boss']!='Nephtis' for p in profiles.values()) and all(s['command']==NEPHTIS_STORY for s in sites):
  for p,(op,raw) in boundaries.items():
   if op==0x88 and struct.unpack_from('<I',raw,1)[0]==0x8b45e88f:
    result[p+1:p+5]=struct.pack('<I',0xfffff75a)
    visual_overrides.append(dict(offset=p,original_command='8b45e88f',replacement_command='fffff75a',reason='Source animated pole reads Nephtis-only global actor pointer'))
 for site in sorted(sites,key=lambda s:s['offset']):
  offset,command=site['offset'],site['command']
  local_profile=profiles[offset]
  if offset not in boundaries or boundaries[offset][0]!=0x88 or struct.unpack_from('<I',original,offset+1)[0]!=command:
   raise ValueError('Source native instruction mismatch')
  source=decode_story_boss(original,offset,command)
  if command==ARDJET_STORY and source['variant'] not in (0,1):raise ValueError('Unknown Ardjet source variant')
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
  templates=local_profile['templates'] if site_profiles is not None or len(sites)==1 else [local_profile['templates'][min(site.get('phase_index',len(reports)),len(local_profile['templates'])-1)]]
  # All Nephtis donors are normalized to the same autonomous full-health
  # combat mode. Multiple donor story spawns must not become duplicate rounds
  # in a single source encounter with one set of throwable support objects.
  foreign_inhert=local_profile['boss']=='Inhert' and command not in INHERT_STORY
  inhert_bounds=local_profile.get('arena_bounds')
  if foreign_inhert:
   templates=local_profile['templates'][:1]
   if inhert_bounds is None:
    import math
    point=[]
    for arg in coords[:3]:
     if arg['kind'] not in (0xc0,0xc1) or arg['value'] is None:raise ValueError('Foreign Inhert requires measured bounds or literal host position')
     value=struct.unpack('<f',struct.pack('<I',arg['value']))[0] if arg['kind']==0xc1 else float(arg['value'])
     if not math.isfinite(value):raise ValueError('Non-finite Inhert host position')
     point.append(value)
    x,y,z=point;inhert_bounds=(x-600,y-300,z-600,x+600,y+300,z+600)
  if all(t['command']==NEPHTIS_STORY for t in templates):
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
   if command==ARDJET_STORY and source['variant']==0 and local_profile['boss']!='Ardjet':result.extend(native(TRANSITION_EFFECT,[]))
   result.extend(b'\x89')
  viola_callbacks=None
  if local_profile.get('full_viola_ai'):
   from boss_variant_pool import append_viola_callbacks
   viola_callbacks,viola_report=append_viola_callbacks(result,source_finish)
  next_callback=viola_report['success_callback'] if viola_callbacks else source_finish
  for index,template in reversed(list(enumerate(templates))):
   phase_entry=len(result)
   identity=source['actor_id'] if index==0 else int.from_bytes(hashlib.sha256(
    (digest+'\0'+local_profile['encounter']+'\0'+str(offset)+'\0'+str(index)).encode()).digest()[:4],'little')
   if index and struct.pack('<I',identity) in original:raise ValueError('Additional phase actor identity collision')
   code=emit_spawn(template['command'],template,identity,coord_bytes,next_callback,noop,inhert_bounds,viola_callbacks)
   if viola_callbacks and site==sorted(sites,key=lambda s:s['offset'])[0] and index==0:
    # Native ef02g SCX5253: installs Jehuty's Ardjet grab handler and its
    # observer, then resets the grab counter. The factory alone does not.
    code=native(0x23aa5aa0,[])+code
    viola_report['player_setup_entry']=phase_entry
    viola_report['player_setup_command']='23aa5aa0'
    viola_report['player_setup_once_per_script']=True
   result.extend(code+b'\x89')
   phase_reports.insert(0,dict(entry=phase_entry,end=len(result),command=f"{template['command']:08x}",
    actor_id=identity,callback=next_callback,donor_offset=template['offset']))
   next_callback=phase_entry
  wrapper=len(result)
  result.extend(procedure(next_callback))
  if command==ARDJET_STORY and source['variant']==0:
   start=source['script_callbacks'][1]['offset']
   if start not in boundaries:raise ValueError('Ardjet start callback boundary mismatch')
   result.extend(procedure(start))
  result.extend(b'\x89');result[offset:offset+5]=procedure(wrapper)
  reports.append(dict(replacement_variant=local_profile.get('variant_label',local_profile['boss']),
   replacement_identity=local_profile['boss_identity'] if 'boss_identity' in local_profile else local_profile['boss'],
   viola_callbacks=viola_report if viola_callbacks else None,source_call=offset,source_command=f'{command:08x}',source_actor_id=source['actor_id'],
   source_completion_callback=callback,source_completion_bridge=source_finish,
   completion_fade_guard=None if fade_guard is None else {k:v for k,v in fade_guard.items() if k!='bytes'},
   inhert_phase_one_only=foreign_inhert,inhert_effective_bounds=inhert_bounds,
   procedure_entry=wrapper,noop_entry=noop,phases=phase_reports,
   coordinates=[dict(kind=a['kind'],value=a['value']) for a in coords],coordinate_expression_bytes=coord_bytes.hex()))
 changed={i for s in sites for i in range(s['offset'],s['offset']+5)}
 changed.update(i for row in visual_overrides for i in range(row['offset']+1,row['offset']+5))
 changed.update(i for row in registration_overrides+rescue_overrides for i in range(row['offset']+1,row['offset']+5))
 if any(a!=b for i,(a,b) in enumerate(zip(original,result)) if i not in changed):raise ValueError('Unrelated source bytes changed')
 return bytes(result),dict(destination_encounter=profile['encounter'],destination_boss=profile['boss'],sites=reports,
  source_sha256=digest,output_sha256=hashlib.sha256(result).hexdigest(),
  original_prefix_preserved=not rescue_overrides,source_rescue_overrides=rescue_overrides,source_visual_overrides=visual_overrides,source_registration_overrides=registration_overrides,foreign_ai_verified=False,source_completion_gameplay_verified=False,
  phase_actor_lifetime_verified=False,arena_verified=False,ready_for_install=False,installed=False)
