# Creates a MediaPress desktop shortcut that launches with no console window.
# Run this once: right-click → "Run with PowerShell", or from a terminal.

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw    = (Get-Command pythonw.exe -ErrorAction Stop).Source
$script     = Join-Path $projectDir "mediapress.py"
$desktop    = [Environment]::GetFolderPath("Desktop")
$shortcut   = Join-Path $desktop "MediaPress.lnk"
$icon       = Join-Path $projectDir "mediapress.ico"

# Use the Python icon if a custom one doesn't exist
if (-not (Test-Path $icon)) {
    $icon = $pythonw
}

$wsh  = New-Object -ComObject WScript.Shell
$lnk  = $wsh.CreateShortcut($shortcut)
$lnk.TargetPath       = $pythonw
$lnk.Arguments        = "`"$script`""
$lnk.WorkingDirectory = $projectDir
$lnk.WindowStyle      = 1          # Normal window
$lnk.IconLocation     = "$icon, 0"
$lnk.Description      = "MediaPress - Media Compression Tool"
$lnk.Save()

Write-Host "Shortcut created: $shortcut"
