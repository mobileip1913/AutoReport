# 独立启动 Vue+PHP 工程后端（8091）
$Root = Split-Path -Parent $PSScriptRoot
$port = 8091

Get-CimInstance Win32_Process -Filter "Name='php.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match ":$port" -and $_.CommandLine -match '-S' } |
  ForEach-Object {
    Write-Host "[serve] stop pid $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }

Start-Sleep -Seconds 1
$php = (Get-Command php -ErrorAction Stop).Source
Write-Host "[serve] cwd  $Root"
Start-Process -FilePath $php `
  -ArgumentList @('-S', "0.0.0.0:$port", '-t', 'public') `
  -WorkingDirectory $Root `
  -WindowStyle Hidden

Start-Sleep -Seconds 1
try {
  Write-Host "[serve] OK $((Invoke-WebRequest -Uri "http://127.0.0.1:$port/" -UseBasicParsing -TimeoutSec 5).StatusCode) — http://127.0.0.1:$port/"
} catch {
  Write-Host "[serve] WARN: $($_.Exception.Message)"
}
