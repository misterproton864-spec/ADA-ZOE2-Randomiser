"""Store changed PAC tables, sharing the verified original texture payload.

The installer streams header + original body to the game only after its existing
backup/preflight transaction. No reconstructed multi-GB seed copy is retained.
"""
import hashlib,json,shutil,struct
from pathlib import Path

CS=r'''using System;using System.IO;using System.Security.Cryptography;
public static class CompactSeedPayload {
 public static byte[] ReadHeader(string path){using(var f=File.OpenRead(path)){var r=new BinaryReader(f);byte[] first=r.ReadBytes(48);if(System.Text.Encoding.ASCII.GetString(first,0,4)!="PAC\0")throw new Exception("Invalid PAC backup");bool big=System.Text.Encoding.ASCII.GetString(first,4,5)=="0.01a";byte[] b=new byte[big?4:8];Array.Copy(first,big?24:32,b,0,b.Length);if(big)Array.Reverse(b);long offset=big?BitConverter.ToUInt32(b,0):(long)BitConverter.ToUInt64(b,0);if(offset<32||offset>16777216||offset>f.Length)throw new Exception("Invalid PAC header size");f.Position=0;byte[] result=r.ReadBytes((int)offset);if(result.Length!=offset)throw new Exception("Truncated PAC header");return result;}}
 static void Pump(Stream input,Stream output,HashAlgorithm hash){byte[] b=new byte[1048576];int n;while((n=input.Read(b,0,b.Length))>0){if(output!=null)output.Write(b,0,n);hash.TransformBlock(b,0,n,b,0);}}
 static string Run(string header,string original,long offset,string destination){
  using(var h=SHA256.Create())using(var head=File.OpenRead(header))using(var input=File.OpenRead(original)){
   if(offset<0||offset>input.Length)throw new Exception("Invalid original payload offset");
   input.Position=offset;
   using(var output=destination==null?null:new FileStream(destination,FileMode.Create,FileAccess.Write,FileShare.None)){
    Pump(head,output,h);Pump(input,output,h);h.TransformFinalBlock(new byte[0],0,0);if(output!=null)output.Flush(true);
    return BitConverter.ToString(h.Hash).Replace("-","").ToLowerInvariant();
   }
  }
 }
 public static string Hash(string header,string original,long offset){return Run(header,original,offset,null);}
 public static string Write(string header,string original,long offset,string destination){return Run(header,original,offset,destination);}
}'''

PS=r'''
$compactPath=Join-Path $package 'compact-payloads.json'
$compact=@{}
if(Test-Path -LiteralPath $compactPath){
 $compactInfo=Get-Content -LiteralPath $compactPath -Raw | ConvertFrom-Json
 if($compactInfo.format -ne 1){throw 'Unknown compact seed format'}
 $originalInputs=Get-Content -LiteralPath (Join-Path $package 'original-inputs.json') -Raw | ConvertFrom-Json
 Add-Type -Path (Join-Path $package 'runtime/CompactSeedPayload.cs')
 foreach($item in $compactInfo.files){
  if($item.file -notin @('atlas_pc_Zlib.pac','atlas_pc_jp_Zlib_ps2.pac')){throw 'Unknown compact payload'}
  $original=$originalInputs.atlases.($item.file)
  if($null -eq $original -or $item.original_path -ne $original.path -or $item.original_sha256 -ne $original.sha256){throw 'Compact payload original differs'}
  if($item.header -ne ('compact/'+$item.file+'.header') -or $compact.ContainsKey($item.file)){throw 'Invalid compact header'}
  $compact[$item.file]=$item
 }
}
function Get-CompactSpec([string]$Path){
 foreach($name in $compact.Keys){if([IO.Path]::GetFullPath($Path) -eq [IO.Path]::GetFullPath((Join-Path $package $name))){return $compact[$name]}}
 if(Test-Path -LiteralPath ($Path+'.compact.json')){
  if(-not [IO.Path]::GetFullPath($Path).StartsWith([IO.Path]::GetFullPath($package)+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Compact backup escapes seed folder'}
  $item=Get-Content -LiteralPath ($Path+'.compact.json') -Raw | ConvertFrom-Json
  $source=$compact[$item.file]
  if($null -eq $source -or $item.original_path -ne $source.original_path -or $item.original_sha256 -ne $source.original_sha256 -or $item.original_data_offset -ne $source.original_data_offset){throw 'Compact backup original differs'}
  $head=[IO.Path]::GetFullPath((Join-Path $package $item.header))
  if(-not $head.StartsWith([IO.Path]::GetFullPath($package)+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Compact backup header escapes seed folder'}
  return $item
 }
 return $null
}
function Get-CompactSha([string]$Path){
 $item=Get-CompactSpec $Path
 if($null -eq $item){return $null}
 $header=Join-Path $package $item.header
 if((Get-Sha $header) -ne $item.header_sha256 -or (Get-Sha $item.original_path) -ne $item.original_sha256){throw 'Compact seed header or shared original changed'}
 $value=[CompactSeedPayload]::Hash($header,$item.original_path,[long]$item.original_data_offset)
 if($value -ne $item.patched_sha256){throw 'Compact seed reconstruction checksum differs'}
 return $value
}
function Copy-SeedPayload([string]$Relative,[string]$Target){
 $source=if([IO.Path]::IsPathRooted($Relative)){$Relative}else{Join-Path $package $Relative}
 $item=Get-CompactSpec $source
 if($null -eq $item){Copy-Item -LiteralPath $source -Destination $Target -Force;return}
 # Recheck the instructions and shared original before writing. The surrounding
 # installer has already verified every payload and backed up every game file.
 $verified=Get-CompactSha $source
 $actual=[CompactSeedPayload]::Write((Join-Path $package $item.header),$item.original_path,[long]$item.original_data_offset,$Target)
 if($actual -ne $verified){throw 'Compact seed write checksum differs; rolling back'}
}
function Save-SeedBackup($Row,[string]$Target){
 $name=[IO.Path]::GetFileName($Row.package_path)
 if(-not $compact.ContainsKey($name)){Copy-Item -LiteralPath $Target -Destination $Row.backup;return}
 $source=$compact[$name];$header=$Row.backup+'.header'
 [IO.File]::WriteAllBytes($header,[CompactSeedPayload]::ReadHeader($Target))
 $relative=$header.Substring([IO.Path]::GetFullPath($package).Length+1).Replace('\','/')
 $item=[pscustomobject]@{file=$name;header=$relative;header_sha256=(Get-Sha $header);original_path=$source.original_path;original_sha256=$source.original_sha256;original_data_offset=$source.original_data_offset;patched_sha256=$Row.original_sha256;expanded_bytes=(Get-Item -LiteralPath $Target).Length}
 [IO.File]::WriteAllText($Row.backup+'.compact.json',($item | ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
 if((Get-CompactSha $Row.backup) -ne $Row.original_sha256){throw 'Installed atlas body differs; no game files changed'}
}
'''

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()

