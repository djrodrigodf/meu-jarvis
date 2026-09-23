param(
    [ValidateSet('chat', 'voice', 'tools', 'ask', 'data')]
    [string]$Mode = 'chat',
    [string[]]$JarvisArguments = @()
)

$jarvisHome = Join-Path $env:LOCALAPPDATA 'Jarvis'
$executable = Join-Path $jarvisHome 'venv\Scripts\jarvis.exe'
$environmentFile = Join-Path $jarvisHome 'infra.env'

if (-not (Test-Path -LiteralPath $executable)) {
    throw "JARVIS não está instalado em $executable. Consulte o README.md."
}

if (Test-Path -LiteralPath $environmentFile) {
    $allowed = @(
        'JARVIS_DATABASE_URL',
        'JARVIS_REDIS_URL',
        'JARVIS_OPENSEARCH_URL'
    )
    foreach ($line in Get-Content -LiteralPath $environmentFile) {
        if ($line -match '^\s*(JARVIS_[A-Z_]+)=(.*)$' -and $allowed -contains $Matches[1]) {
            [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
        }
    }
}

& $executable $Mode @JarvisArguments
exit $LASTEXITCODE
