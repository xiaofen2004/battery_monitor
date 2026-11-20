param([string]$OutputName = ('battery_strain_monitor_exe_' + (Get-Date -Format 'yyyyMMdd')))
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.build-venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Create .build-venv and install requirements.txt plus pyinstaller first.' }
$distpath = Join-Path '..\outputs' $OutputName
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name BatteryStrainMonitor --distpath $distpath --workpath '.build-work' --specpath '.build-spec' --collect-data matplotlib --hidden-import matplotlib.backends.backend_tkagg --hidden-import matplotlib.backends.backend_pdf --hidden-import openpyxl --hidden-import xlrd --hidden-import pandas.io.excel._openpyxl exe_entry.py
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
Write-Host ('EXE output: ' + (Resolve-Path -LiteralPath $distpath))
