param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [ValidateSet('beta','stable')][string]$Channel,
    [string]$PreviousPackage = '',
    [string]$Report = '.test-state/installer-acceptance.json'
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force (Split-Path -Parent ([IO.Path]::GetFullPath($Report))) | Out-Null
$installerPath = (Resolve-Path -LiteralPath $Installer).Path
$checksum = ((Get-Content -LiteralPath ($installerPath + '.sha256') -Raw).Trim() -split '\s+')[0]
if ((Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash -ine $checksum) { throw 'Installer checksum mismatch' }
$testRoot = Join-Path $env:TEMP ('gdl-installer-tests/' + [guid]::NewGuid())
New-Item -ItemType Directory -Force $testRoot | Out-Null
$exe = if ($Channel -eq 'beta') { 'GDLResearchHubBeta.exe' } else { 'FuelCellProjectHub.exe' }
$env:QT_QPA_PLATFORM = 'offscreen'
$results = @()
$registryPaths = @('HKCU:\Software\Classes\gdlresearchhub','HKCU:\Software\Classes\gdlresearchhubbeta',
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{ACAC162E-8C9A-4F0B-998F-710038B7C32D}_is1',
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{9DC7B6A1-418F-4CD4-BAB0-A7D96E5189B6}_is1')
function RegistrySnapshot {
    foreach ($path in $registryPaths) {
        if (Test-Path -LiteralPath $path) {
            Get-ItemProperty -LiteralPath $path | ConvertTo-Json -Compress
            Get-ChildItem -LiteralPath $path -Recurse | ForEach-Object { Get-ItemProperty -LiteralPath $_.PSPath | ConvertTo-Json -Compress }
        }
    }
}
$registryBefore = @(RegistrySnapshot) | ConvertTo-Json -Compress
foreach ($scenario in @('fresh', 'upgrade')) {
    $destination = Join-Path $testRoot $scenario
    New-Item -ItemType Directory -Force $destination | Out-Null
    if ($scenario -eq 'upgrade') {
        $source = if ($PreviousPackage) { (Resolve-Path -LiteralPath $PreviousPackage).Path } else { Join-Path $testRoot 'fresh' }
        Copy-Item -Path (Join-Path $source '*') -Destination $destination -Recurse
    }
    # These sentinel files represent existing local settings/session/index bytes.
    # Startup self-check uses its own isolated fixture, never the real user profile.
    $preserved = Join-Path $destination 'preservation-fixture'
    New-Item -ItemType Directory -Force $preserved | Out-Null
    foreach ($name in @('settings.json','encrypted-session.bin','research.sqlite3','research.txt')) {
        [IO.File]::WriteAllText((Join-Path $preserved $name), 'preserve-' + $name)
    }
    $before = @(Get-ChildItem -LiteralPath $preserved | Get-FileHash -Algorithm SHA256 | Select-Object Hash)
    $log = Join-Path $testRoot ($scenario + '-install.log')
    $args = @('/VERYSILENT','/SUPPRESSMSGBOXES','/SP-','/NORESTART','/NOCLOSEAPPLICATIONS','/NORESTARTAPPLICATIONS','/GDLTESTINSTALL=1',('/DIR="'+$destination+'"'),('/LOG="'+$log+'"'))
    $process = Start-Process -FilePath $installerPath -ArgumentList $args -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) { throw "Installer $scenario failed: $($process.ExitCode). See $log" }
    $after = @(Get-ChildItem -LiteralPath $preserved | Get-FileHash -Algorithm SHA256 | Select-Object Hash)
    if (($before | ConvertTo-Json -Compress) -cne ($after | ConvertTo-Json -Compress)) { throw 'Preservation fixture changed' }
    $check = Join-Path $testRoot ($scenario + '-startup.json')
    $process = Start-Process -FilePath (Join-Path $destination $exe) -ArgumentList @('--self-check',('"'+$check+'"'),'--local-only') -Wait -PassThru -WindowStyle Hidden
    if ($process.ExitCode -ne 0) { throw "Installed app startup failed: $($process.ExitCode)" }
    $startup = Get-Content -LiteralPath $check -Raw | ConvertFrom-Json
    if (-not $startup.startup -or $startup.channel -ne $Channel) { throw 'Installed edition/startup mismatch' }
    $installerVersion = [Diagnostics.FileVersionInfo]::GetVersionInfo($installerPath)
    $numeric = ($startup.version -replace '-beta\.', '.')
    if ($Channel -eq 'stable') { $numeric += '.0' }
    $resourceVersion = "$($installerVersion.FileMajorPart).$($installerVersion.FileMinorPart).$($installerVersion.FileBuildPart).$($installerVersion.FilePrivatePart)"
    if ($resourceVersion -ne $numeric) { throw 'Installer/application version mismatch' }
    $results += @{scenario=$scenario;exit_code=0;channel=$Channel;version=$startup.version;preserved=$true;test_directory=$destination}
}
if ($registryBefore -cne (@(RegistrySnapshot) | ConvertTo-Json -Compress)) { throw 'Disposable installation altered real application registration' }
@{results=$results;installer_sha256=$checksum;registry_and_shortcuts_disabled=$true} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Report
Write-Output "Disposable $Channel fresh installation and upgrade passed; report: $Report"
