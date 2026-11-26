@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chua cai dat. Hay chay CAI_DAT.bat truoc.
  pause
  exit /b 1
)
echo === CHAY WEBSITE (mot may chu) ===
echo Mo http://127.0.0.1:8000 - nhan Ctrl+C de dung.
start "" cmd /c "timeout /t 5 >nul & start http://127.0.0.1:8000"
".venv\Scripts\python.exe" run_local.py
pause
