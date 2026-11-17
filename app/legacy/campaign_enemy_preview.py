import portable_paths as _portable
"""Build a full-campaign regular-enemy archive preview. Boss/reward adapters are not implemented."""
import argparse,json,sys,struct,hashlib,zlib,re,shutil
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'research'))
from zoe2_archive import Archive,align,strcode32,xor_words,MASK,EXT
from scx_bytecode import native_calls,instructions,declarations
from actor_reference_adapter import patch_references
from scx_manager_chain_adapter import append_manager_chain,appended_instructions
from cache_file_rebuilder import replace_group_files
from enemy_pool_dependencies import campaign_pool_dependencies
from prepare_respawn_pool_dependency import prepare_respawn_dependency
from ene_pool_storage import extend_pool_storage
from campaign_pool_path_gate import audit_campaign_pool_paths
from scx_call_arguments import UnresolvedArguments
SOURCE='c5627420319bbaa28f887b0728e14277befd9cf33ced3f82d0e304b389d5e651'
GAME=Path(str(_portable.game()))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def stream(seed,stage):
 return hashlib.sha256(('ZOE2-full-enemies-v1\0'+seed+'\0'+stage).encode()).digest()
def shuffle(pool,key):
 pool=list(pool)
 for i in range(len(pool)-1,0,-1):
  ceiling=(1<<64)-((1<<64)%(i+1));counter=0
  while True:
   x=int.from_bytes(hashlib.sha256(key+i.to_bytes(4,'big')+counter.to_bytes(4,'big')).digest()[:8],'big')
   if x<ceiling:break
   counter+=1
  j=x%(i+1);pool[i],pool[j]=pool[j],pool[i]
 return pool
def section(a,stage,groups,changes,imports,sound_imports=()):
 from model_texture_load_order import order_model_textures
 h=strcode32(stage);key=(129*h+a.seed+0xa78925d9)&MASK;inc=(129*h+0x7a88fb59)&MASK
 with a.path.open('rb') as f:
  f.seek(a.stages[stage]);n=struct.unpack('<I',xor_words(f.read(4),key,inc))[0]
  f.seek(a.stages[stage]);table=xor_words(f.read(4+12*n),key,inc)
 entries=[list(struct.unpack_from('<III',table,4+12*i)) for i in range(n)]
 cache_index=next(i for i,g in enumerate(groups) if g['folder']=='cache')
 sound_index=next((i for i,g in enumerate(groups) if g['folder']=='sound'),None)
 if sound_imports:
  if sound_index is None:raise ValueError('Arena has no sound group')
  changes.setdefault(sound_index,bytearray(a.decode(groups[sound_index])))
 cursor=0;payloads=[];i=0
 for gi,g in enumerate(groups):
  marker=i;i+=1;compressed=g['compressed_size']
  if compressed is not None:descriptor=i;i+=1
  start=i
  while entries[i][0]!=0x7f000000:i+=1
  end=i
  if gi in changes:
   assert len(g['files'])==end-start
   for entry,f in zip(entries[start:end],g['files']):
    expected=f'pk{entry[0]:06x}.sdx' if gi==sound_index else f'{entry[1]:08x}.'+EXT[entry[0]]
    assert f['name']==expected
    entry[2]=f['offset']
  if gi in changes:
   d=changes[gi]
   if gi==cache_index:
    added=[]
    for item,b in imports:
     assert len(d)%16==0
     added.append([next(k for k,v in EXT.items() if v==item.rsplit('.',1)[1]),int(item.split('.')[0],16),len(d)])
     d.extend(b)
    entries[end:end]=added;end+=len(added);i=end
   if gi==sound_index:
    next_pack=max(e[0] for e in entries[start:end])+1
    for b in sound_imports:
     if len(d)%2048 or len(b)%2048:raise ValueError('Sound pack is not sector aligned')
     entries.insert(end,[next_pack,0,len(d)]);end+=1;i=end
     d.extend(b);next_pack+=1
   else:
    ordered,d,_=order_model_textures(entries[start:end],d)
    entries[start:end]=ordered
   entries[marker][2]=len(d);entries[end][2]=len(d)
   if compressed is not None:
    packed=bytearray(zlib.compress(d,6));compressed=len(packed)
    with a.path.open('rb') as f:f.seek(g['location']);k16=struct.unpack('<H',f.read(2))[0]^0x9385
    struct.pack_into('<H',packed,0,(struct.unpack_from('<H',packed)[0]-0x8f3)&0xffff)
    packed.extend(bytes(align(len(packed),4)-len(packed)))
    payload=xor_words(packed,k16|((k16^0x6576)<<16),k16*0x116)
   else:payload=bytes(d)
  else:
   with a.path.open('rb') as f:f.seek(g['location']);payload=f.read(align(compressed,4) if compressed is not None else g['decoded_size'])
  if compressed is not None:
   assert compressed<0x1000000
   entries[descriptor][0]=0x7e000000|compressed;entries[descriptor][2]=cursor
  payload+=bytes(align(len(payload))-len(payload));payloads.append(payload);cursor+=len(payload);i=end+1
 nt=struct.pack('<I',len(entries))+b''.join(struct.pack('<III',*e) for e in entries)
 return xor_words(nt,key,inc)+bytes(align(len(nt))-len(nt))+b''.join(payloads)
