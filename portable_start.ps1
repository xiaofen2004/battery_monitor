param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$envDir = Join-Path $PSScriptRoot '.migration-env'
$marker = Join-Path $envDir 'monitor-ready.json'
$checkCode = "import tkinter, numpy, scipy, pandas, matplotlib, openpyxl, xlrd; print('Environment OK')"

# Discover Conda without depending on VS Code's selected Python or shell profile.
$candidates = @()
if ($env:CONDA_EXE) { $candidates += $env:CONDA_EXE }
$command = Get-Command conda.exe -ErrorAction SilentlyContinue
if ($command) { $candidates += $command.Source }
foreach ($base in @($env:CONDA_PREFIX, "$env:USERPROFILE\anaconda3", "$env:USERPROFILE\miniconda3", "$env:LOCALAPPDATA\anaconda3", "$env:LOCALAPPDATA\miniconda3", "$env:ProgramData\anaconda3", "$env:ProgramData\miniconda3")) {
    if ($base) { $candidates += (Join-Path $base 'Scripts\conda.exe') }
}
foreach ($hive in @('HKCU:\Software\Python\ContinuumAnalytics', 'HKLM:\Software\Python\ContinuumAnalytics')) {
    if (Test-Path $hive) {
        Get-ChildItem $hive | ForEach-Object {
            $key = Join-Path $_.PSPath 'InstallPath'
            if (Test-Path $key) {
                $base = (Get-Item $key).GetValue('')
                if ($base) { $candidates += (Join-Path $base 'Scripts\conda.exe') }
            }
        }
    }
}
$conda = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
if (-not $conda) {
    Write-Host 'Conda was not found. Enter the full path to Scripts\conda.exe in your Anaconda/Miniconda installation.'
    $conda = (Read-Host 'Conda path').Trim('"')
    if (-not (Test-Path -LiteralPath $conda -PathType Leaf)) { throw 'Conda not found. See MIGRATION.md.' }
}
Write-Host "Conda: $conda"
if (Test-Path -LiteralPath $marker) {
    $saved = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
    if ($saved.computer -ne $env:COMPUTERNAME -or $saved.folder -ne $PSScriptRoot) {
        throw 'This environment was moved. Extract the original migration ZIP into a NEW folder, then run START.cmd there.'
    }
}
if (-not (Test-Path -LiteralPath $marker)) {
    if ($CheckOnly) { throw 'Environment has not been installed yet.' }
    if (-not (Test-Path -LiteralPath (Join-Path $envDir 'python.exe'))) {
        Write-Host 'Creating a separate Python environment (internet required)...'
        & $conda create --prefix $envDir python=3.12 pip -y
        if ($LASTEXITCODE -ne 0) { throw 'Environment creation failed. Read the error above and retry.' }
    }
    & $conda run --prefix $envDir python -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Package installation failed. Check network and retry START.cmd.' }
}
& $conda run --prefix $envDir python -c $checkCode
if ($LASTEXITCODE -ne 0) { throw 'Environment check failed. See the error above.' }
@{computer=$env:COMPUTERNAME; folder=$PSScriptRoot} | ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding UTF8
if ($CheckOnly) { exit 0 }
Write-Host 'Starting battery monitor. Keep this console open while using the app.'
& $conda run --no-capture-output --prefix $envDir python (Join-Path $PSScriptRoot 'app.py')
if ($LASTEXITCODE -ne 0) { throw 'Application exited with an error. See the traceback above.' }
