import portable_paths as _portable
"""Independent donor readback and protection of native cinematic/credits media."""
import json,math,struct,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
from archive_tools import sha

CREDITS_SHA='a4d8dfeb6da05da786b8d971c6aa01a69ac6cfa393f127308c84ccc079c50df2'
OPENING_SHA='a638706aedd69b00ca36d33a8f9bd0fe4c55c0a441ea79947a0d509314e28fd9'

def verify(package,manifest):
 if not manifest['settings']['randomise_music']:return dict(passed=True,enabled=False)
 p=Path(package);m=manifest['beyond_the_bounds']
 if m.get('version')!='ending credits' or m.get('native_source_media')!=490090204 or m.get('trim_start_seconds')!=0:raise ValueError('Opening/trimmed recording remains in the Beyond the Bounds donor')
 if sha(p/'audio/files/1965101901.wem')!=CREDITS_SHA:raise ValueError('Credits donor media differs from native credits source')
 root=Path(__file__).resolve().parents[1];out=p/'verification';out.mkdir(exist_ok=True)
 from credits_bank_contract import readback
 xml=readback(p/'audio/files/us0000f0b0.bnk',root)
 def volume(o):
  params=o.find(".//object[@name='NodeInitialParams']");values=[]
  for prop in params.iter('object'):
   pid=prop.find("./field[@name='pID']");value=prop.find("./field[@name='pValue']")
   if pid is not None and value is not None and int(pid.get('value'))==0:values.append(float(value.get('value')))
  if len(values)!=1:raise ValueError('Credits donor volume property ambiguous')
  return values[0]
 roots=[o for o in xml.iter('object') if o.get('name')=='CAkMusicRanSeqCntr']
 expected=-4.0+20*math.log10(4.5)
 if len(roots)!=1 or abs(volume(roots[0])-expected)>0.0001:raise ValueError('Beyond the Bounds track-specific gain missing')
 if m.get('gain_multiplier')!=4.5 or abs(m.get('gain_db',0)-20*math.log10(4.5))>0.0001 or abs(m.get('container_root_volume_db',0)-expected)>0.0001:raise ValueError('Beyond the Bounds gain report differs from playback bank')
 objects=[o for o in xml.iter('object') if o.get('name')=='CAkMusicTrack']
 if len(objects)!=2:raise ValueError('Credits donor must have two native segment tracks')
 for o in objects:
  if abs(volume(o)-(-15.3))>0.0001:raise ValueError('Credits donor segment attenuation differs')
  vals={f.get('name'):f.get('value') for f in o.iter('field')}
  if int(vals['sourceID'])!=1965101901 or int(vals['numSources'])!=1 or int(vals['numPlaylistItem'])!=1:raise ValueError('Credits stream/layer routing differs')
  if float(vals['fSrcDuration'])!=337188 or float(vals['fPlayAt'])!=0 or float(vals['fBeginTrimOffset'])!=0 or float(vals['fEndTrimOffset'])!=0:raise ValueError('Credits music timeline differs from encoded media')
 segments=[o for o in xml.iter('object') if o.get('name')=='CAkMusicSegment']
 for o in segments:
  if any(float(f.get('value'))!=337188 for f in o.iter('field') if f.get('name')=='fDuration'):raise ValueError('Credits segment duration differs')
 plan=json.loads((p/'installation-plan.json').read_text())
 protected={'sound/windows/490090204.wem','sound/windows/english(us)/749576447.wem','sound/windows/global_sfx.bnk'}
 if any(r['relative_path'].replace('\\','/').lower() in protected for r in plan['files']):raise ValueError('An original credits/cinematic asset is in the write plan')
 game=Path(str(_portable.game() / 'sound/Windows'))
 if sha(game/'490090204.wem')!=CREDITS_SHA or sha(game/'English(US)/749576447.wem')!=OPENING_SHA:raise ValueError('Original opening or credits stream changed')
 return dict(passed=True,version='ending credits',native_media_sha256=CREDITS_SHA,tracks_checked=2,original_streams_preserved=True,gameplay_verified=False)
