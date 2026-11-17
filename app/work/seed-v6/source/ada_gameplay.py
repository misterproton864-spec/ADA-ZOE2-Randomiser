import portable_paths as _portable
"""Seeded compatible streamed speech, with the native voice bank kept intact.

v6.4.1 removes the v6.4 shared-bank event rewrite after reported voice silence.
Sound nodes, events, actions and dialogue lifecycle now remain byte-identical.
"""
import hashlib,json,re,struct,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def digest(b):return hashlib.sha256(b).hexdigest()

def fnv(name):
 h=2166136261
 for c in name.lower().encode('ascii'):h=((h*16777619)^c)&0xffffffff
 return h

def objects(b):
 chunks=[];p=0
 while p<len(b):
  tag,n=struct.unpack_from('<4sI',b,p);assert p+8+n<=len(b)
  chunks.append((tag,b[p+8:p+8+n]));p+=8+n
 assert p==len(b)
 data=next(v for t,v in chunks if t==b'HIRC');n=struct.unpack_from('<I',data)[0];p=4;rows={}
 for _ in range(n):
  kind,length,identity=struct.unpack_from('<BII',data,p);assert identity not in rows
  rows[identity]=(kind,data[p+9:p+5+length]);p+=5+length
 assert p==len(data)
 return chunks,rows

def stream_format(b):
 assert b[:4]==b'RIFF' and b[8:12]==b'WAVE'
 assert struct.unpack_from('<I',b,4)[0]+8==len(b)
 pos=12;chunks={}
 while pos+8<=len(b):
  tag,n=struct.unpack_from('<4sI',b,pos);assert pos+8+n<=len(b)
  chunks[tag]=(pos+8,n);end=pos+8+n
  # Native Wwise streams may omit padding after the final odd data chunk.
  pos=end+(n%2 if end<len(b) else 0)
 assert pos==len(b) and b'fmt ' in chunks and b'data' in chunks
 p,n=chunks[b'fmt '];assert n>=18
 tag,channels,rate=struct.unpack_from('<HHI',b,p)
 return dict(codec_tag=tag,channels=channels,sample_rate=rate,fmt_size=n,
  block_bits_extra=b[p+12:p+18].hex(),data_offset=chunks[b'data'][0])

def expanded_groups(media,leftovers,audibility):
 """Whole streams retain exact codec/header requirements; destination routing stays native.

 DirectParentID belongs to the unchanged destination sound node, not the WEM.
 Extend only the old singleton pool so previously shuffled cues never revert.
 """
 groups=collections.defaultdict(list)
 fields=('StreamType','bPrefetch','ulPluginID','uBitsPositioning','uInMemoryMediaSize','uSourceBits')
 for rel in leftovers:
  item=media[rel]
  key=(tuple(item['format'].items()),tuple(item['nodes'][0][k] for k in fields))
  groups[key].append(rel)
 result=[]
 for values in groups.values():
  cluster=[]
  for rel in sorted(values,key=lambda r:(audibility[r]['seconds'],r)):
   if cluster:
    low=audibility[cluster[0]]['seconds'];high=audibility[rel]['seconds']
    if high>2*low or high-low>5:result.append(cluster);cluster=[]
   cluster.append(rel)
  if cluster:result.append(cluster)
 return result

