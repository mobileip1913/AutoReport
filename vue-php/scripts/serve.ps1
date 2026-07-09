# 生产/演示：单端口 PHP（8091），Vue 已 build 在 public/app/
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"

if (-not (Test-Path (Join-Path $backend "public\app\index.html"))) {
  Write-Host "未找到 public/app/index.html，请先运行: .\scripts\install.ps1" -ForegroundColor Red
  exit 1
}

Write-Host "AutoReport Vue+PHP → http://127.0.0.1:8091/app/" -ForegroundColor Cyan
Push-Location $backend
php -S 0.0.0.0:8091 -t public
