import portable_paths as _portable
"""Conservative common-manager epoch analysis; no native execution."""
from scx_manager_chain_adapter import MANAGER_TYPES
COMMON=0xffffedb9
def audit_entry(bypos,entry,limit=200000):
 todo=[(entry,(),0,())];seen=set();gaps=[];duplicates=[];limits=[];common_sites=set();pool_entry_masks={}
 while todo:
  pc,stack,mask,events=todo.pop();state=(pc,stack,mask)
  if state in seen:continue
  if len(seen)>=limit or len(stack)>32:
   limits.append(dict(pc=pc,reason='Traversal limit'));break
  seen.add(state)
  if pc not in bypos:
   limits.append(dict(pc=pc,reason='Unknown instruction target'));continue
  op,raw=bypos[pc];nxt=pc+len(raw)
  if op in (0x85,0x86):
   todo.append((pc+int.from_bytes(raw[1:],'little',signed=True),stack,mask,events))
   if op==0x86:todo.append((nxt,stack,mask,events))
  elif op==0x87:todo.append((int.from_bytes(raw[1:],'little'),stack+(nxt,),mask,events))
  elif op==0x89:
   if stack:todo.append((stack[-1],stack[:-1],mask,events))
   elif mask&1 and mask&2 and not mask&4:gaps.append(dict(return_pc=pc,events=list(events)))
  elif op==0x8e:
   if mask:limits.append(dict(pc=pc,reason='Reached data boundary'))
  else:
   if op==0x88:
    h=int.from_bytes(raw[1:],'little');t=MANAGER_TYPES.get(h)
    if t is not None:pool_entry_masks.setdefault(pc,set()).add(mask)
    if h==COMMON:mask=1;events=(dict(pc=pc,event='common_reset'),);common_sites.add(pc)
    elif mask&1 and t in (32,43):mask|=2;events=events+(dict(pc=pc,event='respawn_source_pool',type=t),)
    elif mask&1 and t==40:
     if mask&4:duplicates.append(dict(pc=pc,events=list(events)))
     mask|=4;events=events+(dict(pc=pc,event='raptor_pool'),)
   todo.append((nxt,stack,mask,events[-12:]))
 return dict(entry=entry,states=len(seen),pool_entry_masks={str(k):sorted(v) for k,v in pool_entry_masks.items()},common_sites=sorted(common_sites),possible_gap_paths=gaps,duplicate_pool_paths=duplicates,unresolved=limits)