def build(tree,out,seed,sound,legacy_clean):
 out=Path(out);cache=_portable.HOME/'audio-clean-originals';cache.mkdir(exist_ok=True)
 index_path=cache/'index.json';index=json.loads(index_path.read_text()) if index_path.exists() else {}
 table=json.loads((ROOT/'voice-stream-compatibility.json').read_text());nodes=table['nodes']
 audibility=json.loads((ROOT/'voice-audibility.json').read_text())['files']
 def pristine(rel):
  p=cache/rel
  if p.exists():
   b=p.read_bytes()
   if rel not in index:assert b==legacy_clean(rel);index[rel]=digest(b)
   assert digest(b)==index[rel]
  else:
   b=legacy_clean(rel);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);index[rel]=digest(b)
  return b
 native=pristine(table['native_bank']);assert digest(native)==table['native_bank_sha256']
 media={};groups=collections.defaultdict(list);excluded=[]
 fields=('StreamType','bPrefetch','ulPluginID','DirectParentID','uBitsPositioning','uInMemoryMediaSize','uSourceBits')
 for f in tree.findall('.//StreamedFiles/File'):
  if f.get('Language')!='English(US)':continue
  name=f.findtext('ShortName') or '';explicit=re.fullmatch(r'(vc[0-9a-f]+)(?:_eng|_jpn)?_360(_pp)?_ada\.wav',name)
  if not (name.startswith('vca') or name=='vcc06202.wav' or explicit):continue
  rel='English(US)/'+f.get('Id')+'.wem';b=pristine(rel);fmt=stream_format(b)
  audible=audibility[rel];assert digest(b)==audible['sha256']
  ns=nodes.get(f.get('Id'),[])
  item=dict(name=name,data=b,format=fmt,nodes=ns);media[rel]=item
  reason=None
  if not audible['audible']:reason='Native silent/near-silent placeholder remains native and is excluded as a donor'
  elif explicit:reason='Paired processed/normal cues retain native media pending audible verification'
  elif len(ns)!=1 or ns[0]['StreamType']!=2 or ns[0]['bPrefetch']!=0:reason='Embedded, prefetched or ambiguous source remains native'
  elif fmt['channels']!=1:reason='Only confirmed mono gameplay stream layout is enabled'
  if reason:excluded.append(dict(file=rel,cue=name,reason=reason));continue
  # Keep exact native streaming/header parameters, bus/position behavior and
  # roughly similar clip lengths. Move complete WEMs; never splice codec data.
  key=(tuple(fmt.items()),tuple(ns[0][k] for k in fields),len(b).bit_length()-1)
  groups[key].append(rel)
 mapping={};leftovers=[]
 for values in groups.values():
  order=sorted(values,key=lambda rel:hashlib.sha256((seed+'\0ada-stream-v1\0'+rel).encode()).digest())
  if len(order)<2:
   leftovers.extend(order);continue
  mapping.update({r:order[(i+1)%len(order)] for i,r in enumerate(order)})
 legacy_count=len(mapping);expanded=set()
 for values in expanded_groups(media,leftovers,audibility):
  order=sorted(values,key=lambda rel:hashlib.sha256((seed+'\0ada-expanded-stream-v1\0'+rel).encode()).digest())
  if len(order)<2:
   excluded.extend(dict(file=r,cue=media[r]['name'],reason='No second header-compatible stream within duration bounds') for r in order);continue
  mapping.update({r:order[(i+1)%len(order)] for i,r in enumerate(order)});expanded.update(order)
 from ada_cycle_expansion import expand
 singletons=[r['file'] for r in excluded if r['reason']=='No second header-compatible stream within duration bounds']
 mapping,inserted,changed=expand(mapping,singletons,media,audibility,seed)
 expanded.update(changed)
 excluded=[r for r in excluded if r['file'] not in inserted]
 legacy_count=len(set(mapping)-expanded)
 rows=[];changes=[]
 bank=table['native_bank'];p=out/'audio/files'/bank;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(native)
 rows.append(dict(relative_path='sound/Windows/'+bank,package_path='audio/files/'+bank,
  expected_before_sha256=digest((sound/bank).read_bytes()),patched_sha256=digest(native),clean_sha256=digest(native),native_voice_bank_restored=True))
 for rel,item in sorted(media.items()):
  source=mapping.get(rel,rel);donor=media[source];b=donor['data']
  if source!=rel:
   assert donor['format']==item['format']
   required=tuple(k for k in fields if rel not in expanded or k!='DirectParentID')
   assert tuple(donor['nodes'][0][k] for k in required)==tuple(item['nodes'][0][k] for k in required)
   changes.append(dict(destination=rel,source=source,destination_cue=item['name'],source_cue=donor['name'],
    destination_clean_sha256=digest(item['data']),source_clean_sha256=digest(b),format=item['format'],native_source=item['nodes'][0],
    compatibility_tier='expanded' if rel in expanded else 'legacy',destination_duration_seconds=audibility[rel]['seconds'],source_duration_seconds=audibility[source]['seconds']))
  path=out/'audio/files'/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b)
  rows.append(dict(relative_path='sound/Windows/'+rel,package_path='audio/files/'+rel,
   expected_before_sha256=digest((sound/rel).read_bytes()),patched_sha256=digest(b),clean_sha256=digest(item['data']),
   source_cue=donor['name'],destination_cue=item['name'],shuffled=source!=rel))
 index_path.write_text(json.dumps(index,indent=2)+'\n')
 report=dict(format=2,seed=seed+'/ada',mapping=mapping,files=rows,voice_files=len(media),voice_events=0,
  shuffled_streams=len(changes),stream_changes=changes,routes=[],excluded=excluded,
  legacy_shuffled_streams=legacy_count,expanded_shuffled_streams=len(expanded),cycle_inserted_streams=len(inserted),
  voice_scope='Compatible English mono vca gameplay streams and confirmed vcc06202; prior shuffle preserved, plus header-compatible singleton groups and cycle insertion within 2x duration and 5 seconds; incompatible/paired cues retain native media',
  speaker_evidence='User confirmed vca0200e, vca0501a and vcc06202 as ADA; remaining vca membership inferred',
  method='Complete compatible streamed WEM permutation; native voice bank, events, actions and sound metadata unchanged',
  native_voice_bank=dict(file=bank,sha256=digest(native),byte_identical=True),
  silent_placeholder_donors_excluded=True,source_audio_fully_decoded=True,
  prior_bank_event_rewrite_removed=True,actual_voice_triggering_verified=False,gameplay_verified=False)
 assert report['shuffled_streams']>=100,report['shuffled_streams']
 (out/'ada-gameplay-mapping.json').write_text(json.dumps(report,indent=2)+'\n')
 return rows,report
