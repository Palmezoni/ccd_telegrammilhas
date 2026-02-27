# cleanup-workspace.ps1
# Purpose: clean up telegram-mtproto workspace folder by archiving unused/legacy files.
# Safe by default: moves files into .\_archive\<timestamp>\ instead of deleting.
# Run in PowerShell (Admin not required for file moves):
#   cd C:\Users\palme\.openclaw\workspace\telegram-mtproto
#   pwsh -NoProfile -ExecutionPolicy Bypass -File .\cleanup-workspace.ps1

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$ts = Get-Date -Format 'yyyyMMdd-HHmmss'
$archiveRoot = Join-Path $root "_archive\\$ts"
New-Item -ItemType Directory -Force -Path $archiveRoot | Out-Null

function Move-IfExists($relativePath) {
  $p = Join-Path $root $relativePath
  if (Test-Path $p) {
    $destDir = Split-Path -Parent (Join-Path $archiveRoot $relativePath)
    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Force -Path $destDir | Out-Null }
    Move-Item -Force -Path $p -Destination (Join-Path $archiveRoot $relativePath)
    Write-Host "Archived: $relativePath"
  }
}

Write-Host "Archiving legacy/unused files into: $archiveRoot"

# Legacy service attempt artifacts (not used with Task Scheduler)
Move-IfExists 'install-service.ps1'
Move-IfExists 'service-runner.cmd'
Move-IfExists 'logs\\service.out.log'
Move-IfExists 'logs\\service.err.log'

# Old watchdog approach (must be disabled to avoid duplicate monitors)
Move-IfExists 'watchdog.vbs'
Move-IfExists 'watchdog.ps1'

# Optional helper script (keep if you still use it)
# Move-IfExists 'tail_events.py'

# Old/extra runtime logs you may not need long-term
# (We keep monitor logs by default; comment out if you want them archived too)
# Move-IfExists 'logs\\monitor-*.out.log'  # glob not supported by this helper

Write-Host "Done. Review the _archive folder; you can delete it later if everything is OK."
