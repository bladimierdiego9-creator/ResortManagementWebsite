$ws = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
if (-not $desktop -or -not (Test-Path $desktop)) {
    $desktop = Join-Path $env:USERPROFILE 'Desktop'
}
$shortcutPath = Join-Path $desktop "A&D Thysia Resort.lnk"
$projectDir = $PSScriptRoot
$targetBat = Join-Path $projectDir "start_server.bat"

$shortcut = $ws.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetBat
$shortcut.WorkingDirectory = $projectDir
$shortcut.Description = "Start A&D Thysia Resort Management System"
$shortcut.Save()

Write-Host "SUCCESS: Shortcut created at $shortcutPath" -ForegroundColor Green

