# 开发环境：PHP 8091 + Vite 5173
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

if (-not (Test-Path (Join-Path $backend "vendor\autoload.php"))) {
  Write-Host "[dev] composer install..."
  Push-Location $backend; composer install; Pop-Location
}

Write-Host "[dev] PHP API http://127.0.0.1:8091"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backend'; php -S 0.0.0.0:8091 -t public"

Start-Sleep -Seconds 1
Write-Host "[dev] Vue http://127.0.0.1:5173"
Push-Location $frontend
npm run dev
