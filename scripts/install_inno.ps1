# Install a pinned compiler from the official Inno Setup release.
# Verification: https://jrsoftware.org/isdl-verify.php
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$toolRoot = Join-Path $PSScriptRoot '..\build\tools'
$toolRoot = [System.IO.Path]::GetFullPath($toolRoot)
New-Item -ItemType Directory -Path $toolRoot -Force | Out-Null
$installer = Join-Path $toolRoot 'innosetup-6.7.3.exe'
$compilerDirectory = Join-Path $toolRoot 'inno-6.7.3'
$downloadUrl = 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe'
Invoke-WebRequest -Uri $downloadUrl -OutFile $installer

$signature = Get-AuthenticodeSignature -LiteralPath $installer
if ($signature.Status -ne 'Valid' -or $null -eq $signature.SignerCertificate -or
    $signature.SignerCertificate.Subject -notmatch '(^|,\s*)CN=Pyrsys B\.V\.(,|$)') {
    throw 'Official Inno Setup installer signature validation failed.'
}

$arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/CURRENTUSER',
               ('/DIR="' + $compilerDirectory + '"'))
$process = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru -WindowStyle Hidden
if ($process.ExitCode -ne 0) {
    throw "Inno Setup installation failed with exit code $($process.ExitCode)."
}
$compiler = Join-Path $compilerDirectory 'ISCC.exe'
if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
    throw 'Inno Setup installation did not produce ISCC.exe.'
}
$env:ISCC = $compiler
if ($env:GITHUB_ENV) {
    Add-Content -LiteralPath $env:GITHUB_ENV -Value ('ISCC=' + $compiler) -Encoding utf8
}
Write-Host 'Verified Inno Setup 6.7.3 compiler is ready.'
