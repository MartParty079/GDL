param([string]$OutputDirectory = 'dist/windows-beta', [ValidateSet('beta','stable')][string]$Channel = 'beta', [string]$ApprovalFile = '', [int]$BetaSequence = 0)
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
    $policyArgs = @('tools/release_policy.py','--channel',$Channel)
    if ($ApprovalFile) { $policyArgs += @('--approval-file',$ApprovalFile) }
    & $appPython @policyArgs
    if ($LASTEXITCODE -ne 0) { throw 'Release approval policy failed.' }
    $env:GDL_BUILD_CHANNEL = $Channel
    if ($ApprovalFile) { $env:GDL_PRODUCTION_APPROVAL_FILE = [IO.Path]::GetFullPath($ApprovalFile) }
    if ($BetaSequence -gt 0) { $env:GDL_BETA_SEQUENCE = "$BetaSequence" }
    & $appPython -m PyInstaller --noconfirm --distpath $buildDestination --workpath build tools/FuelCellProjectHub.spec
    if ($LASTEXITCODE -ne 0) { throw 'Windows build failed.' }
    if ($env:GDL_SIGNTOOL -and $env:GDL_SIGN_CERT_SHA1) {
        $exeName = if ($Channel -eq 'beta') { 'GDLResearchHubBeta' } else { 'FuelCellProjectHub' }
        & $env:GDL_SIGNTOOL sign /sha1 $env:GDL_SIGN_CERT_SHA1 /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 (Join-Path $buildDestination "$exeName/$exeName.exe")
        if ($LASTEXITCODE -ne 0) { throw 'Application signing failed.' }
    }
} finally {
    Remove-Item Env:GDL_BUILD_CHANNEL -ErrorAction SilentlyContinue
    Remove-Item Env:GDL_BETA_SEQUENCE -ErrorAction SilentlyContinue
    Remove-Item Env:GDL_PRODUCTION_APPROVAL_FILE -ErrorAction SilentlyContinue
    Pop-Location
}
