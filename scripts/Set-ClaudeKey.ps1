$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security

$jarvisHome = Join-Path $env:LOCALAPPDATA 'Jarvis'
$secretPath = Join-Path $jarvisHome 'anthropic.key.dpapi'
New-Item -ItemType Directory -Path $jarvisHome -Force | Out-Null

$secure = Read-Host 'Cole a chave Claude API' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    if (-not $plain.StartsWith('sk-ant-')) {
        throw 'A chave Claude API parece inválida.'
    }
    $bytes = [Text.Encoding]::UTF8.GetBytes($plain)
    try {
        $encrypted = [Security.Cryptography.ProtectedData]::Protect(
            $bytes,
            $null,
            [Security.Cryptography.DataProtectionScope]::CurrentUser
        )
        [IO.File]::WriteAllBytes($secretPath, $encrypted)
    } finally {
        [Array]::Clear($bytes, 0, $bytes.Length)
    }
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
}

Write-Output "Chave Claude armazenada para o usuário atual do Windows."
