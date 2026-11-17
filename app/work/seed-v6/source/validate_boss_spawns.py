import portable_paths as _portable
"""Fail-closed, read-only boss validation against packaged archive bytes.

This verifies known spawn contracts and policy, not runtime arena/death behavior.
The installer invokes this afresh before creating backups or writing game files.
"""
import argparse,copy,hashlib,json,math,struct,sys
from pathlib import Path
from archive_tools import Archive,VAN,L,sha,strcode32
from mixed_boss_catalog import payloads,catalog,assets
from boss_variant_pool import variant_profiles
from boss_spawn_contracts import decode_story_boss
from boss_donor_initialisation import TABLE_COMMANDS,REGISTRATIONS
from scx_bytecode import instructions,native_calls,LENGTHS
from scx_call_arguments import call_arguments
from randomizer_settings import BOSSES

VERSION=1
STORY=('ca02','ba02','ba03','wn01','vc01','cy02','ef01','fr02','cs01','fa01','fr04g','am02')
EXTRAS={'vs_wn01','vs_vc01','vs_ef01','vs_cs01','vs_ca02','vs_ba02','vs_cy02','vs_fr02','vs_am02','am01g'}
SPECS={
 'Ardjet':('Ardjet','ca02',{0xfffedd53}),
 'Viola AI (full rescue fight)':('Ardjet','ef02g',{0xfffedd53}),
 'Nephtis':('Nephtis','ba02',{0xffff367b}),
 'Vic Viper':('Vic Viper','wn01',{0x7fed7b0b}),
 'Inhert':('Inhert','fr02',{0xdfedfdb4,0xbfd9f8ec}),
 'Anubis 1':('Anubis','ba03',{0xdfe3a990}),
 'Anubis 2':('Anubis','fr04g',{0xb7d9f1ad}),
 'Compressed-space Anubis':('Anubis','cs01',{0xef217f76}),
 'Fake Anubis':('Anubis','fa01',{0xfa106dc5}),
 'Aumaan Anubis':('Anubis','am02',{0xef9a96d8})}
FACTORIES=set().union(*(s[2] for s in SPECS.values()))

class BossValidationError(ValueError):pass
def need(condition,message):
 if not condition:raise BossValidationError(message)
