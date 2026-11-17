import portable_paths as _portable
"""Rerolled compatible music banks and explicitly named ADA gameplay media."""
import sys,json,hashlib,struct,subprocess,xml.etree.ElementTree as ET,re,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1];W=R.parent;OUT=R/'Ship-v5'
L=Path(str(_portable.LEGACY))
GAME=Path(str(_portable.game()))
SOUND=GAME/'sound/Windows';V3=W/'full-preview-v3/Full-Preview-v3'
SEED=json.loads((R/'seed.json').read_text())['seed']
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,o):p.write_text(json.dumps(o,indent=2)+'\n')
def clean(rel):
 from beta_support import pristine_audio
 return pristine_audio(rel)

def fnv(name):
 h=2166136261
 for c in name.lower().encode('ascii'):h=((h*16777619)^c)&0xffffffff
 return h
def objects(b):
 p=0;chunks=[]
 while p<len(b):
  tag,n=struct.unpack_from('<4sI',b,p);assert p+8+n<=len(b);chunks.append((tag,b[p+8:p+8+n]));p+=8+n
 assert p==len(b)
 payload=next(x for tag,x in chunks if tag==b'HIRC');n=struct.unpack_from('<I',payload)[0];p=4;rows={}
 for _ in range(n):
  kind,length,identity=struct.unpack_from('<BII',payload,p);assert identity not in rows
  rows[identity]=(kind,payload[p+9:p+5+length]);p+=5+length
 assert p==len(payload)
 return chunks,rows
