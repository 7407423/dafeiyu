@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ================================================
echo   大肥鱼 · 启动器
echo ================================================

rem 优先 Python 3.10-3.12：PySide6 目前没有 3.13/3.14 的 wheel。
rem 直接用 py -3 时，新机器上常拿到 3.14，pip 装 PySide6 直接失败 —— 这是"谁都装不起来"的根因之一。
set PY=
for %%v in (3.12 3.11 3.10) do (
  if not defined PY (
    py -%%v --version >nul 2>nul
    if not errorlevel 1 set PY=py -%%v
  )
)
if not defined PY (
  set PY=py -3
  %PY% -c "import sys; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,12) else 1)" >nul 2>nul
  if errorlevel 1 (
    echo [x] 没找到 Python 3.10 - 3.12（当前 py -3 版本太新或太旧）。
    echo     PySide6 还没有 3.13/3.14 的安装包，请装 Python 3.12：
    echo     https://www.python.org/downloads/release/python-3129/
    pause
    exit /b 1
  )
)

if not exist ".venv\Scripts\pythonw.exe" (
  echo [1/3] 创建虚拟环境 .venv ...
  %PY% -m venv .venv || (echo [x] 创建虚拟环境失败 & pause & exit /b 1)
)

echo [2/3] 安装依赖（第一次会慢一点）...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [x] 依赖安装失败。先确认 Python 是 3.12，再试国内镜像：
  echo     .venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
  pause
  exit /b 1
)

echo [3/3] 启动大肥鱼（首次会弹出「初次见面」设定窗口）...
start "" ".venv\Scripts\pythonw.exe" run.py
exit /b 0
