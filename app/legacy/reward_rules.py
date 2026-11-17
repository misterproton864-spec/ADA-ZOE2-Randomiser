import portable_paths as _portable
"""Deterministic reward rules; no game-memory or installation hooks.
Vector Cannon is always excluded. Runtime pickup keys must be stable and persisted
by the eventual pickup adapter; these pure rules do not implement that adapter.
"""
import hashlib
VECTOR_CANNON=5
REQUESTED_WEAPONS=(1,2,3,4,6,7,8,9,10,11,12)
SCRIPT_VERIFIED_WEAPONS=REQUESTED_WEAPONS
def number(seed,domain,key,limit):
 if limit<1:raise ValueError('limit must be positive')
 ceiling=(1<<64)-((1<<64)%limit);counter=0
 while True:
  raw=hashlib.sha256((str(seed)+'\0'+domain+'\0'+str(key)+'\0'+str(counter)).encode()).digest()
  x=int.from_bytes(raw[:8],'big')
  if x<ceiling:return x%limit
  counter+=1
def weapon_permutation(seed,pool=REQUESTED_WEAPONS):
 pool=tuple(sorted(set(pool)))
 if VECTOR_CANNON in pool:raise ValueError('Vector Cannon must remain vanilla')
 if not set(pool)<=set(REQUESTED_WEAPONS):raise ValueError('Unknown story weapon')
 shuffled=list(pool)
 for i in range(len(shuffled)-1,0,-1):
  j=number(seed,'weapons-v1',i,i+1);shuffled[i],shuffled[j]=shuffled[j],shuffled[i]
 return dict(zip(pool,shuffled))
def metatron_reward(seed,pickup_key,owned,chance_percent=20,pool=REQUESTED_WEAPONS):
 if not 0<=chance_percent<=100:raise ValueError('Chance must be 0 through 100')
 if VECTOR_CANNON in pool:raise ValueError('Vector Cannon must remain vanilla')
 if not set(pool)<=set(REQUESTED_WEAPONS):raise ValueError('Unknown story weapon')
 remaining=sorted(set(pool)-set(owned))
 if not remaining or number(seed,'metatron-roll-v1',pickup_key,100)>=chance_percent:return None
 return remaining[number(seed,'metatron-weapon-v1',pickup_key,len(remaining))]
