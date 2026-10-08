param([string]$PackageDirectory = '', [string]$OutputDirectory = '', [string]$Compiler = '', [ValidateSet('beta','stable')][string]$Channel = 'beta')
$ErrorActionPreference = 'Stop'
$projectDirectory = Split-Path -Parent $PSScriptRoot
$appVersion = & (Join-Path $projectDirectory '.venv/Scripts/python.exe') -c 'from app.version import VERSION; print(VERSION)'
if ($appVersion -notmatch '^\d+\.\d+\.\d+$') { throw 'Installer needs a stable semantic version.' }
if (-not $PackageDirectory) { $PackageDirectory = "dist/windows-beta/GDLResearchHubBeta" }
if (-not $OutputDirectory) { $OutputDirectory = "dist/installer-$appVersion" }
$packageRoot = [IO.Path]::GetFullPath((Join-Path $projectDirectory $PackageDirectory))
$outputRoot = [IO.Path]::GetFullPath((Join-Path $projectDirectory $OutputDirectory))
$allowedRoot = [IO.Path]::GetFullPath((Join-Path $projectDirectory 'dist')) + [IO.Path]::DirectorySeparatorChar
if (-not $packageRoot.StartsWith($allowedRoot,[StringComparison]::OrdinalIgnoreCase) -or
    -not $outputRoot.StartsWith($allowedRoot,[StringComparison]::OrdinalIgnoreCase)) { throw 'Package and installer outputs must stay in project dist.' }
$edition = Get-Content -LiteralPath (Join-Path $packageRoot '_internal/config/edition.json') -Raw | ConvertFrom-Json
$metadata = Get-Content -LiteralPath (Join-Path $packageRoot '_internal/config/build_metadata.json') -Raw | ConvertFrom-Json
if ($edition.channel -ne $Channel -or $metadata.channel -ne $Channel) { throw 'Installer/package channel mismatch.' }
$exeName = if ($Channel -eq 'beta') { 'GDLResearchHubBeta' } else { 'FuelCellProjectHub' }
$assetName = if ($Channel -eq 'beta') { 'GDLResearchHubBeta-Setup.exe' } else { 'GDLResearchHub-Setup.exe' }
$displayVersion = $metadata.version
$numericVersion = if ($Channel -eq 'beta') { "$appVersion.$($edition.beta_sequence)" } else { "$appVersion.0" }
if (-not (Test-Path -LiteralPath (Join-Path $packageRoot "$exeName.exe"))) { throw 'Build the application package first.' }
if (-not $Compiler) {
    $candidate = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($candidate) { $Compiler = $candidate.Source }
    else { $Compiler = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe' }
}
& $Compiler "/DAppVersion=$displayVersion" "/DNumericVersion=$numericVersion" "/DChannel=$Channel" "/DPackageRoot=$packageRoot" "/DOutputRoot=$outputRoot" (Join-Path $PSScriptRoot 'GDLResearchHub.iss')
if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
$installer = Join-Path $outputRoot $assetName
if ($env:GDL_SIGNTOOL -and $env:GDL_SIGN_CERT_SHA1) {
    & $env:GDL_SIGNTOOL sign /sha1 $env:GDL_SIGN_CERT_SHA1 /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $installer
    if ($LASTEXITCODE -ne 0) { throw 'Installer signing failed.' }
}
$hash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText($installer + '.sha256', $hash + '  ' + $assetName + [Environment]::NewLine)
Write-Output "Installer and checksum created for $appVersion."
