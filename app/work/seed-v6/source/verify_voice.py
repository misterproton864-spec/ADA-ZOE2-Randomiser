import portable_paths as _portable
"""Read-back guard against rewriting the shared voice bank again."""
import json,hashlib,struct
from pathlib import Path
from ada_gameplay import stream_format

def sha(b):return hashlib.sha256(b).hexdigest()

def verify(package):
 p=Path(package);root=Path(__file__).resolve().parents[1];cache=_portable.HOME/'audio-clean-originals'
 r=json.loads((p/'ada-gameplay-mapping.json').read_text());table=json.loads((root/'voice-stream-compatibility.json').read_text())
 audible=json.loads((root/'voice-audibility.json').read_text())['files']
 assert r['format']==2 and r['prior_bank_event_rewrite_removed']
 native=(cache/table['native_bank']).read_bytes();bank=(p/'audio/files'/table['native_bank']).read_bytes()
 assert bank==native and sha(bank)==table['native_bank_sha256']
 assert not r['routes'] and r['voice_events']==0
 matched=0
 fields=('StreamType','bPrefetch','ulPluginID','DirectParentID','uBitsPositioning','uInMemoryMediaSize','uSourceBits')
 destinations=set()
 for c in r['stream_changes']:
  assert c['destination']!=c['source'] and c['destination'] not in destinations;destinations.add(c['destination'])
  data=(p/'audio/files'/c['destination']).read_bytes();source=(cache/c['source']).read_bytes();before=(cache/c['destination']).read_bytes()
  assert data==source and sha(data)==c['source_clean_sha256'] and sha(before)==c['destination_clean_sha256']
  assert audible[c['source']]['audible'] and audible[c['destination']]['audible']
  assert sha(source)==audible[c['source']]['sha256'] and sha(before)==audible[c['destination']]['sha256']
  assert stream_format(data)==stream_format(before)==c['format']
  dest_nodes=table['nodes'][Path(c['destination']).stem];src_nodes=table['nodes'][Path(c['source']).stem]
  assert len(dest_nodes)==len(src_nodes)==1
  assert dest_nodes[0]['StreamType']==src_nodes[0]['StreamType']==2 and dest_nodes[0]['bPrefetch']==0
  required=fields
  if c.get('compatibility_tier')=='expanded':
   required=tuple(k for k in fields if k!='DirectParentID')
   low,high=sorted((audible[c['source']]['seconds'],audible[c['destination']]['seconds']))
   assert high<=2*low and high-low<=5
   assert c['source_cue'].startswith(('vca','vcc06202')) and c['destination_cue'].startswith(('vca','vcc06202'))
  assert tuple(dest_nodes[0][k] for k in required)==tuple(src_nodes[0][k] for k in required)
  matched+=1
 enabled=r.get('enabled',True)
 assert matched==len(r['mapping'])==r['shuffled_streams']
 assert set(r['mapping'])==set(r['mapping'].values()),'Voice replacements must remain a permutation'
 assert sum(c.get('compatibility_tier')=='expanded' for c in r['stream_changes'])==r.get('expanded_shuffled_streams',0)
 assert matched>=100 if enabled else matched==0
 # Every excluded/retained destination is explicitly reset to its original,
 # so changing seeds cannot leave a previous overlay installed accidentally.
 for row in r['files']:
  if not row.get('native_voice_bank_restored') and not row['shuffled']:
   rel=row['relative_path'].removeprefix('sound/Windows/')
   assert (p/row['package_path']).read_bytes()==(cache/rel).read_bytes()
 return dict(native_voice_bank_byte_identical=True,voice_event_routes_checked=0,voice_stream_files_checked=matched,voice_in_game_audibility_verified=False)
