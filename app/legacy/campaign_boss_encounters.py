import portable_paths as _portable
"""Group verified native spawn sites into campaign encounters before shuffling."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SITES={
'ca02':(2564,), 'ba02':(1432,2155,4370,4877), 'ba03':(2572,),
'wn01':(1479,), 'cy02':(3744,), 'vc01':(3510,), 'ef01':(8926,),
'ef02g':(1364,), 'fr02':(939,12718), 'cs01':(4718,), 'fa01':(3308,),
'am01g':(1544,1623), 'am02':(4785,5232), 'fr04g':(13683,)}
PROTECTED={'ef02g':'Infected Ardjet: user requested vanilla',
'af02':'Zakat: user requested vanilla'}
def build_encounters(catalog):
 entries=catalog['entries']; seen=set(); groups={s:[] for s in SITES}
 for e in entries:
  key=(e['stage'],e['offset'])
  if key in seen:raise ValueError('Duplicate spawn site: '+str(key))
  seen.add(key)
  if e['stage'] not in SITES or e['offset'] not in SITES[e['stage']]:
   raise ValueError('Unreviewed spawn site: '+str(key))
  groups[e['stage']].append(e)
 expected={(s,o) for s,offsets in SITES.items() for o in offsets}
 if seen!=expected:raise ValueError('Missing spawn sites: '+str(sorted(expected-seen)))
 result=[]
 for stage,offsets in SITES.items():
  sites=sorted(groups[stage],key=lambda e:e['offset'])
  names={e['contract'].get('boss','Nephtis') for e in sites}
  if len(names)!=1:raise ValueError('Mixed boss types within '+stage)
  result.append(dict(encounter=stage,boss=names.pop(),source_sites=sites,
   preserve_as_unit=True,randomise=stage not in PROTECTED,
   source_adapter_ready=False,destination_adapter_ready=False,
   protected_reason=PROTECTED.get(stage),
   support_required=['Gauntlet','throwable props','full-health arena adapter']
    if sites[0]['contract'].get('boss','Nephtis')=='Nephtis' else []))
 result.append(dict(encounter='af02',boss='Zakat',source_sites=[],
  preserve_as_unit=True,randomise=False,protected_reason=PROTECTED['af02'],
  source_adapter_ready=False,destination_adapter_ready=False))
 return result
def shuffle(encounters,seed):
 """Stable permutation of whole encounters; does not authorize patching."""
 pool=[e['encounter'] for e in encounters if e['randomise']]
 ordered=sorted(pool,key=lambda s:hashlib.sha256(
  ('zoe2-boss-encounters-v1\0'+seed+'\0'+s).encode()).digest())
 return dict(zip(sorted(pool),ordered))

def shuffle_with_arena_constraints(encounters,seed):
 """Retain the permutation while limiting Inhert to reviewed arena routes.

 fr02 owns its native arena. am02 has a translated bounds plan backed by the
 original native bounds-reader fixture. Other source arenas need separate
 collision/placement work before they can receive this factory.
 """
 mapping=shuffle(encounters,seed)
 source=next((s for s,t in mapping.items() if t=='fr02'),None)
 if source is not None and source not in ('fr02','am02'):
  if 'am02' not in mapping:raise ValueError('Reviewed Inhert arena is absent')
  mapping[source],mapping['am02']=mapping['am02'],mapping[source]
 return mapping
def require_ready(encounters,mapping):
 by={e['encounter']:e for e in encounters}
 pool={k for k,v in by.items() if v['randomise']}
 if set(mapping)!=pool or set(mapping.values())!=pool:
  raise ValueError('Mapping must be a permutation of unprotected encounters')
 for source,target in mapping.items():
  if source==target:continue
  if not by[source]['source_adapter_ready'] or not by[target]['destination_adapter_ready']:
   raise ValueError('Unverified boss adapter: '+source+' -> '+target)
def main():
 catalog=json.loads((ROOT/'campaign-boss-source-catalog.json').read_text())
 encounters=build_encounters(catalog)
 out=dict(format=1,source_creation_sites=len(catalog['entries']),
  logical_encounters=len(encounters),seed='branch-mixed-9',
  encounters=encounters,proposed_mapping=shuffle(encounters,'branch-mixed-9'),
  installed=False,full_game_playable=False)
 (ROOT/'campaign-boss-encounters.json').write_text(json.dumps(out,indent=2))
 print('Grouped',len(catalog['entries']),'sites into',len(encounters),
  'encounters including protected Zakat; offline mapping only')
if __name__=='__main__':main()
