import portable_paths as _portable
"""Resize cached files while preserving their order and every unmodified byte."""
def replace_group_files(group,decoded,replacements):
 old=bytes(decoded);files=group['files'];out=bytearray();updated=[]
 if not files or files[0]['offset']!=0:raise ValueError('Unsupported group layout')
 for f in files:
  start=f['offset'];size=f['size']
  if start%16 or size%16:raise ValueError('Unaligned original cache file')
  original=old[start:start+size];assert len(original)==size
  payload=replacements.get(f['name'],original)
  payload+=bytes((-len(payload))%16)
  nf=dict(f,offset=len(out),size=len(payload));updated.append(nf);out.extend(payload)
  if f['name'] not in replacements:assert payload==original
 assert sum(f['size'] for f in files)==len(old)
 group['files']=updated
 return out
