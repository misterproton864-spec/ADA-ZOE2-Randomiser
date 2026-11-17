import portable_paths as _portable
"""Literal-only combat initialization recovered from the original donor SCX."""
import struct
from functools import lru_cache
from scx_bytecode import native_calls
from scx_call_arguments import call_arguments
from scx_first_boss_handoff import native,literal

TABLE_COMMANDS={0xfffedd53:0x9fc4cb4c,0xdfedfdb4:0xf7ded65b,0xbfd9f8ec:0xf7ded65b,
 0x7fed7b0b:0xa970f8fb,0xfa106dc5:0x3d1d8abc,0xef217f76:0x3d1d8abc,
 0xdfe3a990:0x3d1d8abc,0xef9a96d8:0xbfe97610}
REGISTRATIONS={0xfa106dc5:0xff6900ad,0xef217f76:0xfbbc09c8,0xdfe3a990:0x8fd5dd02}

@lru_cache(maxsize=32)
def donor_table(data,factory):
 command=TABLE_COMMANDS.get(factory)
 if command is None:return b'',None
 matches=[]
 for off,h in native_calls(data):
  if h!=command:continue
  args=call_arguments(data,off)
  if len(args)%3:raise ValueError('Donor damage frame must contain complete index/value triples')
  entries=[];encoded=[]
  for i in range(0,len(args),3):
   tag,index,value=args[i:i+3]
   if tag['kind']!=0xd3 or index['kind']!=0xc0 or value['kind']!=0xc0:raise ValueError('Nonliteral donor damage table')
   if not 0<=index['value']<76 or not 0<=value['value']<=32767:raise ValueError('Out-of-range donor table entry')
   entries.append([index['value'],value['value']]);encoded.extend([b'\xd3',literal(0xc0,index['value']),literal(0xc0,value['value'])])
  if len({p[0] for p in entries})!=len(entries):raise ValueError('Duplicate donor attack index')
  matches.append((native(command,encoded),dict(command=f'{command:08x}',donor_call=off,entries=entries)))
 if not matches or any(b!=matches[0][0] for b,r in matches):raise ValueError('Missing or ambiguous donor combat table')
 return matches[0]
