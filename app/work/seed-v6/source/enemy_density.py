"""Experimental 50% extra ordinary enemies with bounded native manager storage."""
import hashlib,struct,copy
from collections import Counter
from scx_bytecode import native_calls
from scx_call_arguments import call_arguments
from scx_manager_chain_adapter import MANAGER_TYPES
from ene_pool_storage import extend_pool_storage
TYPES=frozenset((31,32,40,41,42,43))
STAGES=frozenset(('ds00','ds02','wn00','cy01','ex01','ef03','fr01','ds00g','ds01g'))
MAX_TOTAL=64
def sha(b):return hashlib.sha256(b).hexdigest()
def apply_stage(stage,files,seed):
 original=dict(files);out=dict(files);edits=[];storage=[];skipped=[]
 if stage not in STAGES:return out,dict(stage=stage,changed=False,reason='Story, boss, tutorial, ship or rescue/objective boundary protected')
 managers={};ene=[]
 for name,data in files.items():
  if name.endswith('.scx'):
   for at,cmd in native_calls(data):
    if cmd not in MANAGER_TYPES:continue
    try:args=call_arguments(data,at)
    except ValueError:return out,dict(stage=stage,changed=False,reason='Computed manager capacity')
    cap=next((a for i,a in enumerate(args) if i and args[i-1]['kind']==0xdd and a['kind']==0xc0),None)
    if cap is None or cap['offset'] is None or not 1<=cap['value']<=64:return out,dict(stage=stage,changed=False,reason='Unqualified manager capacity')
    managers.setdefault(MANAGER_TYPES[cmd],[]).append((name,cap))
  elif name.endswith('.ene'):
   if len(data)<32:return out,dict(stage=stage,changed=False,reason='Truncated ENE')
   count=struct.unpack_from('<H',data,2)[0];base=struct.unpack_from('<I',data,4)[0]
   if base!=32 or len(data)!=base+count*112 or struct.unpack_from('<H',data,0x12)[0]:return out,dict(stage=stage,changed=False,reason='Auxiliary or pre-extended ENE layout')
   ene.append((name,count,base))
 if not managers or not ene:return out,dict(stage=stage,changed=False,reason='No audited ordinary enemy pool')
 # Native Mosquito and Spider slots, their budgets, flags and group IDs never
 # change. Each added ordinary enemy remains part of the native group counter.
 slots=[];totals=Counter()
 for name,count,base in ene:
  data=files[name]
  for rec in range(count):
   flags=struct.unpack_from('<H',data,base+rec*112+0x50)[0]
   for slot in range(4):
    pos=base+rec*112+48+slot*8;typ,n=data[pos:pos+2]
    if typ not in TYPES or not n:continue
    totals[typ]+=n
    if flags in (0,1) and typ in managers and n<=16:slots.append((name,pos,typ,n))
 if sum(totals.values())>MAX_TOTAL:return out,dict(stage=stage,changed=False,reason='Native stage already exceeds experimental actor budget')
 wanted=(sum(s[3] for s in slots)+1)//2
 if sum(totals.values())+wanted>MAX_TOTAL:return out,dict(stage=stage,changed=False,reason='1.5x stage exceeds experimental actor budget')
 extras={};remaining=wanted
 # Proportional allocation across the stage; seeded rounding for odd counts.
 for name,pos,typ,n in slots:extras[name,pos]=n//2;remaining-=n//2
 odd=sorted((s for s in slots if s[3]%2),key=lambda s:hashlib.sha256((str(seed)+'\0density-rounding\0'+stage+'/'+s[0]+'/'+str(s[1])).encode()).digest())
 for name,pos,typ,n in odd[:remaining]:extras[name,pos]+=1
 for name,pos,typ,n in slots:
  extra=extras[name,pos]
  if not extra:continue
  b=bytearray(out[name]);b[pos+1]=n+extra;out[name]=bytes(b);totals[typ]+=extra
  edits.append(dict(file=name,offset=pos+1,before=bytes((n,)).hex(),after=bytes((n+extra,)).hex(),kind='count'))
 if not edits:return out,dict(stage=stage,changed=False,reason='No eligible density groups')
 for typ,sites in managers.items():
  capacity=max(max(a['value'] for _,a in sites),totals[typ])
  if capacity>64:raise ValueError('Density manager capacity exceeds tested bound')
  for name,a in sites:
   if capacity==a['value']:continue
   b=bytearray(out[name]);before=b[a['offset']:a['offset']+4];struct.pack_into('<I',b,a['offset'],capacity);out[name]=bytes(b)
   edits.append(dict(file=name,offset=a['offset'],before=before.hex(),after=struct.pack('<I',capacity).hex(),kind='manager-capacity'))
 needed=max(max(a['value'] for sites in managers.values() for _,a in sites),max(totals.values(),default=1))
 for name,count,base in ene:
  before=out[name];out[name],report=extend_pool_storage(before,needed)
  storage.append(dict(file=name,before_size=len(before),after_size=len(out[name]),**report))
 report=dict(stage=stage,changed=True,multiplier=1.5,extra_enemies=wanted,eligible_original_enemies=sum(s[3] for s in slots),total_regular_enemies=sum(totals.values()),max_total=MAX_TOTAL,edits=edits,storage=storage,
             source_hashes={n:sha(original[n]) for n in {r['file'] for r in edits}|{r['file'] for r in storage}},
             output_hashes={n:sha(out[n]) for n in {r['file'] for r in edits}|{r['file'] for r in storage}},gameplay_verified=False)
 return out,report
