import portable_paths as _portable
"""Opening Ardjet -> Nephtis prototype. Offline only; assets/gameplay pending."""
import struct,hashlib
from scx_bytecode import instructions
from scx_call_arguments import call_arguments
from boss_spawn_contracts import decode_story_boss,ARDJET_STORY
from scx_manager_chain_adapter import appended_instructions
NEPHTIS_CREATE=0xffff367b
NEPHTIS_CONFIG=0x7bf39906
TRANSITION_EFFECT=0x0ba2a83d

def literal(kind,value):
 if kind not in (0xc0,0xc1,0xc5) or type(value)!=int or not 0<=value<=0xffffffff:raise ValueError('Unsupported literal')
 return bytes([0x80,0xb0,kind])+struct.pack('<I',value)
def native(command,args):
 if len(args)>255:raise ValueError('Argument limit')
 return b''.join(args)+bytes([0x84,len(args),0x88])+struct.pack('<I',command)
def procedure(entry):return bytes([0x87])+struct.pack('<I',entry)

def append_first_boss_handoff(data,call_offset,source_sha256):
 original=bytes(data)
 if hashlib.sha256(original).hexdigest()!=source_sha256:raise ValueError('Source SHA mismatch')
 ins={p:(op,raw) for p,op,raw in instructions(original)}
 if call_offset not in ins or ins[call_offset][0]!=0x88 or struct.unpack_from('<I',original,call_offset+1)[0]!=ARDJET_STORY:raise ValueError('Wrong source creation call')
 source=decode_story_boss(original,call_offset,ARDJET_STORY)
 if source['variant']!=0:raise ValueError('Infected Ardjet is protected')
 args=call_arguments(original,call_offset)
 if len(args)!=9 or any(x['kind'] not in (0xc0,0xc1) or x['value'] is None for x in args[:6]):raise ValueError('Computed source coordinates unsupported')
 callbacks=[x['value'] for x in args[6:]]
 if any(p not in ins for p in callbacks):raise ValueError('Invalid original callback')
 if ins[callbacks[2]][0]!=0x89:raise ValueError('Expected inert original HP-zero callback')
 base=[literal(x['kind'],x['value']) for x in args[:6]];base[1]=literal(0xc0,11)
 entry=len(original)
 config=native(NEPHTIS_CONFIG,[literal(0xc0,11)])
 # Fixed-size C5 literal permits computing appended defeat-entry before emission.
 spawn_args=base+[bytes([0xdf]),literal(0xc5,0),bytes([0xe3]),literal(0xc0,3)]
 spawn=native(NEPHTIS_CREATE,spawn_args)
 defeat_entry=entry+len(config)+len(spawn)+5+1
 spawn_args[7]=literal(0xc5,defeat_entry)
 body=config+native(NEPHTIS_CREATE,spawn_args)+procedure(callbacks[1])+bytes([0x89])
 defeat=procedure(callbacks[0])+native(TRANSITION_EFFECT,[])+bytes([0x89])
 patched=bytearray(original);patched[call_offset:call_offset+5]=procedure(entry);patched.extend(body+defeat)
 decoded=list(appended_instructions(patched,entry,len(patched)))
 assert decoded[-1][1]==0x89 and any(p==defeat_entry for p,op,raw in decoded)
 assert patched[:call_offset]==original[:call_offset] and patched[call_offset+5:len(original)]==original[call_offset+5:]
 return bytes(patched),dict(source_sha256=source_sha256,source_call=call_offset,source_actor_id=source['actor_id'],replacement='Nephtis',replacement_type=11,replacement_phase=3,source_callbacks=callbacks,procedure_entry=entry,defeat_entry=defeat_entry,original_offsets_preserved=True,appended_bytes=len(body+defeat),native_commands=[f'{h:08x}' for h in [NEPHTIS_CONFIG,NEPHTIS_CREATE,TRANSITION_EFFECT]],autonomous_enemy_ai_verified=False,phase3_starting_hp="Native half maximum",assets_verified=False,source_selector_adaptation_verified=False,transition_effect_machine_equivalence_verified=False,gameplay_verified=False,installed=False,ready_for_install=False)
