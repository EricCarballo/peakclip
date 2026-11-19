$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
Write-Host '1/3 Compilando Peak Clip…'
& .\scripts\build_peak_clip.ps1 -Destination 'release-subtitles'
if ($LASTEXITCODE -ne 0) { throw 'Falló build_peak_clip.ps1' }

$portable = Join-Path $root 'release-portable\Peak Clip'
$tools = Join-Path $portable 'tools'
$scriptsDir = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\Scripts'
Write-Host '2/3 Empaquetando versión portable…'
if (Test-Path (Join-Path $root 'release-portable')) {
  $resolvedTarget = (Resolve-Path -LiteralPath (Join-Path $root 'release-portable')).Path
  $expectedTarget = [System.IO.Path]::GetFullPath((Join-Path $root 'release-portable'))
  if ($resolvedTarget -ne $expectedTarget) { throw 'Destino portable inesperado.' }
  Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $tools | Out-Null
Copy-Item -Recurse -Force (Join-Path $root 'release-subtitles\Peak Clip\*') $portable
foreach ($name in @('ffmpeg.exe', 'yt-dlp.exe', 'TwitchDownloaderCLI.exe')) {
  $src = Join-Path $scriptsDir $name
  if (-not (Test-Path $src)) { throw "No se encontró $src" }
  Copy-Item -Force $src (Join-Path $tools $name)
}
@'
Peak Clip — versión portable para Windows
1. Abre Peak Clip.exe
2. No borres _internal ni tools
'@ | Set-Content -Encoding UTF8 (Join-Path $portable 'LEEME.txt')
$zip = Join-Path $root 'Peak-Clip-portable-windows.zip'
if (Test-Path $zip) { Remove-Item -Force $zip }
Compress-Archive -Path (Join-Path $root 'release-portable\Peak Clip') -DestinationPath $zip -Force
Write-Host "3/3 Listo: $zip"

$exe = Join-Path $portable 'Peak Clip.exe'
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop 'Peak Clip.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = $portable
$shortcut.IconLocation = $exe
$shortcut.Description = 'Peak Clip'
$shortcut.Save()
Write-Host "Acceso directo actualizado: $shortcutPath"