def apply(stock,updates,settings,seed):
 if settings.get('enemy_density_multiplier',1)==1:return dict(enabled=False,multiplier=1,stages=[],extra_enemies=0,gameplay_verified=False)
 from mixed_boss_catalog import payloads
 reports=[]
 for stage in sorted(STAGES):
  if stage not in stock.stages:continue
  files=payloads(stock,stage);files.update(updates.get(stage,{}));new,report=apply_stage(stage,files,seed);reports.append(report)
  if report['changed']:updates[stage]=new
 total=sum(r.get('extra_enemies',0) for r in reports)
 if not total:raise ValueError('No qualified 1.5x enemy groups exist for these settings')
 return dict(enabled=True,multiplier=1.5,stages=reports,extra_enemies=total,experimental=True,gameplay_verified=False)
def strip_file(report,name,data):
 if not report.get('changed'):return data
 if name not in report['output_hashes']:return data
 if sha(data)!=report['output_hashes'][name]:raise ValueError('Density resource changed')
 b=bytearray(data)
 for row in report['storage']:
  if row['file']==name:b=b[:row['before_size']]
 for edit in report['edits']:
  if edit['file']!=name:continue
  at=edit['offset'];after=bytes.fromhex(edit['after']);before=bytes.fromhex(edit['before'])
  if b[at:at+len(after)]!=after:raise ValueError('Density edit differs')
  b[at:at+len(before)]=before
 if sha(b)!=report['source_hashes'][name]:raise ValueError('Density inverse differs')
 return bytes(b)
def verify(stock,actual,manifest):
 from mixed_boss_catalog import payloads
 settings=manifest['settings'];saved=manifest.get('enemy_density')
 if settings.get('enemy_density_multiplier',1)==1:
  if saved!=dict(enabled=False,multiplier=1,stages=[],extra_enemies=0,gameplay_verified=False):raise ValueError('Disabled density report differs')
  return lambda stage,name,data:data
 reports={r['stage']:r for r in saved['stages']}
 if set(reports)!=STAGES&set(stock.stages):raise ValueError('Density stage set differs')
 for stage,report in reports.items():
  files=payloads(actual,stage);base={n:strip_file(report,n,b) for n,b in files.items()}
  expected,proof=apply_stage(stage,base,manifest['seed'])
  if expected!=files or proof!=report:raise ValueError('Density reconstruction differs: '+stage)
 if saved['extra_enemies']!=sum(r.get('extra_enemies',0) for r in reports.values()):raise ValueError('Density totals differ')
 return lambda stage,name,data:strip_file(reports.get(stage,{}),name,data)
