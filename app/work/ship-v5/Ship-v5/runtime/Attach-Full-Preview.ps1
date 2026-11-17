param([switch]$AtMainMenu,[int]$GameProcessId=0,[string]$GamePath='')
$ErrorActionPreference='Stop'
if(-not $AtMainMenu){throw 'Run only after the game reaches its main menu.'}
$package=Split-Path -Parent $PSScriptRoot
$manifest=Get-Content -LiteralPath (Join-Path $package 'manifest.json') -Raw | ConvertFrom-Json
$plan=Get-Content -LiteralPath (Join-Path $package 'installation-plan.json') -Raw | ConvertFrom-Json
function Get-Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
if($manifest.music_sector_source.archive_sha256 -ne $manifest.patched_sha256){throw 'Music lookup map does not match this archive'}
foreach($file in $plan.files){
 if((Get-Sha (Join-Path $GamePath $file.relative_path)) -ne $file.patched_sha256){throw ('Preview is not fully installed: '+$file.relative_path)}
}
foreach($dependency in $plan.dependencies){
 if((Get-Sha (Join-Path $GamePath $dependency.relative_path)) -ne $dependency.sha256){throw ('Required v3 dependency differs: '+$dependency.relative_path)}
}
foreach($helper in $manifest.runtime_helpers){
 if((Get-Sha (Join-Path $PSScriptRoot $helper.file)) -ne $helper.sha256){throw ('Runtime helper hash mismatch: '+$helper.file)}
}
if((Get-Sha (Join-Path $PSScriptRoot 'MusicSectorAdapter.exe')) -ne $manifest.music_sector_source.helper_sha256){throw 'Bank lookup helper provenance differs'}
foreach($bank in $manifest.original_music_banks){
 if((Get-Sha (Join-Path (Join-Path $GamePath 'sound\Windows') $bank.file)) -ne $bank.sha256){throw ('An authored music bank differs: '+$bank.file)}
}
$games=@(Get-Process Zoe2Mars -ErrorAction SilentlyContinue)
if($GameProcessId){$games=@($games | Where-Object {$_.Id -eq $GameProcessId})}
if($games.Count -ne 1){throw 'Exactly one ZOE2 game process must be at the main menu'}
foreach($helper in $manifest.runtime_helpers){
 $path=Join-Path $PSScriptRoot $helper.file
 if($helper.file -eq 'SeededMetatronAdapter.exe'){
  & $path --attach-menu $games[0].Id $manifest.seed ([string]$manifest.settings.metatron_subweapon_chance_percent)
 }else{ & $path --attach-menu $games[0].Id }
 if($LASTEXITCODE -ne 0){throw ($helper.file+' failed. Close and relaunch the game before retrying any attachment.')}
}
$record=[pscustomobject]@{utc=[DateTime]::UtcNow.ToString('o');pid=$games[0].Id;stage_sha256=$manifest.patched_sha256;helper_count=$manifest.runtime_helpers.Count;boss_seed=$manifest.boss_seed;music_seed=$manifest.music_track_shuffle.seed;ada_seed=$manifest.ada_overlay.seed;difficulty='Not inferred; record the selected difficulty in gameplay notes'}
$record | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $package 'last-attachment.json') -Encoding UTF8
Write-Host ('All '+$manifest.runtime_helpers.Count+' helpers attached. Closing the game removes these runtime hooks.')
