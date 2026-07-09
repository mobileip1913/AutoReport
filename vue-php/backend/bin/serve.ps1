# 以独立进程启动 Twig 版 PHP（8090），不绑定 Cursor 后台终端
$Root = Split-Path -Parent $PSScriptRoot
$port = 8090

Get-CimInstance Win32_Process -Filter "Name='php.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -match ":$port" -and $_.CommandLine -match '-S' } |
  ForEach-Object {
    Write-Host "[serve] stop pid $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }

Start-Sleep -Seconds 1
$php = (Get-Command php -ErrorAction Stop).Source
Write-Host "[serve] cwd  $Root"
Write-Host "[serve] start $php -S 0.0.0.0:$port -t public"

Start-Process -FilePath $php `
  -ArgumentList @('-S', "0.0.0.0:$port", '-t', 'public') `
  -WorkingDirectory $Root `
  -WindowStyle Hidden

Start-Sleep -Seconds 1
try {
  $code = (Invoke-WebRequest -Uri "http://127.0.0.1:$port/" -UseBasicParsing -TimeoutSec 5).StatusCode
  Write-Host "[serve] OK $code — http://127.0.0.1:$port/"
} catch {
  Write-Host "[serve] WARN: $($_.Exception.Message)"
}
