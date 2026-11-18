@echo off
cd /d "%~dp0"
if exist "%~dp0release-portable\Peak Clip\Peak Clip.exe" (
  start "" "%~dp0release-portable\Peak Clip\Peak Clip.exe"
) else if exist "%~dp0release-studio\Peak Clip\Peak Clip.exe" (
  start "" "%~dp0release-studio\Peak Clip\Peak Clip.exe"
) else (
  echo Compila primero con scripts\build_portable.ps1
  pause
)
