import portable_paths as _portable
"""Fail closed on statically detectable Raptor-respawn pool gaps."""
from scx_bytecode import instructions
from scx_manager_chain_adapter import appended_instructions,MANAGER_TYPES
from scx_pool_paths import audit_entry,COMMON

def audit_campaign_pool_paths(archive,plans):
 records=[]
 for stage in plans:
  name=stage['stage']
  if 'manager_counts_verified' not in stage:continue
  for g in archive.groups(name):
   if g['folder'] not in ('cache','nocache'):continue
   raw=archive.decode(g)
   for f in g['files']:
    key=f['name']
    if not key.endswith('.scx'):continue
    b=raw[f['offset']:f['offset']+f['size']]
    ins=list(instructions(b))
    for mapping in (stage.get('script_adapters',{}),stage.get('dependency_adapters',{})):
     if key in mapping:
      primary=mapping[key]
      for part in [primary]+primary.get('additional_procedures',[]):
       ins.extend(appended_instructions(b,part['procedure_entry'],part['procedure_end']))
    bypos={p:(op,arg) for p,op,arg in ins}
    hashes=[int.from_bytes(arg[1:],'little') for p,op,arg in ins if op==0x88]
    if COMMON not in hashes or not any(MANAGER_TYPES.get(h) in (32,43) for h in hashes):continue
    entries={0}|{int.from_bytes(arg[1:],'little') for p,op,arg in ins if op in (0xc5,0x87)}
    results=[audit_entry(bypos,e) for e in entries if e in bypos]
    records.append(dict(stage=name,file=key,entries=len(results),
     possible_gap_entries=sum(bool(r['possible_gap_paths']) for r in results),
     duplicate_pool_entries=sum(bool(r['duplicate_pool_paths']) for r in results),
     unresolved_entries=sum(bool(r['unresolved']) for r in results)))
 return records
