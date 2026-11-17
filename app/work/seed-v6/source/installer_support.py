import portable_paths as _portable
"""Extend the existing transaction to back up, add and restore new audio files."""
import re

ATOMIC_JOURNAL = r'''function Save-Journal($Value){
 $temporary=$journalPath+'.'+[Guid]::NewGuid().ToString('N')+'.tmp'
 try {
  [IO.File]::WriteAllText($temporary,($Value | ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
  for($attempt=0;$attempt -lt 40;$attempt++){
   try {
    if([IO.File]::Exists($journalPath)){[IO.File]::Replace($temporary,$journalPath,[NullString]::Value)}else{[IO.File]::Move($temporary,$journalPath)}
    return
   } catch [IO.IOException] {
    if($attempt -eq 39){throw}
    Start-Sleep -Milliseconds 50
   }
  }
 } finally {if([IO.File]::Exists($temporary)){[IO.File]::Delete($temporary)}}
}'''

def durable_journal(text):
 old="function Save-Journal($Value){$Value | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $journalPath -Encoding UTF8}"
 if old not in text:raise ValueError('Expected installer journal template is missing')
 return text.replace(old,ATOMIC_JOURNAL,1)
def allow_new_files(text):
 text=text.replace("function Get-Sha([string]$Path){(Get-FileHash", "function Get-Sha([string]$Path){if(-not (Test-Path -LiteralPath $Path)){return $null};(Get-FileHash")
 text=text.replace(" Copy-Item -LiteralPath $row.backup -Destination $target -Force", " if($null -eq $row.original_sha256){Remove-Item -LiteralPath $target -Force}else{Copy-Item -LiteralPath $row.backup -Destination $target -Force}")
 text=text.replace(" Copy-Item -LiteralPath (Get-Target $row.relative_path) -Destination $row.backup", " if($null -ne $row.original_sha256){Copy-Item -LiteralPath (Get-Target $row.relative_path) -Destination $row.backup}")
 text=text.replace("  Copy-Item -LiteralPath $row.backup -Destination (Get-Target $relative) -Force", "  if($null -eq $row.original_sha256){$target=Get-Target $relative;if(Test-Path -LiteralPath $target){Remove-Item -LiteralPath $target -Force}}else{Copy-Item -LiteralPath $row.backup -Destination (Get-Target $relative) -Force}")
 text=text.replace('Ship v5 compatibility candidate installed','Seed v6 test build installed')
 # Avoid module auto-loading differences between Windows PowerShell and a
 # parent process using PowerShell 7's PSModulePath. Hash bytes with .NET.
 text=re.sub(r'function Get-Sha\(\[string\]\$Path\)\{[^\n]*\}',lambda _:"function Get-Sha([string]$Path){if(-not (Test-Path -LiteralPath $Path)){return $null};$stream=[IO.File]::OpenRead($Path);$algorithm=[Security.Cryptography.SHA256Cng]::new();try{([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}finally{$stream.Dispose();$algorithm.Dispose()}}",text,count=1)
 return durable_journal(text) if 'function Save-Journal' in text else text
