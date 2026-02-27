# deploy-to-prod.ps1
# Copies the *versioned* repo files into the production folder (telegram-mtproto)
# WITHOUT touching production-only secrets/state (.env, venv, logs, json state, etc.).
#
# Run:
#   pwsh -NoProfile -ExecutionPolicy Bypass -File .\deploy-to-prod.ps1

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$prodRoot = Join-Path (Split-Path -Parent $repoRoot) 'telegram-mtproto'

if (-not (Test-Path $prodRoot)) {
  throw "Production folder not found: $prodRoot"
}

Write-Host "Repo: $repoRoot"
Write-Host "Prod: $prodRoot"

# Copy only tracked/source files. Keep this list explicit to avoid leaking secrets/state.
$files = @(
  'monitor.py',
  'requirements.txt',
  'README.md',
  'run-monitor.cmd',
  '.env.example',
  '.gitignore',
  'tail_events.py',
  'cleanup-workspace.ps1'
)

foreach ($f in $files) {
  $src = Join-Path $repoRoot $f
  if (-not (Test-Path $src)) { throw "Missing in repo: $f" }
  $dst = Join-Path $prodRoot $f
  Copy-Item -Force -Path $src -Destination $dst
  Write-Host "Copied: $f"
}

Write-Host "Done. Production code updated (secrets/state untouched)."
