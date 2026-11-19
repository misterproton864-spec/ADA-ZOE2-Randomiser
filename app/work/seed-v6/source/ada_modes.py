"""Two ADA stream modes; native events, actions and routing are preserved."""
import hashlib,json,math,re,struct
from pathlib import Path
import portable_paths as pp
ROOT=Path(__file__).resolve().parents[1]
MODES=('semi','chaos')

def scene_ada(cue):
 return re.fullmatch(r's[0-9]+m[0-9]+_(?:Re_)?Ada_E(?:ab|bb)?\.wav',cue) is not None

def identified_ada(cue):
 return (cue.startswith('vca') or cue=='vcc06202.wav' or scene_ada(cue)
         or re.fullmatch(r'vc[0-9a-f]+(?:_eng|_jpn)?_360(?:_pp)?_ada\.wav',cue) is not None)
def digest(b):return hashlib.sha256(b).hexdigest()
def source_path(rel):
 # Fresh tester profiles have the verified shared originals, but no legacy
 # audio-clean-originals tree. Reuse those originals instead of copying them.
 for root in (pp.ORIGINALS/'sound/Windows',pp.HOME/'audio-clean-originals'):
  path=root/rel
  if path.is_file():return path
 raise FileNotFoundError('Verified original ADA stream is unavailable: '+rel)
def protected_cues(media,audibility):
 catalog_path=ROOT/'ada-context-protection.json'
 catalog=json.loads(catalog_path.read_text()) if catalog_path.exists() else {}
 known=set(catalog.get('protected',[]));reasons={}
 for rel,item in media.items():
  cue=item['name']
  if rel in known:reasons[rel]='Mission/weapon guidance identified in the local cue audit'
  elif re.match(r'vca(?:01|0c|0d)',cue):reasons[rel]='Conservative story/tutorial cue family retained in native context'
  elif cue.endswith('_ada.wav') or scene_ada(cue):reasons[rel]='Authored scene dialogue retained in native context'
  elif audibility[rel]['seconds']>12:reasons[rel]='Long instruction/dialogue retained in native context'
 return reasons