def pac_data(path):
 with Path(path).open('rb') as f:
  b=f.read(48)
 if b[:4]!=b'PAC\0':raise ValueError('Invalid PAC')
 if b[4:9]==b'0.01a':return struct.unpack_from('>I',b,24)[0]
 if b[4:9]==b'0.01b':return struct.unpack_from('<Q',b,32)[0]
 raise ValueError('Unknown PAC format')

def virtual_sha(package,item):
 p=Path(package);original=Path(item['original_path']);header=p/item['header']
 if sha(original)!=item['original_sha256'] or sha(header)!=item['header_sha256']:raise ValueError('Compact inputs changed')
 h=hashlib.sha256(header.read_bytes())
 with original.open('rb') as f:
  f.seek(item['original_data_offset'])
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 result=h.hexdigest()
 if result!=item['patched_sha256']:raise ValueError('Compact reconstruction differs')
 return result

def prepare_atlases(package,originals,aliases):
 """Create only a PAC index/header and a recipe, never a full texture copy."""
 p=Path(package);(p/'compact').mkdir(exist_ok=True);records=[]
 for label,name in (('small','atlas_pc_jp_Zlib_ps2.pac'),('main','atlas_pc_Zlib.pac')):
  original=originals[name];path=Path(original['path'])
  with path.open('rb') as f:
   first=f.read(48);big=first[4:9]==b'0.01a';endian='>' if big else '<';width=4 if big else 8;number='I' if big else 'Q'
   n=struct.unpack_from(endian+'I',first,12)[0];names,table,data=struct.unpack_from(endian+number*3,first,16)
   f.seek(0);head=f.read(data)
  entries=[]
  for i in range(n):
   key=head[names+i*32:names+(i+1)*32].split(b'\0')[0].decode('ascii')
   size,off=struct.unpack_from(endian+number*2,head,table+i*2*width);entries.append([key,size,off])
  byname={r[0]:r for r in entries};output=[r[:] for r in entries]
  for target,donor in sorted(aliases[label].items()):
   if len(target.encode())>32 or donor not in byname:raise ValueError('Invalid atlas instruction')
   entry=[target,*byname[donor][1:]];found=next((i for i,r in enumerate(output) if r[0]==target),None)
   if found is not None:output[found]=entry;continue
   suffix='.tbl' if target.endswith('.tbl') else '.dat';stage=target.split('_',1)[0]+'_'
   candidates=[i for i,r in enumerate(output) if r[0].startswith(stage) and r[0].endswith(suffix) and (suffix!='.dat' or not r[0].endswith('_msk.dat'))]
   if not candidates:candidates=[i for i,r in enumerate(output) if r[0].endswith(suffix) and (suffix!='.dat' or not r[0].endswith('_msk.dat'))]
   if not candidates:raise ValueError('No atlas texture group')
   output.insert(candidates[0],entry)
  new_table=names+len(output)*32;new_data=new_table+len(output)*2*width
  header=bytearray(head[:names]);struct.pack_into(endian+'I',header,12,len(output));struct.pack_into(endian+number*3,header,16,names,new_table,new_data)
  for key,size,off in output:header.extend(key.encode().ljust(32,b'\0'))
  for key,size,off in output:header.extend(struct.pack(endian+number*2,size,off))
  assert len(header)==new_data
  hp=p/'compact'/(name+'.header');hp.write_bytes(header)
  h=hashlib.sha256(header)
  with path.open('rb') as f:
   f.seek(data)
   for b in iter(lambda:f.read(1048576),b''):h.update(b)
  records.append(dict(file=name,header=hp.relative_to(p).as_posix(),header_sha256=sha(hp),original_path=original['path'],original_sha256=original['sha256'],original_data_offset=data,patched_sha256=h.hexdigest(),expanded_bytes=new_data+path.stat().st_size-data))
 (p/'compact-payloads.json').write_text(json.dumps(dict(format=1,files=records),indent=2)+'\n')
 return records

