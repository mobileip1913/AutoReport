# 停止 8081 上所有 uvicorn / reload 子进程，并启动单一服务实例
$ErrorActionPreference = 'SilentlyContinue'
Set-Location $PSScriptRoot

Write-Host "正在清理 8081 端口..."

# 按端口杀监听进程
Get-NetTCPConnection -LocalPort 8081 -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique |
    ForEach-Object { Stop-Process -Id $_ -Force }

# 杀 uvicorn --reload 残留的 multiprocessing 子进程
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'uvicorn.*8081|spawn_main\(parent_pid=(12008|19184|10404|21380|25080)' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Start-Sleep -Seconds 2

if (Get-NetTCPConnection -LocalPort 8081 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "警告：8081 仍被占用，请手动结束相关 python 进程后重试。" -ForegroundColor Yellow
    netstat -ano | findstr ":8081"
    exit 1
}

Write-Host "启动服务 http://0.0.0.0:8081 ..."
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8081
