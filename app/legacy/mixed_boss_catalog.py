import portable_paths as _portable
"""Full intended boss pool and explicitly experimental combat donor profiles."""
import hashlib,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'research'))
from zoe2_archive import Archive,strcode32
from campaign_boss_encounters import build_encounters,shuffle_with_arena_constraints
from boss_spawn_contracts import decode_story_boss,NEPHTIS_STORY,INHERT_STORY
from scx_mixed_boss_handoff import completion
ORIGINAL=Path(str(_portable.ORIGINALS / 'ZOE2/STAGE.DAT'))

def payloads(archive,stage):
 files={}
 for group in archive.groups(stage):
  if group['folder'] not in ('cache','nocache'):continue
  bits=archive.decode(group)
  for row in group['files']:
   data=bits[row['offset']:row['offset']+row['size']]
   if row['name'] in files:raise ValueError('Duplicate cached resource')
   files[row['name']]=data
 return files

def catalog(seed):
 archive=Archive(ORIGINAL);source=json.loads((ROOT/'campaign-boss-source-catalog.json').read_text())
 encounters=build_encounters(source);profiles={};cache={};sources={};retained=[]
 for encounter in encounters:
  if not encounter['randomise']:continue
  stage=encounter['encounter'];files=cache.setdefault(stage,payloads(archive,stage));combat=[]
  for row in encounter['source_sites']:
   raw=json.loads((ROOT/row['source']).read_text())
   raw=raw if isinstance(raw,list) else [raw]
   matches=[r for r in raw if r['stage']==stage and r['offset']==row['offset']]
   if len(matches)!=1:raise ValueError('Ambiguous source provenance')
   row=dict(row,**{k:matches[0][k] for k in ('file','source_sha256')})
   data=files[row['file']]
   if hashlib.sha256(data).hexdigest()!=row['source_sha256']:raise ValueError('Original script contract mismatch')
   command=int(row['hash'],16) if row.get('hash') else NEPHTIS_STORY
   contract=decode_story_boss(data,row['offset'],command)
   if completion(contract) is None or (command==0xef9a96d8 and contract['source_option']['value']==1):
    retained.append(dict(stage=stage,offset=row['offset'],reason='Original cinematic/native scene creation retained'));continue
   combat.append(dict(data=data,offset=row['offset'],command=command,file=row['file'],contract=contract))
  if not combat:raise ValueError('Encounter has no combat donor')
  if stage=='fr02':combat.sort(key=lambda r:r['contract']['variant'])
  sources[stage]=combat
  # Nephtis combat profiles use passed autonomous phase3 with the same native factory.
  profiles[stage]=dict(encounter=stage,boss=encounter['boss'],protected=False,templates=combat,
   asset_donor='ba02' if encounter['boss']=='Nephtis' else stage)
 return archive,encounters,profiles,sources,retained,shuffle_with_arena_constraints(encounters,seed),cache

def assets(archive,profile):
 donor=profile['asset_donor'];files=payloads(archive,donor)
 names=dict(line.split('|',1) for line in (ROOT/'research/JoyDict/common.tbl').read_text().splitlines() if '|' in line)
 boss=profile['boss']
 if boss=='Nephtis':
  keys={r['key'] for r in json.loads((ROOT/'first-boss-expanded-asset-catalog.json').read_text())['files']}
 elif boss=='Ardjet':prefixes=('wad_','cell_','ardjet');keys={k for k in files if names.get(k,'').startswith(prefixes)}
 elif boss=='Vic Viper':prefixes=('cls_','viv_','bws_');keys={k for k in files if names.get(k,'').startswith(prefixes)}
 elif boss=='Inhert':prefixes=('inh_','inhert');keys={k for k in files if names.get(k,'').startswith(prefixes)}
 else:
  prefixes=('abs_','anubis','aas_','aumaan');keys={k for k in files if names.get(k,'').startswith(prefixes)}
 keys={k for k in keys if k.endswith(('.tex','.mdz','.mtl','.mts','.flw','.cvz'))}
 # Native actor setup also requests geometry using the model's name hash.
 # Keep donor CVZ resources for selected models, including Nephtis's expanded
 # catalog, which originally covered only rendering and motion resources.
 keys.update(k[:-4]+'.cvz' for k in list(keys) if k.endswith('.mdz') and k[:-4]+'.cvz' in files)
 # Aumaan's native setup requests both its own geometry and this companion
 # player geometry by explicit hash; the latter is outside the boss prefixes.
 if boss=='Aumaan Anubis':keys.add('4c8c71d9.cvz')
 # Compressed-space Anubis's setup (1478506b0) explicitly requests the
 # player's break geometry through 148be4da0. It does not share the boss
 # prefix or model hash. Crash 19848 reached 148be3232 with this lookup
 # returning null; the saved caller resource ID was 827e775a.
 if boss=='Compressed-space Anubis':keys.add('827e775a.cvz')
 textures=set();motions=[]
 for key in list(keys):
  data=files[key]
  if key.endswith('.mdz'):
   textures.add(f'{struct.unpack_from("<I",data,32)[0]:08x}.tex')
  if key.endswith('.mts'):
   pointer=struct.unpack_from('<I',data)[0]
   library=data[pointer:].split(b'\0',1)[0].decode('ascii')
   name=f'{strcode32(library):08x}.mtl';keys.add(name);motions.append(dict(script=key,library=name))
 keys.update(textures)
 missing=keys-files.keys()
 if missing:raise ValueError('Missing actor asset dependencies: '+str(sorted(missing)))
 order={'.tex':0,'.mdz':1,'.mtl':2,'.mts':3,'.flw':4,'.cvz':5}
 selected={k:files[k] for k in sorted(keys,key=lambda n:(order[Path(n).suffix],n))}
 aliases={}
 for label in ('main','small'):
  index={line.split('\t')[0] for line in (ROOT/'Loader-Test'/(label+'-index.txt')).read_text().splitlines() if len(line.split('\t'))==3}
  pairs={}
  for tex in textures:
   for suffix in ('.dat','.tbl'):
    key=f'@{donor}_{tex[:8]}{suffix}'
    if key not in index:raise ValueError('Missing donor texture atlas entry '+label+'/'+key)
    pairs[tex[:8]+suffix]=key
  aliases[label]=pairs
 return selected,aliases,dict(donor=donor,files=[dict(name=k,sha256=hashlib.sha256(v).hexdigest()) for k,v in selected.items()],
  motion_dependencies=motions,cvz_geometry_files=sorted(k for k in selected if k.endswith('.cvz')),model_texture_dependencies_verified=True,secondary_effect_closure_verified=False)
