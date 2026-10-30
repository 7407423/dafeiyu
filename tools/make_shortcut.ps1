# Create/refresh the desktop shortcut for DaFeiYu.
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads .ps1 as ANSI unless it has a
# UTF-8 BOM, so Chinese literals here would come out garbled (and broke the .lnk path once).
# The shortcut NAME is derived from the project folder name instead of being hard-coded.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$name = (Split-Path $root -Leaf) + '.lnk'
$vbs = Join-Path $root ((Split-Path $root -Leaf) + '-launch.vbs')
if (-not (Test-Path $vbs)) {
  # fall back to the historical launcher name (Chinese), resolved by wildcard to stay ASCII-safe
  $vbs = (Get-ChildItem $root -Filter '*.vbs' -File | Where-Object { $_.Name -notlike '*-launch*' } |
          Select-Object -First 1).FullName
}
$icon = Join-Path $root 'ui\assets\icon.ico'
if (-not (Test-Path $icon)) {
  $icon = (Get-ChildItem (Join-Path $root 'ui\assets') -Filter '*.ico' -File -ErrorAction SilentlyContinue |
           Select-Object -First 1).FullName
}
if (-not $icon) { $icon = "$env:SystemRoot\System32\shell32.dll" }

$desktop = [Environment]::GetFolderPath('Desktop')
$link = Join-Path $desktop $name

$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut($link)
$sc.TargetPath = "$env:SystemRoot\System32\wscript.exe"
$sc.Arguments = '"' + $vbs + '"'
$sc.WorkingDirectory = $root
$sc.IconLocation = "$icon,0"
$sc.Description = 'DaFeiYu'
$sc.WindowStyle = 7
$sc.Save()

Write-Host "shortcut: $link" -ForegroundColor Green
Write-Host "  target : wscript.exe `"$vbs`""
Write-Host "  icon   : $icon"
