import portable_paths as _portable
"""Independent reconstruction of the pinned BAHRAM branch adapters."""
import hashlib,struct
from mixed_boss_catalog import payloads
from scx_bytecode import native_calls
from actor_reference_adapter import selector_arguments,ENE_TO_EXTERNAL
from opening_enemies import asset_set
from randomizer_settings import weighted_enemy,enemy_level
from archive_tools import L
import json

def expected(stock,seed,settings,report):
 files=payloads(stock,'ba01');original=files.copy();script=original['ef1d2ddf.scx']
 if hashlib.sha256(script).hexdigest()!='f50f94ac07dd1f8a76b488592bfa2ecde06b1e26fe2a79e20ea857f280bdeab0':raise ValueError('Ship source script changed')
 row=next(r for r in json.loads((L/'Full-Rerandomisation-v2/enemy-shuffle-plan.json').read_text())['stages'] if r['stage']=='ba01')
 groups={s['script_group_id'] for s in row['slots'] if s['original_type']==40}
 weights=settings['enemy_percentages'];mapping={g:weighted_enemy(seed,'ba01','ship-group/'+str(g),[40,41,42],weights) for g in sorted(groups)}
 if {int(k):v for k,v in report['group_mapping'].items()}!=mapping:raise ValueError('Ship mapping differs from weighted selection')
 required=set(mapping.values())-{40};resources={};commands={};donors={}
 for typ in sorted(required):
  assets,donor,command=asset_set(stock,typ);resources.update(assets);commands[typ]=command;donors[typ]=donor
 if {int(k):v for k,v in report['donors'].items()}!=donors:raise ValueError('Ship donor differs')
 imported={n:b for n,b in resources.items() if n not in original}
 if report['files']!={n:hashlib.sha256(b).hexdigest() for n,b in imported.items()}:raise ValueError('Ship import manifest differs')
 for slot in row['slots']:
  typ=slot['original_type']
  if typ not in (32,40):continue
  name=slot['file'];p=slot['offset'];b=bytearray(files[name]);b[p]=mapping[slot['script_group_id']] if typ==40 else 32
  b[p+2]=enemy_level(seed,'ba01',name+'/'+str(p),slot['level'],settings['randomise_enemy_levels']);files[name]=bytes(b)
 selectors={int(k,16) for k in json.loads((L/'type-selector-command-catalog.json').read_text())['commands']}
 result=bytearray(script);selector_edits=[]
 for p,h in native_calls(script):
  if h not in selectors:continue
  for item in selector_arguments(script,p,h):
   if item['type'] not in (1,40):continue
   g=item['encounter_id'];new=ENE_TO_EXTERNAL[mapping[g]] if item['type']==1 else mapping[g];q=item['value_offset']
   struct.pack_into('<I',result,q,new)
   selector_edits.append(dict(offset=q,group=g,source=item['type'],target=new,ordinal=item['ordinal']))
 adapters=[]
 for p in (3814,4733,6299):
  if script[p-10:p+5]!=bytes.fromhex('dd80b0c003000000840288d7cf9a86'):raise ValueError('Ship branch source differs')
  if required:
   entry=len(result);result[p:p+5]=b'\x87'+struct.pack('<I',entry)
   result+=bytes.fromhex('88d7cf9a86')
   for typ in sorted(required):result+=bytes.fromhex('dd80b0c003000000840288')+struct.pack('<I',commands[typ])
   result+=b'\x89';adapters.append(dict(source_call=p,entry=entry,end=len(result),capacity=3,types=[40]+sorted(required)))
 if report['adapters']!=adapters or report['selector_edits']!=selector_edits:raise ValueError('Ship branch/selector contract differs')
 files['ef1d2ddf.scx']=bytes(result)+bytes((-len(result))%16) if required else bytes(result)
 if required:
  for name,b in list(files.items()):
   if not name.endswith('.ene'):continue
   count=struct.unpack_from('<H',b,2)[0];start=struct.unpack_from('<I',b,4)[0]
   if start!=32 or len(b)!=32+count*112 or struct.unpack_from('<H',b,18)[0]:raise ValueError('Ship ENE backing contract differs')
   # Native inactive pool initialization reads at least three physical rows.
   # The declared row count and every scripted/native swarm record stay intact.
   if count<3:files[name]=b+(b[32:144] if count else bytes(112))*(3-count)
 files.update(imported)
 if not report.get('native_secondary_actor_stream_preserved') or not report.get('native_mummyhead_identity_preserved'):raise ValueError('Ship native objective declarations missing')
 return files,imported
