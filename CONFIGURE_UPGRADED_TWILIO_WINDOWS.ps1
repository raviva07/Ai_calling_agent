$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath = Join-Path $root 'backend\.env'

if (-not (Test-Path $envPath)) {
  Write-Host "backend\.env not found. Create it from backend\.env.example first." -ForegroundColor Red
  exit 1
}

$sid = Read-Host "Upgraded Twilio Account SID (AC...)"
$token = Read-Host "Upgraded Twilio Auth Token" -AsSecureString
$tokenPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($token))
$from = Read-Host "Twilio Voice From Number (+...)"
$public = Read-Host "Public HTTPS backend URL (https://...)"

if ($public -notmatch '^https://') { throw 'PUBLIC_BACKEND_URL must start with https://' }

$content = Get-Content $envPath -Raw
$replacements = @{
  'TWILIO_ACCOUNT_SID' = $sid
  'TWILIO_AUTH_TOKEN' = $tokenPlain
  'TWILIO_FROM_NUMBER' = $from
  'TWILIO_ACCOUNT_TIER' = 'upgraded'
  'CALLING_PROVIDER' = 'twilio'
  'PUBLIC_BACKEND_URL' = $public.TrimEnd('/')
}

foreach ($key in $replacements.Keys) {
  $value = [string]$replacements[$key]
  $pattern = "(?m)^$key=.*$"
  if ($content -match $pattern) {
    $content = [regex]::Replace($content, $pattern, "$key=$value")
  } else {
    $content += "`r`n$key=$value`r`n"
  }
}

Set-Content -Path $envPath -Value $content -Encoding UTF8
Write-Host "Updated upgraded Twilio configuration in backend\.env" -ForegroundColor Green
