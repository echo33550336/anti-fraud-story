@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
if "%PORT%"=="" set PORT=5000
cd /d "%~dp0"
if exist "backend\app.py" cd /d "%~dp0backend"
if not exist "app.py" (
  echo [ERROR] 未找到 app.py：请把 start.bat 放在 MIX-V5 根目录或 backend 目录下。
  pause
  exit /b 1
)
echo ============================================
echo  反诈陪练 Demo 启动中...
echo  访问地址: http://127.0.0.1:%PORT%
echo  关闭窗口或按 Ctrl+C 停止服务
echo ============================================
python app.py
if errorlevel 1 (
  echo.
  echo [ERROR] 启动失败。请确认已安装 Python 3.8+ 并加入 PATH。
  pause
)
