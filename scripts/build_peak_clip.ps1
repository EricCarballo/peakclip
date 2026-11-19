param([string]$Destination = 'release-subtitles')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
npm --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw 'Falló la compilación de la interfaz.' }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath $Destination "packaging\Peak Clip.spec"
if ($LASTEXITCODE -ne 0) { throw 'Falló el empaquetado.' }
Write-Host "Listo: $Destination\Peak Clip\Peak Clip.exe"
