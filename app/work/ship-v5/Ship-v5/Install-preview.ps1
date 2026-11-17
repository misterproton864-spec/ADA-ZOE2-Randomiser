param([switch]$Restore,[string]$GamePath='')
$ErrorActionPreference='Stop'
if(-not $GamePath){$inputs=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'original-inputs.json') -Raw | ConvertFrom-Json;$GamePath=$inputs.game_root}
if(Get-Process Zoe2Mars -ErrorAction SilentlyContinue){throw 'Close ZOE2 completely before installing or restoring.'}
$package=$PSScriptRoot
$plan=Get-Content -LiteralPath (Join-Path $package 'installation-plan.json') -Raw | ConvertFrom-Json
$gameRoot=(Get-Item -LiteralPath $GamePath).FullName.TrimEnd('\')
$journalPath=Join-Path $package 'installation-journal.json'
function Get-Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Save-Journal($Value){$Value | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $journalPath -Encoding UTF8}
function Get-Target([string]$Relative){
 if([IO.Path]::IsPathRooted($Relative) -or $Relative.Contains('..')){throw 'Invalid installation-relative path'}
 $target=[IO.Path]::GetFullPath((Join-Path $gameRoot $Relative))
 if(-not $target.StartsWith($gameRoot+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Target escapes the game directory'}
 $target
}
if($Restore){
 $journal=Get-Content -LiteralPath $journalPath -Raw | ConvertFrom-Json
 if($journal.game_root -ne $gameRoot -or $journal.status -ne 'installed'){throw 'No completed matching installation journal to restore'}
 foreach($row in $journal.files){
  if((Get-Sha (Get-Target $row.relative_path)) -ne $row.patched_sha256){throw ('Installed file changed since installation: '+$row.relative_path)}
  if((Get-Sha $row.backup) -ne $row.original_sha256){throw 'Restore backup hash mismatch'}
 }
 $journal.status='restoring';Save-Journal $journal
 foreach($row in $journal.files){
  $target=Get-Target $row.relative_path
  Copy-Item -LiteralPath $row.backup -Destination $target -Force
  if((Get-Sha $target) -ne $row.original_sha256){throw 'Restored file hash mismatch; preserve this journal and backups'}
 }
 $journal.status='restored';Save-Journal $journal
 Write-Host 'Previous archive, atlases and audio restored and verified.'
 exit 0
}
if(Test-Path -LiteralPath $journalPath){
 $prior=Get-Content -LiteralPath $journalPath -Raw | ConvertFrom-Json
 if($prior.status -eq 'installed'){
  foreach($row in $plan.files){if((Get-Sha (Get-Target $row.relative_path)) -ne $row.patched_sha256){throw 'Existing installation has changed; inspect it before reinstalling'}}
  Write-Host 'This preview is already installed; hashes verified.';exit 0
 }
 if($prior.status -ne 'restored'){throw 'An unfinished installation/restore journal exists; preserve and inspect it before retrying'}
}
foreach($dependency in $plan.dependencies){
 if((Get-Sha (Get-Target $dependency.relative_path)) -ne $dependency.sha256){throw ('Required v4 atlas/audio dependency differs: '+$dependency.relative_path+'. No files installed.')}
}
$rows=@()
foreach($row in $plan.files){
 $target=Get-Target $row.relative_path
 $source=Join-Path $package $row.package_path
 if((Get-Sha $source) -ne $row.patched_sha256){throw ('Package hash mismatch: '+$row.package_path)}
 $before=Get-Sha $target
 if($before -ne $row.expected_before_sha256){throw ('Installed baseline differs: '+$row.relative_path+'. Nothing has been installed.')}
 $rows+=[pscustomobject]@{relative_path=$row.relative_path;package_path=$row.package_path;original_sha256=$before;patched_sha256=$row.patched_sha256;backup=''}
}
$backupRoot=Join-Path $package ('installation-backups-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $backupRoot | Out-Null
$journal=[pscustomobject]@{status='backing_up';game_root=$gameRoot;utc=[DateTime]::UtcNow.ToString('o');files=$rows;written=@()}
Save-Journal $journal
foreach($row in $rows){
 $row.backup=Join-Path $backupRoot $row.relative_path
 New-Item -ItemType Directory -Path (Split-Path -Parent $row.backup) -Force | Out-Null
 Copy-Item -LiteralPath (Get-Target $row.relative_path) -Destination $row.backup
 if((Get-Sha $row.backup) -ne $row.original_sha256){throw 'Backup verification failed; no installation writes started'}
}
$journal.status='backed_up';Save-Journal $journal
try {
 foreach($row in $rows){
  $target=Get-Target $row.relative_path
  # Record an attempted write before copying so rollback also covers a partial copy.
  $journal.written+=@($row.relative_path);$journal.status='installing';Save-Journal $journal
  Copy-Item -LiteralPath (Join-Path $package $row.package_path) -Destination $target -Force
  if((Get-Sha $target) -ne $row.patched_sha256){throw 'Installed file verification failed'}
 }
 $journal.status='installed';Save-Journal $journal
 Write-Host 'Ship v5 compatibility candidate installed and all file hashes verified. Gameplay is still experimental.'
 Write-Host 'Launch ZOE2, stop at the main menu, then use Attach at main menu.cmd.'
} catch {
 $failure=$_
 $journal.status='rolling_back';Save-Journal $journal
 foreach($relative in $journal.written){
  $row=@($rows | Where-Object {$_.relative_path -eq $relative})[0]
  Copy-Item -LiteralPath $row.backup -Destination (Get-Target $relative) -Force
  if((Get-Sha (Get-Target $relative)) -ne $row.original_sha256){throw 'Rollback failed; retain journal and backups'}
 }
 $journal.status='rolled_back';Save-Journal $journal
 throw $failure
}