def build():
 audio=OUT/'audio/files';audio.mkdir(parents=True,exist_ok=True)
 tree=ET.parse(SOUND/'SoundbanksInfo.xml');patches=[]
 # BAHRAM ba01 uses Play1/2/3 and State1/2/3/4. These three authored
 # multi-track peers lack only Play2. Alias that cue to their authored Play3.
 for family in ('02b2c6','02f1f8','012d21'):
  rel='us00'+family+'.bnk';bank=next(b for b in tree.findall('.//SoundBanks/SoundBank') if b.findtext('Path')==rel)
  source=next(e for e in bank.findall('./IncludedEvents/Event') if e.attrib.get('Name')=='Play_Music_'+family+'_3')
  eventname='Play_Music_'+family+'_2';newid=fnv(eventname);assert fnv(source.attrib['Name'])==int(source.attrib['Id'])
  before=clean(rel);chunks,rows=objects(before);assert newid not in rows
  srcid=int(source.attrib['Id']);assert rows[srcid][0]==4
  changed=dict(rows);changed[newid]=rows[srcid]
  body=struct.pack('<I',len(changed))+b''.join(struct.pack('<BII',k,len(data)+4,identity)+data for identity,(k,data) in changed.items())
  after=b''.join(tag+struct.pack('<I',len(body if tag==b'HIRC' else data))+(body if tag==b'HIRC' else data) for tag,data in chunks)
  achunks,arows=objects(after);assert all(arows[k]==v for k,v in rows.items()) and arows[newid]==rows[srcid]
  assert [(t,b) for t,b in achunks if t!=b'HIRC']==[(t,b) for t,b in chunks if t!=b'HIRC']
  (audio/rel).write_bytes(after)
  attrs=dict(source.attrib);attrs.update(Id=str(newid),Name=eventname,ObjectPath=source.attrib['ObjectPath'].rsplit('\\',1)[0]+'\\'+eventname)
  ET.SubElement(bank.find('./IncludedEvents'),'Event',attrs)
  patches.append(dict(relative_path='sound/Windows/'+rel,package_path='audio/files/'+rel,expected_before_sha256=sha((SOUND/rel).read_bytes()),patched_sha256=sha(after),clean_sha256=sha(before),added_event=eventname,aliases_authored_event=source.attrib['Name'],other_objects_and_chunks_unchanged=True))
 # Reuse the previously machine-tested bank-selection boundary and native tests.
 text=(W/'full-preview-v3/source/build_music_tracks.py').read_text()
 text=text.replace("ROOT=Path(__file__).resolve().parents[1]",'ROOT='+repr(str(R))+'\nROOT=Path(ROOT)')
 text=text.replace("SEED='full-music-2026-10-18-v3'",'SEED='+repr(SEED+'/music'))
 text=text.replace('Full-Preview-v3/','Ship-v5/')
 text=text.replace("tree=ET.parse(GAME/'sound/Windows/SoundbanksInfo.xml')","tree=ET.parse(ROOT/'reports/music-metadata.xml')")
 text=text.replace('families={};ineligible=[]',"regular.update(json.loads((LEGACY/'full-game-scope.json').read_text())['regular_stages'])\n families={};ineligible=[]")
 # Authored Multitrack/Linear structure and complete Play/State signatures
 # remain exact; battle/boss labels no longer split otherwise identical peers.
 text=text.replace("regular=set(r['stage']", "regular=set(r['stage']")
 text=text.replace("if family in protected or category is None:","if family in protected or category is None:")
 text=text.replace("buckets[(row['category'],tuple(row['native_structure']),tuple(row['signature']))]", "buckets[('compatible-gameplay',tuple(row['native_structure']),tuple(row['signature']))]")
 text=text.replace("if __name__=='__main__':build()",'build()')
 tree.write(R/'reports/music-metadata.xml',encoding='utf-8')
 exec(compile(text,str(Path(__file__)), 'exec'),{'__file__':str(Path(__file__)),'__name__':'build_music_v5'})
 # Expand from two hardcoded pairs to a seed-selected derangement of all five
 # explicitly ADA-labelled gameplay tokens, paired across processed variants.
 media={}
 for f in tree.findall('.//StreamedFiles/File'):
  name=f.findtext('ShortName') or '';match=re.fullmatch(r'(vc[0-9a-f]+)(?:_eng|_jpn)?_360(_pp)?_ada\.wav',name)
  if match and f.attrib.get('Language')=='English(US)':media[(match[1],bool(match[2]))]=(name,'English(US)/'+f.attrib['Id']+'.wem')
 tokens=sorted({k[0] for k in media});assert len(tokens)==5 and all((t,p) in media for t in tokens for p in (False,True))
 order=sorted(tokens,key=lambda t:hashlib.sha256((SEED+'/ada/'+t).encode()).digest());mapping={t:order[(i+1)%len(order)] for i,t in enumerate(order)};voices=[]
 def fmt(b):
  assert b[:4]==b'RIFF' and b[8:12]==b'WAVE' and b[12:16]==b'fmt '
  return struct.unpack_from('<HHI',b,20)
 for token in tokens:
  for processed in (False,True):
   name,rel=media[token,processed];source_name,source_rel=media[mapping[token],processed];before=clean(rel);payload=clean(source_rel)
   assert fmt(before)==fmt(payload)
   path=audio/rel;path.parent.mkdir(exist_ok=True);path.write_bytes(payload)
   voices.append(dict(relative_path='sound/Windows/'+rel,package_path='audio/files/'+rel,expected_before_sha256=sha((SOUND/rel).read_bytes()),patched_sha256=sha(payload),source_cue=source_name,destination_cue=name,processed=processed,codec_channels_rate=fmt(payload)))
 m=json.loads((OUT/'manifest.json').read_text());m['music_track_shuffle']=json.loads((R/'reports/music-tracks-verification.json').read_text())
 m['ada_overlay']=dict(seed=SEED+'/ada',mapping=mapping,files=voices,voice_files=len(voices),voice_scope='Five explicitly ADA-labelled English gameplay tokens, normal and processed; broader dialogue and cutscene coverage unimplemented',actual_voice_triggering_verified=False,gameplay_verified=False)
 for bank in m['original_music_banks']:
  patch=next((r for r in patches if r['relative_path']=='sound/Windows/'+bank['file']),None)
  if patch:bank['sha256']=patch['patched_sha256']
 m['music_compatibility_bank_patches']=patches
 save(OUT/'manifest.json',m);save(R/'reports/audio-install-files.json',patches+voices)
 save(R/'reports/ada-verification.json',m['ada_overlay'])
 print('ADA',len(voices),'files',mapping,flush=True)
if __name__=='__main__':build()
