import portable_paths as _portable
"""User selections are deterministic inputs, constrained by known stage pools."""
import hashlib
ENEMIES={'Raptor':40,'Mummyhead':32,'Cyclops':41,'Narita':31,'Clod':43,'Leopardo':42,'Spider':None,'Mosquito / swarm':10}
DEFAULT_WEIGHTS={'Raptor':17,'Mummyhead':17,'Cyclops':17,'Narita':17,'Clod':16,'Leopardo':16,'Spider':0,'Mosquito / swarm':0}
LOCKED_ENEMIES={'Spider':'Native objective spiders stay protected; no qualified replacement pool yet.'}
BOSSES={'Ardjet':'Ardjet','Nephtis':'Nephtis','Vic Viper':'Vic Viper','Inhert':'Inhert','Anubis 1':'Anubis','Anubis 2':'Anubis','Compressed-space Anubis':'Anubis','Fake Anubis':'Anubis','Aumaan Anubis':'Anubis','Viola AI (full rescue fight)':'Ardjet'}
DEFAULT_BOSSES=[name for name in BOSSES if name!='Viola AI (full rescue fight)']
WEAPONS={1:'Geyser',2:'Comet',3:'Gauntlet',4:'Decoy',6:'Homing Missile',7:'Wisp',8:'Floating Mine',9:'Zero Shift',10:'Phalanx',11:'Halberd',12:'Mummy'}

def enemy_weights(values=None):
 values=dict(DEFAULT_WEIGHTS if values is None else values)
 if set(values)!=set(ENEMIES):raise ValueError('Enemy percentages must specify all eight enemy types')
 if any(type(v) is not int or not 0<=v<=100 for v in values.values()):raise ValueError('Enemy percentages must be whole numbers from 0 to 100')
 if any(values[name] for name in LOCKED_ENEMIES):raise ValueError('Spider replacements remain unqualified; their share must remain 0%')
 if sum(values.values())!=100:raise ValueError('Replacement enemy shares must total 100%')
 return values

def boss_selection(names=None,include_viola_ai=False):
 names=list(DEFAULT_BOSSES if names is None else names)
 if include_viola_ai and 'Viola AI (full rescue fight)' not in names:names.append('Viola AI (full rescue fight)')
 if set(names)-set(BOSSES):raise ValueError('Unknown boss selection')
 if not names:raise ValueError('Enable at least one replacement boss')
 if 'Viola AI (full rescue fight)' in names and not include_viola_ai:raise ValueError('Viola AI requires its experimental checkbox')
 return sorted(set(names))

def weapon_selection(ids=None):
 if ids is not None and any(type(i) is not int for i in ids):raise ValueError('Subweapon IDs must be integers')
 ids=sorted(WEAPONS if ids is None else set(ids))
 if set(ids)-set(WEAPONS):raise ValueError('Unknown/protected subweapon selection; Vector Cannon cannot be shuffled')
 return ids

def weighted_enemy(seed,stage,key,pool,weights):
 available=[(typ,weights[name]) for name,typ in ENEMIES.items() if typ in pool and weights[name]>0 and name not in LOCKED_ENEMIES]
 if not available:raise ValueError('No enabled compatible replacement enemy for stage '+stage+'. Adjust enemy shares; no vanilla fallback was applied.')
 total=sum(w for _,w in available)
 draw=int.from_bytes(hashlib.sha256((str(seed)+'\0enemy-share-v1\0'+stage+'\0'+str(key)).encode()).digest()[:8],'big')%total
 for typ,weight in available:
  if draw<weight:return typ
  draw-=weight
 raise AssertionError('Weighted selection bounds')

def enemy_level(seed,stage,key,original,enabled=False):
 if not enabled:return original
 if not 0<=original<=7:raise ValueError('Unqualified native enemy level at '+stage)
 return int.from_bytes(hashlib.sha256((str(seed)+'\0enemy-level-v1\0'+stage+'\0'+str(key)).encode()).digest()[:8],'big')%8

