param(
    [string]$Python = '.venv\Scripts\python.exe'
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
Invoke-Checked $Python @('-m', 'PyInstaller', '--clean', '-y', '--distpath', 'build/desktop/backend', '--workpath', 'build/desktop/pyinstaller', 'backend.spec')
Invoke-Checked $Python @('tools/smoke_backend.py', 'build/desktop/backend/runepilot-backend.exe')
$binaryDir = Join-Path $workspace 'frontend/src-tauri/binaries'
New-Item -ItemType Directory -Force -Path $binaryDir | Out-Null
Copy-Item -LiteralPath 'build/desktop/backend/runepilot-backend.exe' -Destination (Join-Path $binaryDir 'runepilot-backend-x86_64-pc-windows-msvc.exe') -Force
Push-Location frontend
try { Invoke-Checked 'npx.cmd' @('tauri', 'build', '--bundles', 'nsis', '--', '--locked') }
finally { Pop-Location }
$installer = Join-Path $workspace "frontend/src-tauri/target/release/bundle/nsis/RunePilot_${version}_x64-setup.exe"
if (!(Test-Path -LiteralPath $installer)) { throw "Expected installer missing: $installer" }
$output = Join-Path $workspace "dist/desktop/$version"
New-Item -ItemType Directory -Force -Path $output | Out-Null
$name = "RunePilotSetup-$version-x64.exe"
$target = Join-Path $output $name
Copy-Item -LiteralPath $installer -Destination $target -Force
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
"$hash  $name" | Set-Content -Encoding ascii -LiteralPath (Join-Path $output 'SHA256SUMS.txt')
$commit = (& git rev-parse HEAD).Trim()
$dirty = [bool](& git status --porcelain)
[ordered]@{version=$version; commit=$commit; dirty=$dirty; platform='windows-x86_64'; artifact=$name; sha256=$hash} | ConvertTo-Json | Set-Content -Encoding utf8 -LiteralPath (Join-Path $output 'build-manifest.json')
Write-Host "Setup ready: $target"
