param([Parameter(Mandatory=$true)][string]$KeyDirectory)
$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$directory = [IO.Path]::GetFullPath($KeyDirectory)
if ($directory.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or $directory -eq $workspace) {
    throw 'Store the private signing key outside the repository and its build artifacts.'
}
$key = Join-Path $directory 'runepilot-update.key'
if ((Test-Path -LiteralPath $key) -or (Test-Path -LiteralPath "$key.pub")) {
    throw 'A signing key already exists. Keep it; never rotate an installed update identity accidentally.'
}
New-Item -ItemType Directory -Force -Path $directory | Out-Null
Push-Location (Join-Path $workspace 'frontend')
try {
    # The CLI prompts for a password; private key contents are never printed here.
    & npx.cmd tauri signer generate --write-keys $key
    if ($LASTEXITCODE -ne 0) { throw 'Signing key generation failed.' }
} finally { Pop-Location }
Write-Host 'Back up the private key and password separately. Configure GitHub Actions secrets TAURI_SIGNING_PRIVATE_KEY and TAURI_SIGNING_PRIVATE_KEY_PASSWORD, and repository variable RUNEPILOT_UPDATE_PUBLIC_KEY from the .pub file.'