def signature(args):return [(a['kind'],a['value']) for a in args]
def load_json(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def region(data,start,end):
 need(type(start) is int and type(end) is int and 0<=start<end<=len(data),'Invalid procedure bounds')
 p=start;rows=[]
 while p<end:
  op=data[p];n=LENGTHS.get(op,1)
  need(p+n<=end,'Truncated procedure instruction')
  rows.append((p,op,data[p:p+n]));p+=n
 return rows

def procedure(data,start):
 need(type(start) is int and 0<=start<len(data),'Callback outside script')
 p=start;rows=[]
 while p<min(len(data),start+8192):
  op=data[p];n=LENGTHS.get(op,1)
  need(p+n<=len(data) and op>=0x80 and op not in (0x8c,0x8d,0x8e),'Callback points into data or declarations')
  rows.append((p,op,data[p:p+n]));p+=n
  if op==0x89:return rows
 raise BossValidationError('Callback procedure has no bounded return')

def executable_boundaries(data,native_size,native_bounds,seeds):
 """Follow appended procedures and callbacks; never scan embedded support strings."""
 result=set(native_bounds);pending=list(seeds);seen=set()
 while pending:
  target=pending.pop()
  need(type(target) is int and 0<=target<len(data),'Procedure target outside script')
  if target in seen or target<native_size:continue
  seen.add(target);need(len(seen)<=1024,'Procedure traversal exceeds supported bound')
  rows=procedure(data,target);result.update(q for q,op,raw in rows)
  for q,op,raw in rows:
   if op in (0x87,0xc5):
    value=int.from_bytes(raw[1:],'little')
    if value>=native_size:pending.append(value)
 return result

def support_route(data,entry,goal,seen=None):
 if entry==goal:return True
 seen=set() if seen is None else seen
 if entry in seen or len(seen)>32:return False
 seen.add(entry);rows=procedure(data,entry)
 need(not any(op==0x88 and int.from_bytes(raw[1:],'little') in FACTORIES for q,op,raw in rows),'Support wrapper spawns an unvalidated boss')
 need(all(op!=0x88 or int.from_bytes(raw[1:],'little') in {0x911f0cb1,0xffffea2c,0x2be4b123} for q,op,raw in rows),'Unsupported boss support initializer')
 return any(support_route(data,int.from_bytes(raw[1:],'little'),goal,seen) for q,op,raw in rows if op==0x87)

def completion(args,command):
 index=6 if command in (0xfffedd53,0xdfedfdb4,0xbfd9f8ec) else None
 if index is not None:
  need(len(args)>index and args[index]['kind']==0xc5,'Missing source completion callback')
  return args[index]['value']
 callbacks=[a['value'] for a in args if a['kind']==0xc5]
 need(callbacks,'No source completion callback')
 return callbacks[0]

def contract(args,command):
 """Validate the decoder's full contract; inherited dynamic coordinates get zeros.

 Their exact original expression is separately compared byte for byte. This lets
 the native clone-wave height register survive without treating arbitrary script
 expressions as safe spawn data.
 """
 first=1 if command==0x7fed7b0b else 2
 encoded=bytearray()
 for i,a in enumerate(args):
  kind,value=a['kind'],a['value']
  if first<=i<first+4 and (kind not in (0xc0,0xc1) or value is None):kind,value=0xc0,0
  if kind in (0xb1,0xb2,0xb3,0xc0,0xc1,0xc2,0xc3,0xc5):
   need(type(value) is int and 0<=value<=0xffffffff,'Unresolved or invalid boss argument')
   encoded.extend(bytes((0x80,0xb0,kind))+struct.pack('<I',value))
  else:encoded.append(kind)
 off=len(encoded)+2;encoded.extend(bytes((0x84,len(args),0x88))+struct.pack('<I',command)+b'\x8e')
 try:return decode_story_boss(bytes(encoded),off,command)
 except Exception as ex:raise BossValidationError('Invalid boss spawn contract: '+str(ex)) from ex

def load_context(package):
 p=Path(package).resolve();m=load_json(p/'manifest.json');story=load_json(p/'boss-mapping.json')
 actual=sha(p/'STAGE.DAT');need(actual==m.get('patched_sha256'),'Archive checksum differs from manifest')
 if (p/'build-result.json').exists():
  result=load_json(p/'build-result.json')
  need(result.get('seed')==m.get('seed') and result.get('archive_sha256')==actual,'Build result does not match seed/archive')
 # A fresh validator process must resolve the same pinned original as the
 # builder; a Steam reinstall can remove mixed_boss_catalog's old .bak path.
 from original_inputs import pinned_input,STAGE_SHA
 import mixed_boss_catalog as native_catalog
 original=pinned_input([VAN],STAGE_SHA)
 native_catalog.ORIGINAL=Path(original['path'])
 a=Archive(p/'STAGE.DAT');stock=Archive(native_catalog.ORIGINAL)
 from boss_test_profile import campaign_catalog
 _,_,profiles,sources,_,_,_=campaign_catalog('boss-spawn-validation-reference')
 variants=variant_profiles(stock,profiles,include_viola_ai=True);canonical={}
 for label,(identity,donor,commands) in SPECS.items():
  if identity in variants:profile=next(x for x in variants[identity] if x['variant_label']==label)
  else:profile=profiles[donor]
  canonical[label]=dict(profile=profile,required=assets(stock,profile)[0])
  if identity=='Nephtis' and m.get('settings',{}).get('boss_mode')=='shuffle_test':
   from boss_test_profile import nephtis_support_assets
   canonical[label]['required'].update(nephtis_support_assets(stock))
 names={r.get('stage') for r in m.get('boss_changes',[])}
 resources={s:payloads(a,s) for s in names if s in a.stages}
 originals={s:payloads(stock,s) for s in names if s in stock.stages}
 positions={}
 for s in resources:
  positions[s]={f['name']:(gi,i) for gi,g in enumerate(a.groups(s)) for i,f in enumerate(g['files'])}
 return dict(package=p,manifest=m,story=story,resources=resources,originals=originals,positions=positions,
  canonical=canonical,sources=sources,archive_sha256=actual,
  manifest_sha256=sha(p/'manifest.json'),boss_mapping_sha256=sha(p/'boss-mapping.json'))

def validate_context(ctx):
 m=ctx['manifest'];story=ctx['story'];p=ctx['package']
 test_profile=m.get('settings',{}).get('boss_mode')=='shuffle_test'
 if test_profile:
  from boss_test_profile import stages
  expected_story=stages(m['settings'])
  expected_extras=set()
 else:expected_story=STORY;expected_extras=EXTRAS
 need(isinstance(story,list) and [r.get('stage') for r in story]==list(expected_story),'Missing, duplicate or out-of-order story boss encounters')
 allrows=m.get('boss_changes',[])
 need(len(allrows)==len(expected_story)+len(expected_extras) and {r.get('stage') for r in allrows}==set(expected_story)|expected_extras,'Missing, duplicate or unknown assigned boss encounter')
 bystage={r['stage']:r for r in allrows};used=set();variant_bags={}
 selected=m.get('settings',{}).get('enabled_bosses')
 if selected is not None:need(set(selected)<=set(BOSSES) and bool(selected),'Invalid boss inclusion settings')
 for r in story:
  stage=r['stage'];identity=r.get('identity');allowed={'Ardjet','Nephtis','Anubis','Vic Viper'}
  if stage=='fr02':allowed.add('Inhert')
  if stage=='vc01':allowed.remove('Vic Viper')
  if selected is not None:allowed &= {BOSSES[name] for name in selected}
  if test_profile:
   from boss_test_profile import compatible
   allowed=compatible(stage,selected,m['settings'].get('include_inhert_experimental',False),m['settings'].get('valley_viper_test',False))
  need(identity in allowed,stage+': incompatible boss identity')
  need(set(r.get('compatible',[]))==allowed,stage+': compatibility list disagrees with policy')
  need(r==bystage[stage],stage+': boss map and manifest disagree')
  remaining=allowed-used;reset=not remaining
  if reset:used-=allowed;remaining=allowed
  need(identity in remaining and r.get('compatible_bag_reset')==reset,stage+': identity repeated before compatible pool exhaustion')
  used.add(identity)
  label=r.get('variant');need(label in SPECS and SPECS[label][0]==identity,stage+': boss variant and identity disagree')
  if identity in ('Ardjet','Anubis'):
   pool={k for k,v in SPECS.items() if v[0]==identity}
   if selected is not None:pool &= set(selected)
   if m.get('settings',{}).get('include_viola_ai') is False:pool.discard('Viola AI (full rescue fight)')
   need(label in pool,stage+': disabled experimental boss variant')
   bag=variant_bags.setdefault(identity,set())
   if bag==pool:bag.clear()
   need(label not in bag,stage+': variant repeated before variant pool exhaustion');bag.add(label)
 if test_profile:
  from arena_runtime_support import verify as verify_reach
  verify_reach(p,m)
  from viper_runtime_support import verify as verify_viper
  verify_viper(p,m,story)
 helper_hashes={h['file']:h['sha256'] for h in m.get('runtime_helpers',[])}
 for name in ('AumaanArenaGuard.exe','ViperArenaGuard.exe','FakeAnubisDamageAdapter.exe','FakeAnubisDamageTableAdapter.exe','NephtisFullHealthAdapter.exe'):
  need(name in helper_hashes and (p/'runtime'/name).is_file() and sha(p/'runtime'/name)==helper_hashes[name],'Missing or altered boss runtime support: '+name)
 checked=[];asset_count=0;callback_count=0
 for r in allrows:
  stage=r['stage'];label=r.get('variant',r.get('destination_boss'))
  if label=='Bahram Anubis':label='Anubis 1'
  need(label in SPECS,stage+': unknown boss variant')
  identity,donor,commands=SPECS[label]
  need(r.get('destination_encounter')==donor,stage+': variant has wrong native donor')
  resources=ctx['resources'].get(stage,{});originals=ctx['originals'].get(stage,{})
  name=r.get('file');need(name in resources and name in originals,stage+': spawn script missing')
  b=resources[name];native=originals[name];main=list(instructions(native));native_bounds={q for q,op,raw in main if op not in (0x8c,0x8d,0x8e)}
  nephtis_sites=[s for s in r['sites'] if s.get('replacement_identity',identity)=='Nephtis']
  if test_profile and nephtis_sites and m.get('effective_settings'):
   from nephtis_encounter_support import pole_wrapper
   supports=r.get('nephtis_support',[])
   need(len(supports)==len(nephtis_sites),stage+': missing Nephtis pole support manifest')
   for info,site in zip(supports,nephtis_sites):
    poles=info['poles']
    need(info.get('gauntlet_cube_added') is False and len(poles['actor_ids'])==8,stage+': invalid required poles or unwanted cube')
    if 'height_expression' in poles:
     from dynamic_nephtis_poles import height_expression,pole_wrapper as dynamic_wrapper
     need(stage=='am01g',stage+': unexpected dynamic support height')
     expression=height_expression(native,site['source_call'])
     need(poles['height_expression']==expression.hex(),stage+': support height differs from source')
     pb,_=dynamic_wrapper(poles['entry'],site['procedure_entry'],poles['positions'],poles['actor_ids'],expression)
    else:pb,_=pole_wrapper(poles['entry'],site['procedure_entry'],poles['positions'],poles['actor_ids'])
    need(b[poles['entry']:poles['entry']+len(pb)]==pb,stage+': required pole support bytes differ')
    need(b[site['source_call']:site['source_call']+5]==b'\x87'+struct.pack('<I',poles['entry']),stage+': required support bypassed')
  need(isinstance(r.get('sites'),list) and r['sites'],stage+': no boss spawn sites')
  source_offsets=[s['source_call'] for s in r['sites']]
  need(len(set(source_offsets))==len(source_offsets),stage+': duplicate boss source site')
  preserved=r.get('native_viola_preserved',False)
  if preserved:
   need(stage=='ef02g' and label=='Viola AI (full rescue fight)',stage+': invalid native rescue preservation claim')
   need(b[:len(native)]==native and not any(b[len(native):]),stage+': native rescue script was altered')
   need(r.get('source_sha256')==hashlib.sha256(native).hexdigest(),stage+': native rescue provenance differs')
  seeds=[]
  if not preserved:
   for site in r['sites']:
    seeds.extend([site['procedure_entry'],site['noop_entry'],site['source_completion_bridge']])
    seeds.extend(phase['entry'] for phase in site['phases'])
    source=site['source_call']
    need(0<=source<len(b)-4 and b[source]==0x87,stage+': source spawn bypasses validated procedures')
    seeds.append(struct.unpack_from('<I',b,source+1)[0])
  boundaries=executable_boundaries(b,len(native),native_bounds,seeds)
  if test_profile or stage in STORY:
   expected=ctx['sources'][stage]
   expected_offsets={s['offset'] for s in expected}
   need(name==expected[0]['file'] and set(source_offsets)==expected_offsets,stage+': source combat phase omitted or added')
  site_labels=[s.get('replacement_variant',label) for s in r['sites']]
  if stage=='am01g' and r.get('clone_safety'):
   need(len(site_labels)==2 and len({SPECS[x][0] for x in site_labels})==2,stage+': clone boss identities repeat')
  required={}
  for site_label in site_labels:
   need(site_label in SPECS,stage+': unknown clone boss variant')
   for asset,data in ctx['canonical'][site_label]['required'].items():
    need(asset not in required or required[asset]==data,stage+': conflicting clone resource '+asset)
    required[asset]=data
  declared={x['name']:x['sha256'] for x in r.get('assets',{}).get('files',[])}
  need(required and set(required)<=set(declared),stage+': incomplete boss resource manifest')
  for asset,data in required.items():
   need(asset in resources and hashlib.sha256(resources[asset]).digest()==hashlib.sha256(data).digest(),stage+': missing or incompatible boss resource '+asset)
  for asset,digest in declared.items():
   need(asset in resources and hashlib.sha256(resources[asset]).hexdigest()==digest,stage+': resource checksum mismatch '+asset)
   asset_count+=1
   if asset.endswith('.mts'):
    data=resources[asset];off=struct.unpack_from('<I',data)[0]
    need(0<=off<len(data),stage+': invalid motion reference')
    lib=data[off:].split(b'\0',1)[0].decode('ascii');key=f'{strcode32(lib):08x}.mtl'
    need(key in resources and ctx['positions'][stage][key]<ctx['positions'][stage][asset],stage+': missing or late motion library '+key)
  if label=='Compressed-space Anubis':need('827e775a.cvz' in resources,stage+': compressed-space player geometry missing')
  if label=='Aumaan Anubis':need('4c8c71d9.cvz' in resources,stage+': Aumaan player geometry missing')
  if preserved:
   for site in r['sites']:
    source=site['source_call'];args=call_arguments(native,source)
    need(source in native_bounds and native[source:source+5]==bytes.fromhex('8853ddfeff'),stage+': native rescue factory differs')
    need(args[1]['value']==1 and site['source_actor_id']==args[0]['value'] and site['source_completion_callback']==completion(args,0xfffedd53),stage+': native rescue callback/variant differs')
    need(site.get('phases')==[] and site.get('viola_callbacks') is None,stage+': preserved rescue declares replacement code')
    checked.append(dict(stage=stage,variant=label,source=source,factory='fffedd53',native_script_preserved=True,callback=completion(args,0xfffedd53)))
    callback_count+=3
   continue
  for site in r['sites']:
   site_label=site.get('replacement_variant',label)
   _,_,commands=SPECS[site_label]
   source=site['source_call'];source_cmd=int(site['source_command'],16)
   need(source in native_bounds and native[source:source+5]==b'\x88'+struct.pack('<I',source_cmd),stage+': original source factory mismatch')
   source_args=call_arguments(native,source);source_id=source_args[0]['value'];source_done=completion(source_args,source_cmd)
   need(site['source_actor_id']==source_id and site['source_completion_callback']==source_done,stage+': original actor/completion mismatch')
   need(source_done in native_bounds,stage+': original completion is not an instruction boundary')
   phases=site.get('phases',[]);need(phases,stage+': no replacement boss phase')
   wrapper=site['procedure_entry']
   actual_entry=struct.unpack_from('<I',b,source+1)[0]
   need(actual_entry in boundaries and support_route(b,actual_entry,wrapper),stage+': source spawn bypasses validated wrapper')
   wrapper_rows=procedure(b,wrapper)
   need(wrapper_rows[0][1]==0x87 and int.from_bytes(wrapper_rows[0][2][1:],'little')==phases[0]['entry'],stage+': wrapper does not reach first boss phase')
   bridge=site['source_completion_bridge']
   need(bridge in boundaries,stage+': completion bridge is not an instruction boundary')
   if bridge!=source_done:
    bridge_rows=procedure(b,bridge)
    need(any(op==0x87 and int.from_bytes(raw[1:],'little')==source_done for q,op,raw in bridge_rows),stage+': completion bridge does not reach original progression')
   first=1 if source_cmd==0x7fed7b0b else 2;coords=source_args[first:first+4]
   need(len(coords)==4 and coords[0]['offset'] is not None and coords[-1]['offset'] is not None,stage+': unresolved coordinate expression bounds')
   expression=native[coords[0]['offset']-3:coords[-1]['offset']+4]
   need(site.get('coordinate_expression_bytes')==expression.hex(),stage+': coordinate expression differs from original encounter')
   phase_ids=set()
   for index,phase in enumerate(phases):
    start,end=phase['entry'],phase['end'];rows=region(b,start,end)
    need(start in boundaries and rows[-1][1]==0x89,stage+': invalid phase entry/return')
    calls=[(q,int.from_bytes(raw[1:],'little')) for q,op,raw in rows if op==0x88]
    spawns=[(q,h) for q,h in calls if h in FACTORIES]
    need(len(spawns)==1,stage+': phase must contain exactly one supported boss spawn')
    off,cmd=spawns[0]
    need(cmd in commands and cmd==int(phase['command'],16),stage+': wrong actual boss factory')
    frag=b[start:end]+b'\x8e';args=call_arguments(frag,off-start);decoded=contract(args,cmd)
    need(args[0]['value']==phase['actor_id'] and (index!=0 or phase['actor_id']==source_id),stage+': boss actor identity mismatch')
    need(phase['actor_id'] not in phase_ids,stage+': duplicate actor identity within replacement chain');phase_ids.add(phase['actor_id'])
    cfirst=1 if cmd==0x7fed7b0b else 2;actual_coords=args[cfirst:cfirst+4]
    need(signature(actual_coords)==signature(coords),stage+': actual spawn coordinates differ from source')
    need(actual_coords[0]['offset'] is not None and actual_coords[-1]['offset'] is not None and frag[actual_coords[0]['offset']-3:actual_coords[-1]['offset']+4]==expression,stage+': altered dynamic coordinate expression')
    for arg in actual_coords:
     if arg['kind']==0xc1 and arg['value'] is not None:need(math.isfinite(struct.unpack('<f',struct.pack('<I',arg['value']))[0]),stage+': nonfinite spawn coordinate')
    expected=phases[index+1]['entry'] if index+1<len(phases) else (site.get('viola_callbacks',{}).get('success_callback') if site_label=='Viola AI (full rescue fight)' else bridge)
    need(phase['callback']==expected and completion(args,cmd)==expected,stage+': boss completion chain is broken')
    for arg in args:
     if arg['kind']==0xc5:
      need(arg['value'] in boundaries,stage+': callback points into data, an operand, or outside script');callback_count+=1
    if cmd==0xfffedd53:
     need(args[1]['value']==(1 if site_label=='Viola AI (full rescue fight)' else 0),stage+': incorrect Ardjet/Viola variant')
     if site_label=='Viola AI (full rescue fight)':
      vc=site.get('viola_callbacks') or {}
      need([x['value'] for x in args[-3:]]==[expected,vc.get('mid_callback'),vc.get('failure_callback')],stage+': Viola AI callback mismatch')
      for key in ('success_callback','mid_callback','resume_callback','failure_callback','finish_failure_callback'):need(vc.get(key) in boundaries,stage+': Viola AI bridge missing')
      success_rows=procedure(b,vc['success_callback'])
      success_calls=[q for q,op,raw in success_rows if op==0x88 and int.from_bytes(raw[1:],'little')==0xffffb011]
      success_fragment=b[vc['success_callback']:success_rows[-1][0]+1]+b'\x8e'
      need(len(success_calls)==1 and signature(call_arguments(success_fragment,success_calls[0]-vc['success_callback']))==[(0xc0,40),(0xc5,bridge)],stage+': Viola AI native success/release delay is missing or bypasses host progression')
      need(vc.get('success_delay_frames')==40 and vc.get('completion_callback')==bridge,stage+': Viola AI release delay metadata differs')
      setup=[q for q,h in calls if h==0x23aa5aa0]
      first_setup=site is r['sites'][0] and index==0
      need(len(setup)==int(first_setup),stage+': Viola AI player grab setup missing or duplicated')
      if first_setup:
       need(setup[0]==start+2 and setup[0]<off and frag[:7]==bytes.fromhex('840088a05aaa23') and not call_arguments(frag,setup[0]-start),stage+': Viola AI player handler must be installed before spawn')
       need(vc.get('player_setup_entry')==start and vc.get('player_setup_command')=='23aa5aa0' and vc.get('player_setup_once_per_script') is True,stage+': Viola AI player setup metadata differs')
      for key,command in (('mid_callback',0xd1f9be9f),('resume_callback',0xffe438ce),('failure_callback',0x144505ad),('finish_failure_callback',0x90dfcb93)):
       vc_rows=procedure(b,vc[key]);need(any(op==0x88 and int.from_bytes(raw[1:],'little')==command for q,op,raw in vc_rows),stage+': Viola AI control flow incomplete')
      for key,command,expected_args in (('mid_callback',0xd1f9be9f,[(0xc5,vc['resume_callback'])]),('failure_callback',0xffcc3307,[(0xc0,0)]*4+[(0xc0,500),(0xc5,vc['finish_failure_callback'])])):
       vc_rows=procedure(b,vc[key]);start_vc=vc[key];end_vc=vc_rows[-1][0]+1;frag_vc=b[start_vc:end_vc]+b'\x8e'
       matches=[q for q,h in native_calls(frag_vc) if h==command]
       need(len(matches)==1 and signature(call_arguments(frag_vc,matches[0]))==expected_args,stage+': Viola AI resume/failure callback chain broken')
    if cmd==0xffff367b:need(decoded['phase']==3 and decoded['script_callback']==expected,stage+': Nephtis combat mode/callback invalid')
    if cmd==0xef9a96d8:need(decoded['source_option']['value']==0,stage+': cinematic Aumaan variant cannot replace combat')
    for command in ([TABLE_COMMANDS[cmd]] if cmd in TABLE_COMMANDS else []):
     setups=[q for q,h in calls if h==command and q<off]
     need(len(setups)==1,stage+': boss damage-table setup missing or duplicated')
     table=call_arguments(frag,setups[0]-start)
     need(table and len(table)%3==0 and len({table[i+1]['value'] for i in range(0,len(table),3)})==len(table)//3 and all(table[i]['kind']==0xd3 and table[i+1]['kind']==0xc0 and table[i+2]['kind']==0xc0 and 0<=table[i+1]['value']<76 and 0<=table[i+2]['value']<=32767 for i in range(0,len(table),3)),stage+': invalid boss damage table')
    if cmd in REGISTRATIONS:
     need(any(h==REGISTRATIONS[cmd] and q<off for q,h in calls),stage+': boss actor registration missing')
    if cmd==0xef9a96d8:need(any(h==0x019506a4 and q<off for q,h in calls),stage+': Aumaan actor registration missing')
    setup_command=REGISTRATIONS.get(cmd,0x019506a4 if cmd==0xef9a96d8 else (0x7bf39906 if cmd==0xffff367b else None))
    if setup_command is not None:
     setup=[q for q,h in calls if h==setup_command and q<off]
     expected_type=10 if cmd==0xef9a96d8 else (11 if cmd==0xffff367b else 9)
     need(len(setup)==1 and signature(call_arguments(frag,setup[0]-start))==[(0xc0,expected_type)],stage+': invalid boss registration/configuration type')
    checked.append(dict(stage=stage,variant=site_label,source=source,entry=start,factory=f'{cmd:08x}',callback=expected))
 return dict(format=1,validator_version=VERSION,passed=True,seed=m['seed'],archive_sha256=ctx['archive_sha256'],manifest_sha256=ctx['manifest_sha256'],boss_mapping_sha256=ctx['boss_mapping_sha256'],story_encounters_checked=len(story),additional_assigned_encounters_checked=len(expected_extras),spawn_phases_checked=len(checked),resource_hashes_checked=asset_count,callback_boundaries_checked=callback_count,repeat_policy_checked=True,checks=checked,gameplay_verified=False,limitation='Static spawn, resource and progression-contract checks do not establish live arena behavior or a crash-free run.')

def validate(package):
 if load_json(Path(package)/'manifest.json').get('settings',{}).get('boss_mode')=='native':
  from validate_native_seed import verify
  return verify(package)
 return validate_context(load_context(package))

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--package',required=True);parser.add_argument('--output');args=parser.parse_args()
 try:
  p=Path(args.package)
  need((p/'build-result.json').is_file() and (p/'installation-plan.json').is_file(),'Incomplete installable seed package')
  report=validate(p)
 except Exception as ex:
  report=dict(format=1,validator_version=VERSION,passed=False,error=str(ex),gameplay_verified=False)
  code=1
 else:code=0
 if args.output:
  path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print(('PASS boss-spawn validation: '+str(report.get('spawn_phases_checked'))+' phases' if code==0 else 'FAIL boss-spawn validation: '+report['error']),flush=True)
 return code
if __name__=='__main__':sys.exit(main())
