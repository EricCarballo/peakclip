$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
Write-Host '1/3 Compilando Peak Clip…'
& .\scripts\build_peak_clip.ps1
if ($LASTEXITCODE -ne 0) { throw 'Falló build_peak_clip.ps1' }

$portable = Join-Path $root 'release-portable\Peak Clip'
$tools = Join-Path $portable 'tools'
$scriptsDir = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\Scripts'
Write-Host '2/3 Empaquetando versión portable…'
if (Test-Path (Join-Path $root 'release-portable')) {
  Remove-Item -Recurse -Force (Join-Path $root 'release-portable')
}
New-Item -ItemType Directory -Force -Path $tools | Out-Null
Copy-Item -Recurse -Force (Join-Path $root 'release-studio\Peak Clip\*') $portable
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
