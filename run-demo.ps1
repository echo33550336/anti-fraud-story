# 一键启动本地 Demo（后端同时托管前端）
# 用法：powershell -ExecutionPolicy Bypass -File .\run-demo.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$env:HOST = "127.0.0.1"
$env:PORT = "5000"
$env:ALLOW_PUBLIC = "1"
Write-Host "打开 http://127.0.0.1:5000/"
Set-Location $backend
python app.py
