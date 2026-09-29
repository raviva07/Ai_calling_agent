$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath = Join-Path $root 'backend\.env'
$examplePath = Join-Path $root 'backend\.env.example'

if (-not (Test-Path $envPath)) {
    Copy-Item $examplePath $envPath
}

Write-Host "Configuring OpenRouter for AI Calling Agent" -ForegroundColor Cyan
$secure = Read-Host "Paste your OpenRouter API key (input is hidden)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

if ([string]::IsNullOrWhiteSpace($key)) {
    throw "No API key entered. Nothing was changed."
}

$content = Get-Content $envPath -Raw
if ($content -match '(?m)^OPENROUTER_API_KEY=.*$') {
    $content = [regex]::Replace($content, '(?m)^OPENROUTER_API_KEY=.*$', "OPENROUTER_API_KEY=$key")
} else {
    $content += "`r`nOPENROUTER_API_KEY=$key`r`n"
}
$content = [regex]::Replace($content, '(?m)^LLM_PROVIDER=.*$', 'LLM_PROVIDER=openrouter')
$content = [regex]::Replace($content, '(?m)^OPENROUTER_MODEL=.*$', 'OPENROUTER_MODEL=openrouter/free')
Set-Content -Path $envPath -Value $content -Encoding UTF8
$key = $null
Write-Host "Saved securely to backend\.env (ignored by Git). Model: openrouter/free" -ForegroundColor Green
Write-Host "Do not commit backend\.env." -ForegroundColor Yellow
