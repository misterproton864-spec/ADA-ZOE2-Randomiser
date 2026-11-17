import portable_paths as _portable
"""Apply OFF states by restoring pristine payloads, including prior seed overlays."""
import json
from pathlib import Path
from archive_tools import W,L,sha,save

def apply(directory,options):
 directory=Path(directory);out=directory/'Ship-v5';m=json.loads((out/'manifest.json').read_text())
 rows=json.loads((directory/'reports/audio-install-files.json').read_text())
 voice=json.loads((out/'ada-gameplay-mapping.json').read_text())
 if not options['randomise_ada']:
  cache=_portable.HOME/'audio-clean-originals'
  for row in voice['files']:
   rel=row['relative_path'].removeprefix('sound/Windows/')
   source=cache/rel
   if sha(source)!=row['clean_sha256']:raise ValueError('Pristine ADA input differs: '+rel)
   (out/row['package_path']).write_bytes(source.read_bytes());row['patched_sha256']=row['clean_sha256'];row['shuffled']=False
  voice.update(enabled=False,mapping={},stream_changes=[],shuffled_streams=0,legacy_shuffled_streams=0,expanded_shuffled_streams=0)
  bypath={r['relative_path']:r for r in voice['files']}
  rows=[bypath.get(r['relative_path'],r) for r in rows]
  save(out/'ada-gameplay-mapping.json',voice);m['ada_overlay']=voice
 else:
  voice['enabled']=True;save(out/'ada-gameplay-mapping.json',voice);m['ada_overlay']=voice
 if not options['randomise_music']:
  voicepaths={r['relative_path'] for r in voice['files']}
  for row in rows:
   if row['relative_path'] in voicepaths:continue
   rel=row['relative_path'].removeprefix('sound/Windows/')
   digest=row.get('clean_sha256')
   if digest:
    candidates=[_portable.ORIGINALS/'sound/Windows'/rel]
    source=next((p for p in candidates if p.is_file() and sha(p)==digest),None)
    if source is None:raise ValueError('Pristine music input unavailable: '+rel)
    (out/row['package_path']).write_bytes(source.read_bytes());row['patched_sha256']=digest
    for bank in m['original_music_banks']:
     if bank['file']==rel:bank['sha256']=digest
  # Extra donor files are inert without music hooks; keeping them in the plan
  # lets a future enabled seed replace them transactionally.
  m['music_track_shuffle'].update(enabled=False,track_mapping={},tracks=[])
  m['beyond_the_bounds']=dict(enabled=False,included=False,in_music_pool=False)
 else:m['music_track_shuffle']['enabled']=True
 save(out/'manifest.json',m);save(directory/'reports/audio-install-files.json',rows)

def helpers(options):
 # Packing changes absolute sound-bank sectors even with music shuffle OFF.
 result={'SeededMetatronAdapter.exe','MusicSectorAdapter.exe'}
 if options.get('randomise_music',True):result.add('MusicTrackAdapter.exe')
 return result
