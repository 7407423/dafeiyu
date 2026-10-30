# DaFeiYu v2 setup / repair.
# Usage: powershell -ExecutionPolicy Bypass -File tools\install.ps1
# NOTE: ASCII-only on purpose (PowerShell 5.1 parses .ps1 as ANSI without a BOM).

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Write-Host "root: $root"

$candidates = @(
  "$env:USERPROFILE\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe",
  "D:\python.exe",
  (Get-Command python -ErrorAction SilentlyContinue).Source
) | Where-Object { $_ -and (Test-Path $_) }

$python = $null
foreach ($p in $candidates) {
  try {
    $ver = & $p -c "import sys;print('%d.%d' % sys.version_info[:2])" 2>$null
    if ($ver -and [version]$ver -ge [version]'3.10') { $python = $p; break }
  } catch { }
}
if (-not $python) { throw "Python 3.10+ not found" }
Write-Host "python: $python"

$venv = Join-Path $root '.venv'
if (-not (Test-Path "$venv\Scripts\python.exe")) {
  Write-Host "creating venv ..."
  & $python -m venv $venv
}
$py = "$venv\Scripts\python.exe"

Write-Host "installing PySide6 / APScheduler ..."
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install PySide6 APScheduler

Write-Host "initializing database ..."
Push-Location $root
& $py -c "import sys;sys.path.insert(0,'.');from core import settings,db;settings.ensure_dirs();print(db.init_db())"
Pop-Location

Write-Host "creating desktop shortcut ..."
& powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'make_shortcut.ps1')

Write-Host ""
Write-Host "done. double-click the desktop shortcut to start." -ForegroundColor Green
Write-Host "health check: $py tools\doctor.py" -ForegroundColor DarkGray
