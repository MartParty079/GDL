param([string]$OutputDirectory = 'dist/windows-branded')
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$appPython = Join-Path $projectDirectory '.venv\Scripts\python.exe'
$buildDestination = [IO.Path]::GetFullPath((Join-Path $projectDirectory $OutputDirectory))
$distRoot = [IO.Path]::GetFullPath((Join-Path $projectDirectory 'dist')) + [IO.Path]::DirectorySeparatorChar
if (-not $buildDestination.StartsWith($distRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Build output must stay inside this project dist folder.'
}
Push-Location -LiteralPath $projectDirectory
try {
    & $appPython -m PyInstaller --noconfirm --distpath $buildDestination --workpath build tools/FuelCellProjectHub.spec
    if ($LASTEXITCODE -ne 0) { throw 'Windows build failed.' }
    if ($env:GDL_SIGNTOOL -and $env:GDL_SIGN_CERT_SHA1) {
        & $env:GDL_SIGNTOOL sign /sha1 $env:GDL_SIGN_CERT_SHA1 /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 (Join-Path $buildDestination 'FuelCellProjectHub/FuelCellProjectHub.exe')
        if ($LASTEXITCODE -ne 0) { throw 'Application signing failed.' }
    }
} finally {
    Pop-Location
}
