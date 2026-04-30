@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python launcher ^("py"^) not found. Please install Python 3.10+ first.
  exit /b 1
)

py -3 -m pip install --upgrade pip
if errorlevel 1 exit /b 1

py -3 -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1

py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name TileDownloader main.py
if errorlevel 1 exit /b 1

echo.
echo Build done. EXE path: %cd%\dist\TileDownloader.exe
endlocal
