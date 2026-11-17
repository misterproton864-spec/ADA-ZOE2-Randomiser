import portable_paths as _portable
"""Strengthen the generated main-menu launcher before package provenance is sealed."""
from pathlib import Path
from installer_support import allow_new_files


def prepare(package):
    path = Path(package) / 'runtime/Attach-Full-Preview.ps1'
    text = path.read_text(encoding='utf-8-sig')
    text = text.replace('param([switch]$AtMainMenu,','param([switch]$AtMainMenu,[switch]$VerifyOnly,',1)
    anchor = "$manifest=Get-Content -LiteralPath (Join-Path $package 'manifest.json') -Raw | ConvertFrom-Json"
    receipt = """$journalPath=Join-Path $package 'installation-journal.json'
if(-not (Test-Path -LiteralPath $journalPath)){throw 'This seed has no successful Apply receipt. Close the game and Apply an installable seed before attaching.'}
$journal=Get-Content -LiteralPath $journalPath -Raw | ConvertFrom-Json
if($journal.status -ne 'installed'){throw ('This seed is not installed (receipt: '+$journal.status+'). Successfully Apply it before attaching.')}
if(-not $PSBoundParameters.ContainsKey('GamePath')){$GamePath=$journal.game_root}
if([IO.Path]::GetFullPath($GamePath).TrimEnd('\\') -ne [IO.Path]::GetFullPath($journal.game_root).TrimEnd('\\')){throw 'Selected game directory differs from the Apply receipt.'}
$build=Get-Content -LiteralPath (Join-Path $package 'build-result.json') -Raw | ConvertFrom-Json
if($build.installable -ne $true){throw ('This seed is diagnostic only. Apply and attachment remain blocked: '+($build.blocked_reasons -join '; '))}
"""
    if text.count(anchor) != 1:
        raise ValueError('Cannot locate attachment preflight boundary')
    text = text.replace(anchor, receipt + anchor, 1)
    text = text.replace(anchor, anchor + "\nif($build.seed -ne $manifest.seed -or $build.archive_sha256 -ne $manifest.patched_sha256){throw 'Build seed/archive metadata disagree. No helpers started.'}", 1)
    health_check = """if($manifest.health_multiplier_runtime.enabled){
 $health=$manifest.health_multiplier_runtime
 if($health.enemy_multiplier -notin @(1,2,3) -or $health.boss_multiplier -notin @(1,2,3)){throw 'Invalid health multiplier metadata'}
 $healthTargets=Join-Path $package $health.target_file
 if((Get-Sha $healthTargets) -ne $health.target_sha256){throw 'Health target list differs from this seed. No helpers started.'}
 if((Get-Sha (Join-Path $PSScriptRoot $health.helper)) -ne $health.helper_sha256){throw 'Health helper differs from this seed. No helpers started.'}
}
"""
    anchor = "if((Get-Sha (Join-Path $PSScriptRoot 'MusicSectorAdapter.exe'))"
    if text.count(anchor) != 1:
        raise ValueError('Cannot locate health preflight boundary')
    text = text.replace(anchor, health_check + anchor, 1)
    hook = " }else{ & $path --attach-menu $games[0].Id }"
    branch = """ }elseif($helper.file -eq 'HealthMultiplierAdapter.exe'){
  & $path --attach-menu $games[0].Id ([string]$manifest.health_multiplier_runtime.enemy_multiplier) ([string]$manifest.health_multiplier_runtime.boss_multiplier) (Join-Path $package $manifest.health_multiplier_runtime.target_file)
 }else{ & $path --attach-menu $games[0].Id }"""
    if text.count(hook) != 1:
        raise ValueError('Cannot locate health attach boundary')
    text = text.replace(hook, branch, 1)
    check = " if((Get-Sha (Join-Path $GamePath $file.relative_path)) -ne $file.patched_sha256){throw ('Preview is not fully installed: '+$file.relative_path)}"
    replacement = """ $entry=@($journal.files | Where-Object {$_.relative_path -eq $file.relative_path})
 if($entry.Count -ne 1 -or $entry[0].patched_sha256 -ne $file.patched_sha256){throw ('Apply receipt differs from this build: '+$file.relative_path)}
 $actual=Get-Sha (Join-Path $GamePath $file.relative_path)
 if($actual -ne $file.patched_sha256){throw ('Installed files do not match seed '+$manifest.seed+': '+$file.relative_path+'. Expected '+$file.patched_sha256+'; actual '+$actual+'. The game may have been reinstalled, restored or another seed applied. Close the game and successfully Apply an installable seed before attaching. No helpers started.')}
""".rstrip()
    if text.count(check) != 1:
        raise ValueError('Cannot locate full attachment file validation')
    text = text.replace(check, replacement, 1)
    anchor = "if($games.Count -ne 1){throw 'Exactly one ZOE2 game process must be at the main menu'}"
    if text.count(anchor) != 1:
        raise ValueError('Cannot locate attachment process validation')
    text = text.replace(anchor, anchor + "\nif([IO.Path]::GetFullPath($games[0].Path) -ne [IO.Path]::GetFullPath((Join-Path $GamePath 'Zoe2Mars.exe'))){throw 'The running game is from a different installation. No helpers started.'}", 1)
    text = text.replace('$games=@(Get-Process Zoe2Mars',"if($VerifyOnly){Write-Host 'Installed files and helper hashes verified. No helpers started.';exit 0}\n$games=@(Get-Process Zoe2Mars",1)
    text = allow_new_files(text)  # Same .NET hashing as the Windows installer.
    path.write_text(text, encoding='utf-8')
