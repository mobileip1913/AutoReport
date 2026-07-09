# Vue+PHP 独立套件 — 一键安装（Windows）
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

Write-Host "=== AutoReport Vue+PHP 安装 ===" -ForegroundColor Cyan

if (-not (Test-Path (Join-Path $backend ".env"))) {
  Copy-Item (Join-Path $backend ".env.example") (Join-Path $backend ".env")
  Write-Host "[ok] 已创建 backend/.env，请按需填写 MySQL" -ForegroundColor Yellow
}

Push-Location $backend
if (-not (Test-Path "vendor\autoload.php")) {
  Write-Host "[..] composer install"
  composer install --no-interaction
}
Write-Host "[..] php bin/init.php"
php bin/init.php
Pop-Location

Push-Location $frontend
if (-not (Test-Path "node_modules")) {
  Write-Host "[..] npm install"
  npm install
}
Write-Host "[..] npm run build → backend/public/app/"
npm run build
Pop-Location

Write-Host ""
Write-Host "安装完成。启动：" -ForegroundColor Green
Write-Host "  生产单端口: .\scripts\serve.ps1  →  http://127.0.0.1:8091/app/"
Write-Host "  开发双进程: .\scripts\dev.ps1     →  5173 + 8091"
