import portable_paths as _portable
"""Weighted assignments retain distinct selector namespaces within each group."""
import hashlib
from randomizer_settings import ENEMIES,weighted_enemy

def conflicts(row):
 groups={}
 for slot in row['slots']:
  if slot['count'] and slot['original_type'] in (31,32,40,41,42,43):
   groups.setdefault(slot['script_group_id'],set()).add(slot['original_type'])
 return {frozenset((a,b)) for types in groups.values() for a in types for b in types if a!=b}

def mapping(seed,stage,row,pool,weights):
 edges=conflicts(row);sources=sorted({s['original_type'] for s in row['slots'] if s['original_type'] in (31,32,40,41,42,43)})
 # Constrain the most connected sources first, using hashes for stable ties.
 sources.sort(key=lambda t:(-sum(t in edge for edge in edges),hashlib.sha256((str(seed)+'\0pool-order\0'+stage+'\0'+str(t)).encode()).digest()))
 assigned={}
 def visit(index):
  if index==len(sources):return True
  source=sources[index]
  forbidden={assigned[other] for other in assigned if frozenset((source,other)) in edges}
  remaining={t for t in pool if t not in forbidden and any(typ==t and weights[name]>0 for name,typ in ENEMIES.items())}
  attempt=0
  while remaining:
   target=weighted_enemy(seed,stage,'distinct/'+str(source)+'/'+str(attempt),sorted(remaining),weights)
   assigned[source]=target
   if visit(index+1):return True
   del assigned[source];remaining.remove(target);attempt+=1
  return False
 if not visit(0):raise ValueError('Enabled enemy pools cannot keep distinct scripted actors in '+stage+'. Enable more compatible enemy types; no disabled enemy or vanilla fallback was selected.')
 return dict(sorted(assigned.items()))

def validate(row,assigned):
 for edge in conflicts(row):
  a,b=tuple(edge)
  if a in assigned and b in assigned and assigned[a]==assigned[b]:
   raise ValueError('Enemy mapping merges scripted actor identities in '+row['stage']+': '+str(a)+' and '+str(b))
