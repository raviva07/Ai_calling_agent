$ErrorActionPreference = "Stop"

$envPath = Join-Path $PSScriptRoot "backend\.env"
$examplePath = Join-Path $PSScriptRoot "backend\.env.example"

if (-not (Test-Path $envPath)) {
    if (-not (Test-Path $examplePath)) { throw "backend\.env.example was not found." }
    Copy-Item $examplePath $envPath
}

Write-Host "Configure REAL receiver-phone calling (Twilio)" -ForegroundColor Cyan
Write-Host "Use a verified/consenting test recipient. Keep the Cloudflare HTTPS tunnel running." -ForegroundColor Yellow

$publicUrl = Read-Host "PUBLIC_BACKEND_URL (example https://abc.trycloudflare.com)"
$sid = Read-Host "TWILIO_ACCOUNT_SID (AC...)"
$from = Read-Host "TWILIO_FROM_NUMBER (E.164, example +12025550100)"
$secure = Read-Host "TWILIO_AUTH_TOKEN" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }

if (-not $publicUrl.StartsWith("https://")) { throw "Use the HTTPS URL printed by Cloudflare tunnel." }
if (-not $sid.StartsWith("AC")) { throw "Account SID should start with AC." }
if ([string]::IsNullOrWhiteSpace($token)) { throw "Auth token cannot be empty." }
if (-not $from.StartsWith("+")) { throw "From number must use E.164 format and start with +." }

$content = Get-Content $envPath -Raw
function Set-EnvValue([string]$name, [string]$value) {
    $script:content = $script:content -replace "(?m)^$([regex]::Escape($name))=.*$", "$name=$value"
    if ($script:content -notmatch "(?m)^$([regex]::Escape($name))=") {
        $script:content += "`r`n$name=$value`r`n"
    }
}

Set-EnvValue "PUBLIC_BACKEND_URL" $publicUrl.TrimEnd('/')
Set-EnvValue "TWILIO_ACCOUNT_SID" $sid
Set-EnvValue "TWILIO_AUTH_TOKEN" $token
Set-EnvValue "TWILIO_FROM_NUMBER" $from
Set-EnvValue "TWILIO_VOICE_MODE" "gather"
Set-EnvValue "TWILIO_VALIDATE_SIGNATURE" "true"

Set-Content -Path $envPath -Value $content -Encoding UTF8
Write-Host "Saved to backend\.env. Restart FastAPI, then check http://localhost:8000/api/telephony/config" -ForegroundColor Green
