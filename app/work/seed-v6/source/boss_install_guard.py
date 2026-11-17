import portable_paths as _portable
"""Generate the installation gate once; GUI Apply never regenerates scripts."""
import json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
MARKER='# Required boss-spawn validation v2'

def console_python(executable=None):
    path=Path(executable or sys.executable)
    if path.name.lower()=='pythonw.exe': path=path.with_name('python.exe')
    if not path.is_file(): raise FileNotFoundError('Console Python is unavailable: '+str(path))
    return path

def ps_quote(value):return "'"+str(value).replace("'","''")+"'"

def ensure_gate(package):
    p=Path(package);installer=p/'Install-preview.ps1';text=installer.read_text(encoding='utf-8-sig')
    python=console_python()
    wrapper="""$ErrorActionPreference='Stop'
$validator=VALIDATOR
$python=PYTHON
if(-not (Test-Path -LiteralPath $validator) -or -not (Test-Path -LiteralPath $python)){throw 'Required build validator is unavailable. No game files changed.'}
$attempt=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fffffff')+'-'+[guid]::NewGuid().ToString('N')
$logs=Join-Path $PSScriptRoot 'verification'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$stdout=Join-Path $logs ($attempt+'-stdout.log')
$stderr=Join-Path $logs ($attempt+'-stderr.log')
$report=Join-Path $logs ($attempt+'-preflight.json')
$arguments='-u "'+$validator+'" --package "'+$PSScriptRoot+'" --output "'+$report+'"'
$child=Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
$code=$child.ExitCode
Get-Content -LiteralPath $stdout | Write-Host
Get-Content -LiteralPath $stderr | Write-Host
if($code -ne 0){throw ('Build validation failed (exit '+$code+'). No game files changed. Report: '+$report+'; stderr: '+$stderr)}
if(-not (Test-Path -LiteralPath $report)){throw 'Validator returned success without a fresh report. No game files changed.'}
$fresh=Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
if($fresh.passed -ne $true -or $fresh.diagnostic_only -eq $true){throw 'Fresh installation validation did not pass. No game files changed.'}
Write-Host ('Fresh preflight passed: '+$fresh.seed+' / '+$fresh.archive_sha256)
exit 0
""".replace('VALIDATOR',ps_quote(ROOT/'apply_validation.py')).replace('PYTHON',ps_quote(python))
    (p/'Validate boss spawns.ps1').write_text(wrapper,encoding='utf-8')
    block="""# Required boss-spawn validation v2
$bossCheck=Join-Path $package 'Validate boss spawns.ps1'
if(-not (Test-Path -LiteralPath $bossCheck)){throw 'Required build validation is missing. No game files changed.'}
& "$env:SystemRoot\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File $bossCheck
if($LASTEXITCODE -ne 0){throw 'Build validation failed. No game files changed. See the attempt report and stdout/stderr in verification.'}

"""
    if '# Required boss-spawn validation v1' in text:
        text,count=re.subn(r'# Required boss-spawn validation v1\n.*?\n\n',lambda _:block,text,count=1,flags=re.S)
        if count!=1:raise ValueError('Cannot upgrade legacy validation boundary')
    elif MARKER not in text:
        anchor='if(Test-Path -LiteralPath $journalPath){'
        if text.count(anchor)!=1:raise ValueError('Cannot locate safe installer preflight boundary')
        text=text.replace(anchor,block+anchor,1)
    if text.count(MARKER)!=1 or text.index(MARKER)>text.index('foreach($dependency in $plan.dependencies)'):
        raise ValueError('Build check is not before installation preflight')
    installer.write_text(text,encoding='utf-8')
    config=dict(format=2,required=True,validator=str(ROOT/'apply_validation.py'),python=str(python),
                fresh_check_before_install=True,restore_allowed_without_check=True,explicit_wait=True)
    (p/'boss-spawn-check.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    return config
