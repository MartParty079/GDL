param([string]$PackageDirectory = 'dist/windows-gdl-hub-0.3.0/FuelCellProjectHub',
      [string]$OutputDirectory = 'dist/installer-0.3.0', [string]$Compiler = '')
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$packageRoot = [IO.Path]::GetFullPath((Join-Path $projectDirectory $PackageDirectory))
$outputRoot = [IO.Path]::GetFullPath((Join-Path $projectDirectory $OutputDirectory))
$allowedRoot = [IO.Path]::GetFullPath((Join-Path $projectDirectory 'dist')) + [IO.Path]::DirectorySeparatorChar
if (-not $packageRoot.StartsWith($allowedRoot,[StringComparison]::OrdinalIgnoreCase) -or
    -not $outputRoot.StartsWith($allowedRoot,[StringComparison]::OrdinalIgnoreCase)) { throw 'Package and installer outputs must stay in project dist.' }
if (-not (Test-Path -LiteralPath (Join-Path $packageRoot 'FuelCellProjectHub.exe'))) { throw 'Build the application package first.' }
if (-not $Compiler) {
    $candidate = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($candidate) { $Compiler = $candidate.Source }
    else { $Compiler = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe' }
}
$appVersion = & (Join-Path $projectDirectory '.venv/Scripts/python.exe') -c 'from app.version import VERSION; print(VERSION)'
if ($appVersion -notmatch '^\d+\.\d+\.\d+$') { throw 'Installer needs a stable semantic version.' }
& $Compiler "/DAppVersion=$appVersion" "/DPackageRoot=$packageRoot" "/DOutputRoot=$outputRoot" (Join-Path $PSScriptRoot 'GDLResearchHub.iss')
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
$installer = Join-Path $outputRoot 'GDLResearchHub-Setup.exe'
if ($env:GDL_SIGNTOOL -and $env:GDL_SIGN_CERT_SHA1) {
    & $env:GDL_SIGNTOOL sign /sha1 $env:GDL_SIGN_CERT_SHA1 /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $installer
    if ($LASTEXITCODE -ne 0) { throw 'Installer signing failed.' }
}
$hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText($installer + '.sha256', $hash + '  GDLResearchHub-Setup.exe' + [Environment]::NewLine)
Write-Output "Installer and checksum created for $appVersion."
