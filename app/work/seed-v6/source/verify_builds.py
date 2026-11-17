import portable_paths as _portable
"""Independent output checks. Does not launch or attach to the game."""
import sys,json,struct,hashlib,collections
from pathlib import Path
from archive_tools import *
from mixed_boss_catalog import payloads
def motion(a,stage):
 issues=[];checks=0
 for g in a.groups(stage):
  if g['folder'] not in ('cache','nocache','resident'):continue
  data=a.decode(g);positions={f['name']:i for i,f in enumerate(g['files'])}
  for i,f in enumerate(g['files']):
   if not f['name'].endswith('.mts'):continue
   b=data[f['offset']:f['offset']+f['size']];p=struct.unpack_from('<I',b)[0];lib=b[p:].split(b'\0',1)[0].decode('ascii');key=f'{strcode32(lib):08x}.mtl'
   if key in positions:
    checks+=1
    if positions[key]>=i:issues.append(dict(stage=stage,script=f['name'],library=key))
 return checks,issues
def verify(package):
 p=Path(package);m=json.loads((p/'manifest.json').read_text());a=Archive(p/'STAGE.DAT');assert sha(a.path)==m['patched_sha256']
 count,errors=motion(a,'ba01');assert not errors
 if (p/'enemy-mapping.json').exists():
  rows=json.loads((p/'enemy-mapping.json').read_text());cache={};clods=[]
  for r in rows:
   if r.get('protected'):continue
   if r['stage'] not in cache:cache[r['stage']]=payloads(a,r['stage'])
   data=cache[r['stage']][r['file']];off=struct.unpack_from('<I',data,4)[0]+112*r['record']+48+8*r['slot']
   assert data[off:off+3]==bytes([r['enemy'],r['count'],r['level']]),r
   if r['enemy']==10:
    assert any((s['stage'],s['file'],s['offset'])==(r['stage'],r['file'],r['offset']) for s in m.get('mosquito_replacements',{}).get('selected',[]))
   if r['enemy']==31:clods.append(r['count'])
  # Independently enforce exhaustion against each logged compatible pool.
  used=set()
  for r in json.loads((p/'boss-mapping.json').read_text()):
   allowed=set(r['compatible']);remaining=allowed-used
   if not remaining:used-=allowed;remaining=allowed;assert r['compatible_bag_reset']
   else:assert not r['compatible_bag_reset']
   assert r['identity'] in remaining;used.add(r['identity'])
  for stage in {r['stage'] for r in rows}:
   n,e=motion(a,stage);count+=n;errors.extend(e)
  assert not errors,errors
  weapon=json.loads((p/'subweapon-mapping.json').read_text());assert '5' not in weapon['mapping'] and 5 not in weapon['mapping'].values()
  assert m['settings']['metatron_subweapon_chance_percent']==(20 if m['settings'].get('enabled_subweapons',[1]) else 0)
  assert m['beyond_the_bounds']['in_music_pool']
  music={int(k):v for k,v in m['music_track_shuffle']['track_mapping'].items()};assert 0xf0b0 in music.values()
  for item in weapon['files']:
   if item['stage'] not in cache:cache[item['stage']]=payloads(a,item['stage'])
   b=cache[item['stage']][item['file']];assert struct.unpack_from('<I',b,item['offset'])[0]==item['reward']
 return dict(package=str(p),stage_sha256=m['patched_sha256'],motion_dependencies_checked=count,motion_order_errors=errors,gameplay_verified=False)
def main():
 root=Path(__file__).resolve().parents[1];packages=[root/'Ship-v5.1-order-test']+[Path(x) for x in sys.argv[1:]];reports=[verify(p) for p in packages]
 a=Archive(root/'Ship-v5.1-order-test/STAGE.DAT');v=Archive(V5/'STAGE.DAT')
 assert payloads(a,'ba01')==payloads(v,'ba01')
 assert all(sec(a,s)==sec(v,s) for s in a.stages if s!='ba01')
 builds=[json.loads((p/'build-result.json').read_text()) for p in packages[1:]]
 if len(builds)==3:
  first,second,repeat=builds
  assert first['seed']==repeat['seed'] and first['archive_sha256']==repeat['archive_sha256']
  assert first['category_manifest_hashes']==repeat['category_manifest_hashes']
  assert first['seed']!=second['seed'] and first['archive_sha256']!=second['archive_sha256']
  assert all(first['category_manifest_hashes'][k]!=second['category_manifest_hashes'][k] for k in ('enemies','bosses','music','subweapons'))
 save(root/'regression-verification.json',dict(passed=True,packages=reports,two_seeds_and_repeat_verified=len(builds)==3,full_playthrough_verified=False))
 print('PASS',len(packages),'archives; no gameplay claim')
if __name__=='__main__':main()
