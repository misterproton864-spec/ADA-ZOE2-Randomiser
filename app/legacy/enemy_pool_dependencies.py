import portable_paths as _portable
"""Native actor-pool dependencies; checks only, no gameplay or archive mutation.
Mummyhead/Clod death paths can request a Raptor using birth flag0400.
Ordinary ENE type permutations do not change this hardcoded native pool.
"""
TYPES={31:'Narita',32:'Mummyhead',40:'Raptor',41:'Cyclops',42:'Leopard',43:'Clod'}
RESPAWN_SOURCES={'Mummyhead','Clod'}
def enemy_name(value):
 if isinstance(value,int) or (isinstance(value,str) and value.isdecimal()):
  try:return TYPES[int(value)]
  except KeyError:raise ValueError('Unknown ENE type: '+str(value))
 if value not in TYPES.values():raise ValueError('Unknown enemy: '+str(value))
 return value
def stage_pool_dependencies(plan):
 mapping={enemy_name(k):enemy_name(v) for k,v in plan['mapping'].items()}
 source_managers=plan.get('manager_types',list(mapping))
 pools={mapping[enemy_name(source)] for source in source_managers}
 pools.update(enemy_name(value) for value in plan.get('dependency_manager_types',[]))
 sources=sorted(pools & RESPAWN_SOURCES)
 missing=['Raptor'] if sources and 'Raptor' not in pools else []
 return dict(stage=plan['stage'],mapped_manager_pools=sorted(pools),native_respawn_sources=sources,required_native_pools=['Raptor'] if sources else [],missing_native_pools=missing,pool_presence_verified=not missing,respawn_capacity_verified=False,gameplay_validated=False)
def campaign_pool_dependencies(plans):
 rows=[stage_pool_dependencies(plan) for plan in plans]
 return dict(stages=rows,missing_pool_stages=[r['stage'] for r in rows if r['missing_native_pools']],all_required_pools_present=all(not r['missing_native_pools'] for r in rows),native_respawn_behavior_randomised=False,installation_ready=False)
