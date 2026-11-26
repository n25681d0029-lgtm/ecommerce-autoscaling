@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chua cai dat. Hay chay CAI_DAT.bat truoc.
  pause
  exit /b 1
)
echo === CHAY BO KIEM THU TU DONG ===
".venv\Scripts\python.exe" -m pytest
pause
