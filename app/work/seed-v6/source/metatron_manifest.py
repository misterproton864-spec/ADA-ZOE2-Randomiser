import portable_paths as _portable
import hashlib
POOL=[1,2,3,4,6,7,8,9,10,11,12]
def manifest(seed,chance=20,pool=None):
 pool=POOL if pool is None else list(pool)
 key=int.from_bytes(hashlib.sha256(('zoe2-metatron-native-v1\0'+seed).encode()).digest()[:4],'little');rows=[]
 for counter in range(256):
  x=counter^key;x^=x>>16;x=x*0x85ebca6b&0xffffffff;x^=x>>13;x=x*0xc2b2ae35&0xffffffff;x^=x>>16
  first=(x>>8)%len(pool) if pool else 0;rows.append(dict(native_pickup_counter_before=counter,roll_percent=x%100,subweapon_roll=bool(pool) and x%100<chance,weapon_priority=pool[first:]+pool[:first]))
 return dict(seed=seed,native_seed_key=key,chance_percent=chance,vector_cannon_excluded=True,interpretation='Hook uses saved native pickup counter before increment. On a successful roll it grants the first unowned weapon in this priority order. These are deterministic plans, not observed pickup results; owned weapons and loaded save counters affect actual grants.',counter_manifest=rows)
