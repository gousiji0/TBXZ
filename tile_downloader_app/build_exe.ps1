Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Set-Location $PSScriptRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' not found. Please install Python 3.10+ first."
}

py -3 -m pip install --upgrade pip
py -3 -m pip install -r requirements-build.txt
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name TileDownloader main.py

Write-Host "`nBuild done. EXE path: $PSScriptRoot\dist\TileDownloader.exe"