def select(media,audibility,seed,mode):
 if mode not in MODES:raise ValueError('ADA mode must be Semi-random or Chaos ADA')
 spoken={r for r in media if audibility[r]['audible']}
 protected=protected_cues(media,audibility) if mode=='semi' else {}
 eligible=spoken-set(protected)
 rank=lambda r:hashlib.sha256((str(seed)+'\0ada-'+mode+'-v1\0'+r).encode()).digest()
 selected=sorted(eligible,key=rank)
 if mode=='semi':selected=selected[:min((len(spoken)+1)//2,len(selected))]
 if len(selected)<2:raise ValueError('Not enough ADA lines remain for the selected mode')
 offsets=sorted((n for n in range(1,len(selected)) if math.gcd(n,len(selected))==1),key=lambda n:hashlib.sha256((str(seed)+'\0ada-offset\0'+str(n)).encode()).digest())
 for offset in offsets:
  mapping={r:selected[(i+offset)%len(selected)] for i,r in enumerate(selected)}
  if all(media[a]['data']!=media[b]['data'] for a,b in mapping.items()):break
 else:raise ValueError('ADA sources cannot produce a complete non-identical shuffle')
 if mode=='chaos' and set(mapping)!=spoken:raise ValueError('Chaos ADA must cover every audible identified ADA stream')
 from voice_routing import constrain
 return constrain(mapping,media,audibility,seed),protected
def build(tree,out,seed,sound,legacy_clean):
 from ada_gameplay import stream_format
 out=Path(out);settings=json.loads((out/'manifest.json').read_text()).get('settings',{});mode=settings.get('ada_mode','semi')
 table=json.loads((ROOT/'voice-stream-compatibility.json').read_text());audibility=json.loads((ROOT/'voice-audibility.json').read_text())['files']
 offsets=json.loads((ROOT/'ada-source-field-offsets.json').read_text());cache=pp.HOME/'audio-clean-originals'
 native=source_path(table['native_bank']).read_bytes()
 if digest(native)!=table['native_bank_sha256'] or digest(native)!=offsets['bank_sha256']:raise ValueError('Native ADA bank differs')
 media={}
 for f in tree.findall('.//StreamedFiles/File'):
  if f.get('Language')!='English(US)':continue
  cue=f.findtext('ShortName') or ''
  if not identified_ada(cue):continue
  rel='English(US)/'+f.get('Id')+'.wem';source=source_path(rel)
  data=source.read_bytes()
  if rel not in audibility or digest(data)!=audibility[rel]['sha256']:raise ValueError('ADA source fingerprint differs: '+cue)
  nodes=table['nodes'].get(f.get('Id'),[]);positions=offsets['nodes'].get(f.get('Id'),[])
  if audibility[rel]['audible'] and (len(nodes)!=1 or len(positions)!=1 or nodes[0]['StreamType']!=2 or nodes[0]['bPrefetch']!=0):raise ValueError('ADA source has an unaudited embedded/prefetched route: '+cue)
  media[rel]=dict(name=cue,data=data,format=stream_format(data),node=nodes[0] if nodes else {},offsets=positions[0] if positions else {})
 if set(media)!=set(audibility):raise ValueError('ADA coverage catalogue differs from the installed metadata')
 mapping,protected=select(media,audibility,seed,mode)
 bank=bytearray(native);bank_changes=[];stream_changes=[];rows=[]
 for rel,item in sorted(media.items()):
  donor_rel=mapping.get(rel,rel);donor=media[donor_rel]
  if donor_rel!=rel and (donor['node']['ulPluginID']!=item['node']['ulPluginID'] or donor['node']['uSourceBits']!=item['node']['uSourceBits']):raise ValueError('ADA codec plugin contract differs')
  # Whole WEMs keep the donor's complete codec/header. The native SFX source
  # must read the donor header size, rather than the previous clip's size.
  field=item['offsets'].get('uInMemoryMediaSize');value=donor['node'].get('uInMemoryMediaSize')
  if donor_rel!=rel and field['value']!=value:
   off=field['offset'];before=bank[off:off+4];assert int.from_bytes(before,'little')==field['value'];struct.pack_into('<I',bank,off,value)
   bank_changes.append(dict(destination=rel,source=donor_rel,offset=off,before=bytes(before).hex(),after=struct.pack('<I',value).hex(),field='uInMemoryMediaSize'))
  data=donor['data'];path=out/'audio/files'/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
  if donor_rel!=rel:stream_changes.append(dict(destination=rel,source=donor_rel,destination_cue=item['name'],source_cue=donor['name'],destination_clean_sha256=digest(item['data']),source_clean_sha256=digest(data),destination_format=item['format'],source_format=donor['format']))
  rows.append(dict(relative_path='sound/Windows/'+rel,package_path='audio/files/'+rel,expected_before_sha256=digest((sound/rel).read_bytes()),patched_sha256=digest(data),clean_sha256=digest(item['data']),source_cue=donor['name'],destination_cue=item['name'],shuffled=donor_rel!=rel))
 rel=table['native_bank'];path=out/'audio/files'/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(bank)
 rows.insert(0,dict(relative_path='sound/Windows/'+rel,package_path='audio/files/'+rel,expected_before_sha256=digest((sound/rel).read_bytes()),patched_sha256=digest(bank),clean_sha256=digest(native),native_voice_bank_restored=not bank_changes,voice_bank_source_metadata_only=True))
 spoken=sum(audibility[r]['audible'] for r in media)
 report=dict(format=3,seed=seed+'/ada',mode=mode,enabled=True,mapping=mapping,files=rows,voice_files=len(media),audible_voice_files=spoken,silent_placeholders=len(media)-spoken,
  shuffled_streams=len(mapping),stream_changes=stream_changes,voice_events=0,routes=[],excluded=[dict(file=r,cue=media[r]['name'],reason=protected.get(r,'Silent placeholder is not a spoken voice line')) for r in media if r not in mapping],
  protected_context=protected,bank_source_metadata_changes=bank_changes,legacy_shuffled_streams=0,expanded_shuffled_streams=len(mapping),
  chaos_complete=mode=='chaos' and len(mapping)==spoken,semi_fraction=len(mapping)/spoken,
  native_voice_bank=dict(file=rel,sha256=digest(bank),original_sha256=digest(native),byte_identical=not bank_changes),
  native_events_actions_and_routing_unchanged=True,prior_bank_event_rewrite_removed=True,silent_placeholder_donors_excluded=True,
  voice_scope='Every identified audible English ADA stream in Chaos; about half, with conservative context protection, in Semi-random',
  speaker_evidence='Native vca naming, explicit ADA suffixes, twelve explicitly named English Ada_E scene recordings, and the previously user-confirmed vcc06202 cue',
  actual_voice_triggering_verified=False,gameplay_verified=False)
 from voice_routing import summary
 report['playback_compatibility']=summary(mapping,media,audibility)
 (out/'ada-gameplay-mapping.json').write_text(json.dumps(report,indent=2)+'\n')
 return rows,report
def verify(package):
 p=Path(package);r=json.loads((p/'ada-gameplay-mapping.json').read_text());table=json.loads((ROOT/'voice-stream-compatibility.json').read_text());aud=json.loads((ROOT/'voice-audibility.json').read_text())['files'];cache=pp.HOME/'audio-clean-originals'
 native=source_path(table['native_bank']).read_bytes();expected=bytearray(native);allowed=set()
 offsets=json.loads((ROOT/'ada-source-field-offsets.json').read_text())['nodes']
 if r.get('enabled',True):
  derived=[]
  for rel,source in sorted(r['mapping'].items()):
   field=offsets[Path(rel).stem][0]['uInMemoryMediaSize'];value=table['nodes'][Path(source).stem][0]['uInMemoryMediaSize']
   if value!=field['value']:derived.append(dict(destination=rel,source=source,offset=field['offset'],before=struct.pack('<I',field['value']).hex(),after=struct.pack('<I',value).hex(),field='uInMemoryMediaSize'))
  if derived!=r['bank_source_metadata_changes']:raise ValueError('ADA source-header metadata differs from native field evidence')

 if r.get('enabled',True):
  for edit in r['bank_source_metadata_changes']:
   q=edit['offset'];before=bytes.fromhex(edit['before']);after=bytes.fromhex(edit['after'])
   if expected[q:q+4]!=before or len(after)!=4 or allowed&set(range(q,q+4)):raise ValueError('Invalid ADA source metadata patch')
   expected[q:q+4]=after;allowed.update(range(q,q+4))
 if (p/'audio/files'/table['native_bank']).read_bytes()!=expected:raise ValueError('ADA event/action/routing bytes changed')
 mapping=r['mapping'];spoken={rel for rel,item in aud.items() if item['audible']}
 if set(mapping)!=set(mapping.values()) or any(a==b for a,b in mapping.items()):raise ValueError('ADA mapping is not a complete derangement')
 if r.get('enabled',True) and r['mode']=='chaos' and set(mapping)!=spoken:raise ValueError('Chaos ADA left a spoken line native')
 if r['mode']=='semi' and set(mapping)&set(r['protected_context']):raise ValueError('Semi-random replaced protected guidance')
 media={}
 from ada_gameplay import stream_format
 for rel,item in aud.items():
  data=source_path(rel).read_bytes()
  if digest(data)!=item['sha256']:raise ValueError('ADA original fingerprint differs: '+rel)
  media[rel]=dict(name=item['cue'],data=data,format=stream_format(data))
 from voice_routing import summary
 if r.get('enabled',True) and summary(mapping,media,aud)!=r['playback_compatibility']:raise ValueError('ADA playback compatibility report differs')
 for row in r['files']:
  rel=row['relative_path'].removeprefix('sound/Windows/')
  if rel==table['native_bank']:continue
  source=mapping.get(rel,rel)
  if (p/row['package_path']).read_bytes()!=source_path(source).read_bytes():raise ValueError('ADA media differs from seeded instructions')
  if source!=rel and not aud[source]['audible']:raise ValueError('Silent ADA donor')
 return dict(native_voice_events_actions_and_routing_preserved=True,voice_stream_files_checked=len(mapping),mode=r['mode'],audible_lines=len(spoken),chaos_complete=r.get('enabled',True) and r['mode']=='chaos' and set(mapping)==spoken,voice_in_game_audibility_verified=False)
