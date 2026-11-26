@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === CAI DAT CLOUDSHOP (chay mot lan tren may moi) ===

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Khong tim thay Python. Hay cai Python 3.11 tu https://www.python.org/downloads/ va tick "Add python.exe to PATH".
  pause
  exit /b 1
)
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
  echo Can Python 3.10 tro len. Phien ban hien tai:
  %PY% --version
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Tao moi truong ao .venv ...
  %PY% -m venv .venv
  if errorlevel 1 ( echo Tao moi truong ao that bai. & pause & exit /b 1 )
)

echo Cai thu vien cho website ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo Cai thu vien that bai. Kiem tra ket noi Internet roi chay lai. & pause & exit /b 1 )

echo Cai cong cu kiem thu (pytest, locust) ...
".venv\Scripts\python.exe" -m pip install -r requirements-tools.txt
if errorlevel 1 echo Canh bao: chua cai duoc cong cu kiem thu. Website va demo van chay duoc.

echo.
echo Xong. Chay CHAY_DEMO.bat de xem demo can bang tai, hoac CHAY_WEB.bat de chay website.
pause