def build(seed,out,stage_filter=None,opening_nonidentity=False):
 out.mkdir(exist_ok=False)
 original=GAME/'ZOE2'/'STAGE.DAT.zoe2-ca01-loader-v1.bak'
 assert sha(original)==SOURCE,'Original backup hash mismatch'
 a=Archive(original)
 specs=json.loads((root/'enemy-assets.json').read_text())
 scope=json.loads((root/'full-game-scope.json').read_text(encoding='utf-8-sig'))
 by_type={v['type']:name for name,v in specs.items()}
 setup_aliases=json.loads((root/'enemy-setup-aliases.json').read_text())['aliases']
 alias_types={int(h,16):specs[name]['type'] for name,hashes in setup_aliases.items() for h in hashes}
 donors={}
 for name,spec in specs.items():
  g=next(g for g in a.groups(spec['donor']) if g['folder']=='cache');d=a.decode(g);lookup={f['name']:f for f in g['files']}
  donors[name]={item['hash']:d[lookup[item['hash']]['offset']:lookup[item['hash']]['offset']+lookup[item['hash']]['size']] for item in spec['files']}
 atlas={}
 for label in ['main','small']:
  lines=(root/'Loader-Test'/(label+'-index.txt')).read_text().splitlines()
  atlas[label]={line.split('\t')[0] for line in lines if len(line.split('\t'))==3}
 blocks={};plans=[];aliases={'main':{},'small':{}};expected={};excluded=[]
 for stage in scope['regular_stages']:
  if stage_filter is not None and stage not in stage_filter:continue
  gs=a.groups(stage);decoded={};files={};script_adapters={};dependency_adapters={};adapter_groups=set()
  for gi,g in enumerate(gs):
   if g['folder'] in ['cache','nocache']:
    decoded[gi]=bytearray(a.decode(g))
    if stage=='mf01':
     matches=[f for f in g['files'] if f['name']=='e5d52896.scx']
     if matches:
      f=matches[0];source=bytes(decoded[gi][f['offset']:f['offset']+f['size']])
      evidence=json.loads((root/'mf01-manager-chain-preview.json').read_text())
      assert hashlib.sha256(source).hexdigest()==evidence['source_sha256'],'Manager adapter source mismatch'
      patched,adapter=append_manager_chain(source,0x2567,0x869acfd7,[0xd1efc2e5,0x7d6e9d45])
      decoded[gi]=replace_group_files(g,decoded[gi],{f['name']:patched})
      script_adapters[f['name']]=adapter;adapter_groups.add(gi)
    for f in g['files']:files[f['name']]=(gi,f)
  def script_calls(data,key):
   calls=native_calls(data)
   if key in script_adapters:
    adapter=script_adapters[key]
    calls.extend((p,int.from_bytes(raw[1:],'little')) for p,op,raw in appended_instructions(data,adapter['procedure_entry'],adapter['procedure_end']) if op==0x88)
   if key in dependency_adapters:
    primary=dependency_adapters[key]
    for adapter in [primary]+primary.get('additional_procedures',[]):
     calls.extend((p,int.from_bytes(raw[1:],'little')) for p,op,raw in appended_instructions(data,adapter['procedure_entry'],adapter['procedure_end']) if op==0x88)
   return calls
  present=set();slots=[];actor_sites={}
  for key,(gi,f) in files.items():
   if not key.endswith('.ene'):continue
   d=decoded[gi];base=f['offset'];count=struct.unpack_from('<H',d,base+2)[0]
   record_offset=struct.unpack_from('<I',d,base+4)[0]
   assert record_offset>=32 and record_offset+count*112<=f['size'], 'Invalid native ENE record bounds: '+stage+' '+key
   for r in range(count):
    for s in range(4):
     p=base+record_offset+112*r+48+8*s;t,n=d[p:p+2]
     if n and t in by_type:present.add(t);slots.append((gi,p,t,key,r,s,n,d[p+2]))
  selector_commands={int(h,16) for h in json.loads((root/'type-selector-command-catalog.json').read_text())['commands']}
  sites={t:[] for t in by_type}
  for key,(gi,f) in files.items():
   if key.endswith('.scx'):
    b=bytes(decoded[gi][f['offset']:f['offset']+f['size']])
    for q,h in script_calls(b,key):
     if h in selector_commands:actor_sites.setdefault(key,[]).append(dict(offset=q,command=h))
     t=alias_types.get(h)
     if t in sites:sites[t].append((gi,f['offset']+q+1,key,q+1))
  unsupported=sorted(t for t in present if not sites[t])
  if unsupported:
   excluded.append(dict(stage=stage,reason='Existing native setup callback not found for ENE types',types=unsupported));continue
  manager_types={t for t,refs in sites.items() if refs}
  mapping_types=present|manager_types
  mapping=dict(zip(sorted(mapping_types),shuffle(sorted(by_type),stream(seed,stage))))
  if opening_nonidentity and stage in ('ca00','ca01'):
   assert mapping_types=={40},'Opening override requires the reviewed Raptor-only source pool'
   # Restrict this preview fix to self-contained normal pools: Mummyhead/Clod
   # require an extra respawn manager; Narita's attachment issue is unresolved.
   candidates=shuffle([41,42],stream(seed,stage))
   mapping={40:candidates[0]}
  assert len(set(mapping.values()))==len(mapping),'Duplicate replacement manager type'
  expected_manager_counts={mapping[t]:len(sites[t]) for t in manager_types}
  changed={t:to for t,to in mapping.items() if t!=to}
  mapped_manager_types={mapping[t] for t in manager_types}
  needs_respawn_pool=bool(mapped_manager_types & {32,43}) and (40 not in mapped_manager_types or stage=='ba01')
  if not changed and not script_adapters and not needs_respawn_pool:plans.append(dict(stage=stage,mapping=mapping,changed_slots=0));continue
  changed_groups=set(adapter_groups);edits=[];reference_edits=[];reference_failed=False
  for key,refs in actor_sites.items():
   gi,f=files[key];original_script=bytes(decoded[gi][f['offset']:f['offset']+f['size']])
   binding=None
   if stage=='af01g':
    candidate=json.loads((root/'battleship-binding.json').read_text())
    if candidate['file']==key:binding=candidate
   try:patched_script,patches=patch_references(original_script,refs,mapping,binding)
   except UnresolvedArguments as e:
    excluded.append(dict(stage=stage,reason='Unresolved scripted enemy selector: '+str(e),file=key));reference_failed=True;break
   assert native_calls(original_script)==native_calls(patched_script)
   assert declarations(original_script)==declarations(patched_script)
   assert [(p,op) for p,op,raw in instructions(original_script)]==[(p,op) for p,op,raw in instructions(patched_script)]
   if patches:
    decoded[gi][f['offset']:f['offset']+f['size']]=patched_script;changed_groups.add(gi)
    reference_edits.extend(dict(file=key,**patch) for patch in patches)
  if reference_failed:continue
  for gi,p,t,key,r,s,n,level in slots:
   if t in changed:
    decoded[gi][p]=changed[t];changed_groups.add(gi)
    edits.append(dict(file=key,record=r,slot=s,original=t,replacement=changed[t],count=n,level=level))
  for t,to in changed.items():
   for gi,p,key,local in sites[t]:
    struct.pack_into('<I',decoded[gi],p,int(specs[by_type[to]]['command'],16));changed_groups.add(gi)
  if needs_respawn_pool:
   scripts={key:bytes(decoded[gi][f['offset']:f['offset']+f['size']]) for key,(gi,f) in files.items() if key.endswith('.scx')}
   try:replacements,dependency_adapters=prepare_respawn_dependency(scripts,script_adapters)
   except ValueError as e:
    excluded.append(dict(stage=stage,reason='Unresolved native respawn dependency: '+str(e)));continue
   assert len(dependency_adapters)==1
   for key,patched in replacements.items():
    gi,f=files[key];decoded[gi]=replace_group_files(gs[gi],decoded[gi],{key:patched});changed_groups.add(gi)
   files={f['name']:(gi,f) for gi,g in enumerate(gs) if gi in decoded for f in g['files']}
   expected_manager_counts[40]=expected_manager_counts.get(40,0)+sum(1+len(r.get('additional_procedures',[])) for r in dependency_adapters.values())
  pool_storage_extensions=[]
  if dependency_adapters:
   capacity=max(adapter['dependency_capacity'] for adapter in dependency_adapters.values())
   storage_changes={}
   try:
    for key,(gi,f) in files.items():
     if not key.endswith('.ene'):continue
     original_ene=bytes(decoded[gi][f['offset']:f['offset']+f['size']])
     backed_ene,storage_record=extend_pool_storage(original_ene,capacity)
     if storage_record['changed']:
      storage_changes.setdefault(gi,{})[key]=backed_ene
      pool_storage_extensions.append(dict(file=key,**storage_record))
   except ValueError as e:
    excluded.append(dict(stage=stage,reason='Unresolved supplemental pool storage: '+str(e)));continue
   for gi,replacements in storage_changes.items():
    decoded[gi]=replace_group_files(gs[gi],decoded[gi],replacements);changed_groups.add(gi)
   files={f['name']:(gi,f) for gi,g in enumerate(gs) if gi in decoded for f in g['files']}
  ci=next(i for i,g in enumerate(gs) if g['folder']=='cache');changed_groups.add(ci)
  imports={}
  imported_tex={}
  import_types=(set(mapping.values()) if script_adapters else set(changed.values())) | ({40} if dependency_adapters else set())
  for to in sorted(import_types):
   name=by_type[to];spec=specs[name]
   for item,b in donors[name].items():
    if item not in files:
     if item in imports:assert imports[item]==b,'Conflicting imported asset'
     imports[item]=b
     if item.endswith('.tex'):imported_tex[item.split('.')[0]]=spec['donor']
  order=lambda item:({'tex':0,'mdz':1,'mtl':2,'mts':3,'flw':4}[item.rsplit('.',1)[1]],item)
  import_list=[(key,imports[key]) for key in sorted(imports,key=order)]
  for h,donor in imported_tex.items():
   for label,names in atlas.items():
    donor_names=sorted(n for n in names if n.startswith('@'+donor+'_'+h) and n.endswith(('.dat','.tbl')))
    assert any(n.endswith('.dat') for n in donor_names) and any(n.endswith('.tbl') for n in donor_names),'Missing atlas donor: '+label+' '+donor+' '+h
    for n in donor_names:
     target='@'+stage+n[len('@'+donor):]
     if target not in names:aliases[label][target]=n
  actual_manager_counts={}
  for key,(gi,f) in files.items():
   if key.endswith('.scx'):
    for _,h in script_calls(bytes(decoded[gi][f['offset']:f['offset']+f['size']]),key):
     t=alias_types.get(h)
     if t is not None:actual_manager_counts[t]=actual_manager_counts.get(t,0)+1
  assert actual_manager_counts==expected_manager_counts,'Manager multiplicity mismatch: '+stage
  expected[stage]={key:bytes(decoded[gi][f['offset']:f['offset']+f['size']]) for key,(gi,f) in files.items()}
  expected[stage].update(imports)
  blocks[stage]=section(a,stage,gs,{gi:decoded[gi] for gi in changed_groups},import_list)
  plans.append(dict(stage=stage,mapping={by_type[k]:by_type[v] for k,v in mapping.items()},manager_types=[by_type[t] for t in sorted(manager_types)],ene_types=[by_type[t] for t in sorted(present)],manager_counts_verified=True,script_adapters=script_adapters,dependency_adapters=dependency_adapters,pool_storage_extensions=pool_storage_extensions,dependency_manager_types=(['Raptor'] if dependency_adapters else []),changed_slots=len(edits),edits=edits,actor_reference_edits=reference_edits,imports=list(imports)))
  print('Prepared',stage,len(edits),'groups',len(imports),'assets',flush=True)
 stages=sorted(a.stages,key=a.stages.get);offsets={};output=out/'STAGE.DAT'
 with original.open('rb') as f,output.open('xb') as o:
  o.write(f.read(a.stages[stages[0]]))
  for i,stage in enumerate(stages):
   offsets[stage]=o.tell()
   end=a.stages[stages[i+1]] if i+1<len(stages) else a.size
   if stage in blocks:o.write(blocks[stage])
   else:f.seek(a.stages[stage]);o.write(f.read(end-a.stages[stage]))
  f.seek(4);directory=bytearray(xor_words(f.read(12+20*a.header['section_count']),a.seed,a.seed^0xf0f0))
  for i in range(a.header['section_count']):
   p=12+20*i;name=directory[p:p+16].split(b'\0')[0].decode();assert offsets[name]%2048==0
   struct.pack_into('<I',directory,p+16,offsets[name]//2048)
  o.seek(4);o.write(xor_words(directory,a.seed,a.seed^0xf0f0))
 check=Archive(output);verified=0
 for stage in stages:
  if stage not in blocks:
   idx=stages.index(stage);old_end=a.stages[stages[idx+1]] if idx+1<len(stages) else a.size
   new_end=check.stages[stages[idx+1]] if idx+1<len(stages) else check.size
   assert old_end-a.stages[stage]==new_end-check.stages[stage]
   with original.open('rb') as f,output.open('rb') as o:
    f.seek(a.stages[stage]);o.seek(check.stages[stage]);assert f.read(old_end-a.stages[stage])==o.read(new_end-check.stages[stage])
   continue
  seen=set();old_groups=a.groups(stage);new_groups=check.groups(stage)
  assert len(old_groups)==len(new_groups)
  for old_g,g in zip(old_groups,new_groups):
   assert old_g['folder']==g['folder']
   if g['folder'] not in ['cache','nocache']:
    assert a.decode(old_g)==check.decode(g),'Changed unrelated group: '+stage+' '+g['folder']
    continue
   d=check.decode(g)
   for f in g['files']:
    if f['name'] in expected[stage]:
     assert d[f['offset']:f['offset']+f['size']]==expected[stage][f['name']],stage+' '+f['name']
     seen.add(f['name']);verified+=1
  assert seen==set(expected[stage]),'Missing original or imported files: '+stage
 pool_paths=audit_campaign_pool_paths(check,plans)
 (out/'all-pool-path-audit.json').write_text(json.dumps(pool_paths,indent=2))
 if any(r['possible_gap_entries'] or r['duplicate_pool_entries'] or r['unresolved_entries'] for r in pool_paths):
  raise ValueError('Unsafe or unresolved native respawn pool path; see all-pool-path-audit.json')
 report=dict(format=1,seed=seed,status='regular-enemy archive preview only; not installed',source_sha256=SOURCE,patched_sha256=sha(output),stages=plans,excluded=excluded,atlas_aliases=aliases,original_and_imported_files_verified=verified,actor_reference_adapter=True,bosses_implemented=False,subweapons_implemented=False,metatron_implemented=False)
 report['native_pool_dependencies']=campaign_pool_dependencies(plans)
 report['regular_enemy_runtime_ready']=False
 report['additional_enemy_systems']=scope.get('additional_enemy_systems',[])
 (out/'manifest.json').write_text(json.dumps(report,indent=2));print('Verified',len(blocks),'modified stages;',verified,'original and imported files;',len(excluded),'stages blocked',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--seed',required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();build(args.seed,args.output)
