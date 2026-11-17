import portable_paths as _portable
"""Preserve the clone arena's authored height expression for throwable props."""
import struct
from scx_call_arguments import call_arguments
from scx_first_boss_handoff import literal,native,procedure
from nephtis_encounter_support import address,fp,POLE_MODEL,POLE_ASSETS

def height_expression(data,source):
 args=call_arguments(data,source);x,y,z=args[2:5]
 if x['kind']!=0xc1 or z['kind']!=0xc1 or y['value'] is not None:
  raise ValueError('Expected native clone-wave dynamic height')
 return data[x['offset']+4:z['offset']-3]

def pole_wrapper(entry,continuation,positions,identifiers,expression):
 address(entry);address(continuation)
 if len(positions)!=8 or len(identifiers)!=8 or len(set(identifiers))!=8:raise ValueError('Eight distinct support poles required')
 config=native(0x911f0cb1,[literal(0xc0,v) for v in (0x91da1b63,80,6000,800)])
 def emit(string):
  calls=[]
  for (x,y,z),ident in zip(positions,identifiers):
   if y is not None:raise ValueError('Dynamic height must not be replaced by a literal')
   args=[literal(0xc0,address(ident)),b'\x80\xb0\xc2'+struct.pack('<I',address(string)),fp(x),expression,fp(z)]+[literal(0xc0,0)]*3
   calls.append(native(0xffffea2c,args))
  return config+b''.join(calls)+procedure(continuation)+b'\x89'
 string=entry+len(emit(0));body=emit(string)+POLE_MODEL.encode()+b'\0'
 return body,dict(entry=entry,code_end=string,string_offset=string,continuation=continuation,
                  actor_ids=list(identifiers),positions=list(positions),assets=list(POLE_ASSETS),height_expression=expression.hex())
