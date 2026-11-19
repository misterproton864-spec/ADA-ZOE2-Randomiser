import portable_paths as _portable
"""Seeded cue-compatible music choices; never remap an unsupported event."""
import hashlib, math
from collections import Counter


def select(families, seed):
    def rank(domain, value):
        return hashlib.sha256((str(seed)+'\0'+domain+'\0'+str(value)).encode()).digest()

    candidates = {}
    for src, row in families.items():
        required = set(map(tuple, row['signature']))
        candidates[src] = [dst for dst, donor in families.items()
                           if dst != src
                           and row['native_structure'] == donor['native_structure']
                           and required <= set(map(tuple, donor['signature']))]
    # Assign scarce choices first, balancing donor use before the seeded tie-break.
    usage = Counter()
    mapping = {}
    # Keep the existing release promise that Beyond the Bounds is heard in
    # at least one compatible gameplay family in every enabled seed.
    donor = 0xf0b0
    eligible = [src for src in families if donor in candidates[src]]
    if eligible:
        src = min(eligible, key=lambda f: rank('featured', f))
        mapping[src] = donor
        usage[donor] += 1
    for src in sorted(families, key=lambda f: (len(candidates[f]), rank('source', f))):
        if src in mapping:
            continue
        if candidates[src]:
            # A hard least-used-first rule made scarce cue groups force later
            # choices into the same sequence. A seeded weighted draw keeps
            # every compatible donor eligible while gently balancing reuse.
            def score(d):
                raw=int.from_bytes(rank(str(src),d)[:8],'big')
                uniform=(raw+1)/(2**64+1)
                return -math.log(uniform)*(1+usage[d])
            dst = min(candidates[src], key=score)
            mapping[src] = dst
            usage[dst] += 1
    return mapping, candidates


def patch_compiler(text):
    start = text.index(' buckets=collections.defaultdict(list)')
    end = text.index(' # Match the stolen instruction', start)
    text = text[:start] + ''' from music_selection import select
 mapping,candidates=select(families,SEED)
 rows=[]
 for src,dst in sorted(mapping.items()):
  assert src!=dst
  assert families[src]['native_structure']==families[dst]['native_structure']
  assert set(families[src]['signature'])<=set(families[dst]['signature'])
  rows.append(dict(source_family=f'{src:06x}',destination_family=f'{dst:06x}',
   source_bank=families[src]['bank'],destination_bank=families[dst]['bank'],category='compatible-gameplay',
   source_stages=families[src]['stages'],destination_stages=families[dst]['stages'],
   play_and_state_signature=families[src]['signature'],
   destination_signature=families[dst]['signature'],compatible_donors=len(candidates[src])))
 for src in sorted(set(families)-set(mapping)):
  ineligible.append(dict(family=f'{src:06x}',reason='no structure-compatible donor supporting every source cue'))
 assert len(mapping)>=10
''' + text[end:]
    text = text.replace("category_basis='Original stage membership; conservative inferred gameplay categories plus exact authored structure/state signatures.'",
                        "selection_policy='seeded-weighted-cue-superset-v2',category_basis='Gameplay banks with identical authored structure; donor supports every source Play/State cue.'")
    return text
