"""Add compatible singleton cues to seeded cycles without losing shuffled cues."""
import hashlib

FIELDS=('StreamType','bPrefetch','ulPluginID','uBitsPositioning','uInMemoryMediaSize','uSourceBits')

def expand(mapping, candidates, media, audibility, seed):
    result=dict(mapping)
    if set(result)!=set(result.values()) or any(k==v for k,v in result.items()):
        raise ValueError('Existing voice mapping must be a fixed-point-free permutation')
    added=set();changed=set();pending=set(candidates)-set(result)
    def rank(domain,value):
        return hashlib.sha256((str(seed)+'\0ada-cycle-v1\0'+domain+'\0'+value).encode()).digest()
    def compatible(a,b):
        left,right=media[a],media[b]
        if left['format']!=right['format'] or len(left['nodes'])!=1 or len(right['nodes'])!=1:return False
        an,bn=left['nodes'][0],right['nodes'][0]
        if an['StreamType']!=2 or an['bPrefetch']!=0:return False
        if tuple(an[k] for k in FIELDS)!=tuple(bn[k] for k in FIELDS):return False
        if not audibility[a]['audible'] or not audibility[b]['audible']:return False
        low,high=sorted((audibility[a]['seconds'],audibility[b]['seconds']))
        return low>0 and high<=2*low and high-low<=5
    while pending:
        progress=False
        for rel in sorted(pending,key=lambda r:(rank('cue',r),r)):
            edges=[dest for dest,donor in result.items() if compatible(dest,rel) and compatible(rel,donor)]
            if not edges:continue
            dest=min(edges,key=lambda r:(rank(rel,r),r))
            result[rel]=result[dest];result[dest]=rel
            added.add(rel);changed.update((dest,rel));pending.remove(rel);progress=True
        if not progress:break
    assert set(mapping)<=set(result) and set(result)==set(result.values())
    assert all(k!=v for k,v in result.items())
    return result,added,changed
