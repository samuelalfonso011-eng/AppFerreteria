# Carga en Vercel (entorno Production) las variables que necesita el backend Flask (api/index.py).
# Lee los valores de backend\.env sin mostrarlos y genera una SECRET_KEY nueva para producción.
# Uso, desde la raíz del proyecto (con `vercel login` hecho y el proyecto vinculado):
#   powershell -ExecutionPolicy Bypass -File scripts\vercel-env.ps1
$ErrorActionPreference = "Stop"
$EnvFile = Join-Path $PSScriptRoot "..\backend\.env"
$Domain = "appferreteria.vercel.app"

if (-not (Test-Path $EnvFile)) { throw "No existe backend\.env" }
$values = @{}
foreach ($line in Get-Content -LiteralPath $EnvFile -Encoding UTF8) {
    if ($line -match '^\s*([A-Z_][A-Z0-9_]*)\s*=(.*)$') { $values[$Matches[1]] = $Matches[2].Trim() }
}

# Copiadas de backend\.env (la conexión ya usa el Session pooler de Supabase, que funciona por IPv4)
$copy = "DATABASE_URL", "SMTP_HOST", "SMTP_PORT", "SMTP_STARTTLS", "SMTP_USER", "SMTP_FROM", "SMTP_FROM_NAME",
        "SMTP_PASSWORD", "GEMINI_API_KEY", "GEMINI_MODEL", "CACHE_TTL", "ORDER_PENDING_EXPIRY_MINUTES"
$secret = "DATABASE_URL", "SECRET_KEY", "SMTP_PASSWORD", "GEMINI_API_KEY"

$bytes = New-Object byte[] 32
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$set = [ordered]@{
    FLASK_ENV          = "production"
    SECRET_KEY         = -join ($bytes | ForEach-Object { $_.ToString("x2") })
    TRUSTED_HOSTS      = "$Domain,appferreteria-samuelalfonso011-eng.vercel.app,appferreteria-git-main-samuelalfonso011-eng.vercel.app"
    TRUSTED_PROXY_HOPS = "1"
    PUBLIC_BASE_URL    = "https://$Domain"
}
foreach ($name in $copy) {
    if ($values.ContainsKey($name) -and $values[$name] -ne "") { $set[$name] = $values[$name] }
}
if (-not $set.Contains("DATABASE_URL")) { throw "backend\.env no tiene DATABASE_URL" }

foreach ($name in $set.Keys) {
    $kind = if ($secret -contains $name) { "--sensitive" } else { "--no-sensitive" }
    & vercel env add $name --environment production --value $set[$name] $kind --force --yes *> $null
    if ($LASTEXITCODE -ne 0) { throw "No se pudo cargar $name (revisa vercel login y el proyecto vinculado)" }
    Write-Host "Cargada: $name"
}
Write-Host "Listo: $($set.Count) variables en Production. Vuelve a desplegar para que se apliquen."