def compact(package):
 p=Path(package).resolve();inputs=json.loads((p/'original-inputs.json').read_text())
 plan=json.loads((p/'installation-plan.json').read_text());records=[]
 (p/'compact').mkdir(exist_ok=True)
 prebuilt=json.loads((p/'compact-payloads.json').read_text())['files'] if (p/'compact-payloads.json').is_file() else []
 for row in plan['files']:
  name=row['package_path']
  if name not in ('atlas_pc_Zlib.pac','atlas_pc_jp_Zlib_ps2.pac'):continue
  prior=next((r for r in prebuilt if r['file']==name),None)
  if prior:
   if virtual_sha(p,prior)!=row['patched_sha256']:raise ValueError('Prebuilt atlas instructions differ')
   records.append(prior);continue
  full=p/name;original=inputs['atlases'][name];off=pac_data(original['path']);new_off=pac_data(full)
  if full.stat().st_size-new_off!=Path(original['path']).stat().st_size-off:raise ValueError('Atlas body size changed')
  header=p/'compact'/(name+'.header')
  with full.open('rb') as f:header.write_bytes(f.read(new_off))
  item=dict(file=name,header=header.relative_to(p).as_posix(),header_sha256=sha(header),original_path=original['path'],original_sha256=original['sha256'],original_data_offset=off,patched_sha256=row['patched_sha256'],expanded_bytes=full.stat().st_size)
  # Independently proves every original body byte is unchanged before removing
  # this task's newly generated full atlas. No installed/original file is deleted.
  if sha(full)!=row['patched_sha256'] or virtual_sha(p,item)!=row['patched_sha256']:raise ValueError('Atlas compact roundtrip failed')
  records.append(item)
 if len(records)!=2:raise ValueError('Both atlases are required for compact seeds')
 (p/'compact-payloads.json').write_text(json.dumps(dict(format=1,files=records),indent=2)+'\n')
 (p/'runtime/CompactSeedPayload.cs').write_text(CS)
 installer=p/'Install-preview.ps1';text=installer.read_text(encoding='utf-8-sig')
 anchor='if($Restore){'
 if text.count(anchor)!=1:raise ValueError('Installer restore boundary changed')
 text=text.replace(anchor,PS+'\n'+anchor,1)
 needle='if(-not (Test-Path -LiteralPath $Path)){return $null}'
 if text.count(needle)!=1:raise ValueError('Installer hash boundary changed')
 text=text.replace(needle,'if(-not (Test-Path -LiteralPath $Path)){return Get-CompactSha $Path}',1)
 needle='Copy-Item -LiteralPath (Join-Path $package $row.package_path) -Destination $target -Force'
 if text.count(needle)!=1:raise ValueError('Installer payload write boundary changed')
 text=text.replace(needle,'Copy-SeedPayload $row.package_path $target',1)
 text=text.replace('Copy-Item -LiteralPath (Get-Target $row.relative_path) -Destination $row.backup','Save-SeedBackup $row (Get-Target $row.relative_path)')
 text=text.replace('Copy-Item -LiteralPath $row.backup -Destination $target -Force','Copy-SeedPayload $row.backup $target')
 text=text.replace('Copy-Item -LiteralPath $row.backup -Destination (Get-Target $relative) -Force','Copy-SeedPayload $row.backup (Get-Target $relative)')
 installer.write_text(text,encoding='utf-8')
 for item in records:
  full=p/item['file']
  if full.parent!=p or full.resolve().parent!=p:raise ValueError('Compact deletion escaped new package')
  if full.exists():full.unlink()
 summary=dict(format=1,mode='shared-original-instructions',files=records,omitted_full_payload_bytes=sum(i['expanded_bytes'] for i in records),instruction_bytes=sum((p/i['header']).stat().st_size for i in records),shared_originals_preserved=True)
 (p/'compact-storage.json').write_text(json.dumps(summary,indent=2)+'\n')
 return summary
