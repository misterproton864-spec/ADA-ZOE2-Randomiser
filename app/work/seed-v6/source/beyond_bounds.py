import portable_paths as _portable
"""Private gameplay donor from the native credits stream; originals untouched."""
import copy,hashlib,json,struct,shutil,math,xml.etree.ElementTree as ET
from pathlib import Path
from archive_tools import save,sha
ROOT=Path(__file__).resolve().parents[1]
SOUND=_portable.ORIGINALS/'sound/Windows'
FAMILY=0xf0b0;BANK='us0000f0b0.bnk';MEDIA=1965101901
TRIM_SECONDS=0.0;GAIN=4.5
TRACK_VOLUME_DB=-15.3
CREDITS_MEDIA=490090204
CREDITS_SAMPLES=16185024
CREDITS_SHA='a4d8dfeb6da05da786b8d971c6aa01a69ac6cfa393f127308c84ccc079c50df2'
def fnv(s):
 h=2166136261
 for c in s.lower().encode('ascii'):h=((h*16777619)^c)&0xffffffff
 return h
def prepare(tree,out):
 out=Path(out);audio=out/'audio/files';audio.mkdir(parents=True,exist_ok=True)
 source=SOUND/'us0002287f.bnk';data=bytearray(source.read_bytes());xml=ET.parse(ROOT/'native-music-bank.xml')
 assert sha(source)=='3701ccddf017b56d73ae5603b3ba5f5755c415600352867a17af2743f9482fb0','Native music template differs from the independently parsed input'
 nodes={}
 for o in xml.iter('object'):
  f=o.find("./field[@name='ulID']")
  if f is not None:nodes[int(f.get('value'))]=o
 def fields(o,name):return [f for f in o.iter('field') if f.get('name')==name and f.get('offset')]
 def value(o,name):return int(fields(o,name)[0].get('value'))
 template=next(b for b in tree.findall('.//SoundBank') if b.findtext('Path')=='us0002287f.bnk')
 events=[e for e in template.findall('./IncludedEvents/Event') if e.get('Name','').startswith(('Play_Music_02287f_','Set_State_02287f_'))]
 keep={int(e.get('Id')) for e in events}
 for id in list(keep):
  for f in nodes[id].iter('field'):
   if f.get('type')=='tid' and int(f.get('value')) in nodes:keep.add(int(f.get('value')))
 # The play action's target is the music root. State-setting action values
 # remain the native state-group/value IDs; those are not HIRC objects.
 for id in list(keep):
  for f in nodes[id].iter('field'):
   if f.get('type')=='tid' and int(f.get('value')) in nodes:keep.add(int(f.get('value')))
 roots=[id for id in keep if nodes[id].get('name')=='CAkMusicRanSeqCntr']
 if not roots:roots=[id for id in keep if 'MusicRanSeq' in nodes[id].get('name','')]
 assert len(roots)==1,roots
 root=nodes[roots[0]]
 segments={int(f.get('value')) for f in fields(root,'ulChildID')};assert len(segments)==2
 keep.update(segments);chosen={}
 for id in segments:
  children=fields(nodes[id],'ulChildID');assert children
  chosen[id]=next(int(f.get('value')) for f in children if value(nodes[int(f.get('value'))],'numSources')==1 and value(nodes[int(f.get('value'))],'numPlaylistItem')==1);keep.add(chosen[id])
 rename={id:fnv('zoe2-beyond-bounds-v1/'+str(id)) for id in keep}
 for e in events:rename[int(e.get('Id'))]=fnv(e.get('Name').replace('02287f','00f0b0'))
 assert len(set(rename.values()))==len(rename) and not set(rename.values())&set(nodes)
 source_duration=CREDITS_SAMPLES/48000*1000
 trim_ms=TRIM_SECONDS*1000;duration=source_duration-trim_ms
 assert 0<duration<=source_duration
 bodies=[]
 for id,o in sorted(((id,nodes[id]) for id in keep),key=lambda p:int(fields(p[1],'eHircType')[0].get('offset'))):
  pos=int(fields(o,'eHircType')[0].get('offset'));size=value(o,'dwSectionSize');body=bytearray(data[pos+5:pos+5+size]);kind=value(o,'eHircType')
  def patch(f,fmt,v):struct.pack_into(fmt,body,int(f.get('offset'))-pos-5,v)
  for f in o.iter('field'):
   if f.get('offset') and f.get('type') in ('sid','tid') and int(f.get('value')) in rename:patch(f,'<I',rename[int(f.get('value'))])
  if id in chosen.values():
   params=o.find(".//object[@name='NodeInitialParams']")
   volumes=[]
   for prop in params.iter('object'):
    pid=prop.find("./field[@name='pID']");v=prop.find("./field[@name='pValue']")
    if pid is not None and v is not None and int(pid.get('value'))==0:volumes.append(v)
   assert len(volumes)==1
   patch(volumes[0],'<f',TRACK_VOLUME_DB)
  if id==roots[0]:
   volume=[]
   params=o.find(".//object[@name='NodeInitialParams']")
   for prop in params.iter('object'):
    pid=prop.find("./field[@name='pID']");v=prop.find("./field[@name='pValue']")
    if pid is not None and v is not None and int(pid.get('value'))==0:volume.append(v)
   assert len(volume)==1
   patch(volume[0],'<f',float(volume[0].get('value'))+20*math.log10(GAIN))
  if id in chosen:
   for f in fields(o,'fDuration'):patch(f,'<d',duration)
   for f in fields(o,'fPosition'):patch(f,'<d',0 if float(f.get('value'))==0 else duration)
   count=fields(o,'ulNumChilds')[0];patch(count,'<I',1);children=fields(o,'ulChildID')
   patch(children[0],'<I',rename[chosen[id]])
   start=int(children[1].get('offset'))-pos-5;end=start+4*(len(children)-1);del body[start:end]
  if id in chosen.values():
   assert value(o,'numSources')==1 and value(o,'numPlaylistItem')==1
   # fPlayAt moves the underlying source origin; cancel the positive start
   # trim so the retained audio starts immediately at segment time zero.
   for name,val,fmt in [('StreamType',2,'<B'),('uInMemoryMediaSize',0,'<I'),('uSourceBits',0,'<B'),('sourceID',MEDIA,'<I'),('fPlayAt',-trim_ms,'<d'),('fBeginTrimOffset',trim_ms,'<d'),('fEndTrimOffset',0,'<d'),('fSrcDuration',source_duration,'<d')]:
    for f in fields(o,name):patch(f,fmt,val)
  bodies.append(struct.pack('<BI',kind,len(body))+body)
 # The new bank has unique HIRC identities and no embedded SFX/cutscene data.
 n=struct.unpack_from('<I',data,4)[0];header=bytearray(data[8:8+n]);struct.pack_into('<I',header,4,fnv(BANK[:-4]));hirc=struct.pack('<I',len(bodies))+b''.join(bodies)
 bankbytes=b'BKHD'+struct.pack('<I',len(header))+header+b'HIRC'+struct.pack('<I',len(hirc))+hirc
 (audio/BANK).write_bytes(bankbytes)
 sourcewem=SOUND/(str(CREDITS_MEDIA)+'.wem');assert sha(sourcewem)==CREDITS_SHA,'Native credits song differs';shutil.copyfile(sourcewem,audio/(str(MEDIA)+'.wem'))
 bank=copy.deepcopy(template);bank.set('Id',str(fnv(BANK[:-4])));bank.find('Path').text=BANK
 for tag in ('IncludedEvents','IncludedMemoryFiles','ReferencedStreamedFiles'):
  for elem in list(bank.findall(tag)):bank.remove(elem)
 included=ET.SubElement(bank,'IncludedEvents')
 for e in events:
  new=copy.deepcopy(e);new.set('Id',str(rename[int(e.get('Id'))]));new.set('Name',e.get('Name').replace('02287f','00f0b0'));new.set('ObjectPath',e.get('ObjectPath','').replace('02287f','00f0b0'));included.append(new)
 tree.find('.//SoundBanks').append(bank)
 proof=dict(title='Beyond the Bounds',version='ending credits',native_event='Play_sd000011',native_source_media=CREDITS_MEDIA,family=FAMILY,bank=BANK,media_id=MEDIA,source=str(sourcewem),source_sha256=sha(sourcewem),media_sha256=sha(audio/(str(MEDIA)+'.wem')),duration_seconds=duration/1000,source_duration_seconds=source_duration/1000,trim_start_seconds=TRIM_SECONDS,gain_multiplier=GAIN,gain_db=20*math.log10(GAIN),container_root_volume_db=-4.0+20*math.log10(GAIN),uniform_track_volume_db=TRACK_VOLUME_DB,measured_dry_stereo_downmix_lufs=-14.49,level_basis='Native template first-segment attenuation retained for both segments; eliminates the 3.1dB loop drop. Credits recording replaces quieter cinematic mix. In-game balance pending.',edit_method='Independent credits stream, aligned native music timeline and consistent segment volume; streamed codec unchanged',channels=8,identity_confirmed_by_user=False,recording='Native sd000011 credits stream; opening movie s000op_E excluded',original_cinematic_and_credits_assets_written=False,new_hirc_identities=len(keep),single_active_stream_per_segment=True,codec_transcoded=False,gameplay_playback_verified=False,bank_sha256=sha(audio/BANK))
 save(audio.parent/'beyond-the-bounds.json',proof)
 return [dict(relative_path='sound/Windows/'+name,package_path='audio/files/'+name,expected_before_sha256=None,patched_sha256=sha(audio/name),allow_new_file=True) for name in (BANK,str(MEDIA)+'.wem')]
if __name__=='__main__':
 import sys
 tree=ET.parse(SOUND/'SoundbanksInfo.xml');prepare(tree,sys.argv[1]);tree.write(Path(sys.argv[1])/'beyond-bounds-metadata.xml')
