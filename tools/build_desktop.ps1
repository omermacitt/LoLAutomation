param(
    [string]$Python = '.venv\Scripts\python.exe',
    [switch]$SignedUpdates
)
$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $workspace
if (!(Test-Path -LiteralPath $Python)) { throw 'Install Python build requirements first.' }
$Python = (Resolve-Path -LiteralPath $Python).Path
$env:PATH = (Join-Path $env:USERPROFILE '.cargo\bin') + ';' + $env:PATH
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed ($LASTEXITCODE)" }
}
Invoke-Checked $Python @('tools/release_version.py')
$version = (& $Python tools/release_version.py --print).Trim()
if ($SignedUpdates -and (!$env:TAURI_SIGNING_PRIVATE_KEY -or !$env:RUNEPILOT_UPDATE_PUBLIC_KEY)) {
    throw 'Signed updates require TAURI_SIGNING_PRIVATE_KEY and RUNEPILOT_UPDATE_PUBLIC_KEY.'
}
if (!$SignedUpdates) { Remove-Item Env:RUNEPILOT_UPDATE_PUBLIC_KEY -ErrorAction SilentlyContinue }
Invoke-Checked $Python @('-m', 'PyInstaller', '--clean', '-y', '--distpath', 'build/desktop/backend', '--workpath', 'build/desktop/pyinstaller', 'backend.spec')
Invoke-Checked $Python @('tools/smoke_backend.py', 'build/desktop/backend/runepilot-backend.exe')
$binaryDir = Join-Path $workspace 'frontend/src-tauri/binaries'
New-Item -ItemType Directory -Force -Path $binaryDir | Out-Null
Copy-Item -LiteralPath 'build/desktop/backend/runepilot-backend.exe' -Destination (Join-Path $binaryDir 'runepilot-backend-x86_64-pc-windows-msvc.exe') -Force
Push-Location frontend
try {
    $arguments = @('tauri', 'build', '--bundles', 'nsis')
    if ($SignedUpdates) {
        $override = Join-Path $workspace 'build/desktop/update-build.json'
        $updateConfig = @{ bundle = @{ createUpdaterArtifacts = $true }; plugins = @{ updater = @{ pubkey = $env:RUNEPILOT_UPDATE_PUBLIC_KEY.Trim(); requireSignedVersion = $true; windows = @{ installMode = 'passive' } } } }
        [IO.File]::WriteAllText($override, ($updateConfig | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
        $arguments += @('--config', $override)
    }
    $arguments += @('--', '--locked')
    Invoke-Checked 'npx.cmd' $arguments
}
finally { Pop-Location }
$installer = Join-Path $workspace "frontend/src-tauri/target/release/bundle/nsis/RunePilot_${version}_x64-setup.exe"
if (!(Test-Path -LiteralPath $installer)) { throw "Expected installer missing: $installer" }
if ($SignedUpdates) {
    $env:RUNEPILOT_VERIFY_SETUP = $installer
    $env:RUNEPILOT_VERIFY_VERSION = $version
    try {
        Invoke-Checked 'cargo' @('test', '--locked', '--manifest-path', 'frontend/src-tauri/Cargo.toml', '--test', 'update_signature', 'verify_built_installer', '--', '--ignored')
    } finally {
        Remove-Item Env:RUNEPILOT_VERIFY_SETUP,Env:RUNEPILOT_VERIFY_VERSION -ErrorAction SilentlyContinue
    }
}
$output = Join-Path $workspace "dist/desktop/$version"
New-Item -ItemType Directory -Force -Path $output | Out-Null
$name = "RunePilotSetup-$version-x64.exe"
$target = Join-Path $output $name
# A local unsigned rebuild must never retain a previous build's signed feed.
foreach ($stale in @("$target.sig", (Join-Path $output 'latest.json'))) {
    if (Test-Path -LiteralPath $stale) { Remove-Item -LiteralPath $stale }
}
Copy-Item -LiteralPath $installer -Destination $target -Force
if ($SignedUpdates) {
    Copy-Item -LiteralPath "$installer.sig" -Destination "$target.sig" -Force
    Invoke-Checked $Python @('tools/release_updates.py', $output, '--version', $version)
}
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
"$hash  $name" | Set-Content -Encoding ascii -LiteralPath (Join-Path $output 'SHA256SUMS.txt')
$commit = (& git rev-parse HEAD).Trim()
$dirty = [bool](& git status --porcelain)
[ordered]@{version=$version; commit=$commit; dirty=$dirty; platform='windows-x86_64'; artifact=$name; sha256=$hash} | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath (Join-Path $output 'build-manifest.json')
Write-Host "Setup ready: $target"
