@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Chua cai dat. Hay chay CAI_DAT.bat truoc.
  pause
  exit /b 1
)
echo === DEMO CAN BANG TAI VA CO GIAN TREN MAY CA NHAN ===
echo Trinh duyet se mo http://127.0.0.1:8000/system/live sau vai giay.
echo Trong cua so nay: go + roi Enter de them may, - de bot may, s xem trang thai, q de thoat.
echo.
start "" cmd /c "timeout /t 8 >nul & start http://127.0.0.1:8000/system/live"
".venv\Scripts\python.exe" scripts\local_cluster.py --nodes 2
pause
