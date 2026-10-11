param([ValidateSet('member', 'admin')][string]$Role = 'member')
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $appRoot '.venv/Scripts/pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Use the existing development Python environment first.' }
$archivePath = Join-Path $env:USERPROFILE 'Downloads/skills-main.zip'
if (-not (Test-Path -LiteralPath $archivePath)) { throw 'Place the verified skills-main.zip in Downloads first.' }
Start-Process -FilePath $pythonPath -WorkingDirectory $appRoot -ArgumentList @('-m', 'tools.ui_prototypes.run', '--role', $Role) -WindowStyle Hidden
Write-Output 'Opened the isolated Home picker. Use 1/2/3 or arrow keys outside text fields. No layout is integrated until owner selection.'
