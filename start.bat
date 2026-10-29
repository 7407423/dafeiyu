@echo off

chcp 65001 >nul

setlocal

cd /d "%~dp0"



echo ================================================

echo   大肥鱼 · 启动器

echo ================================================



where py >nul 2>nul

if %errorlevel%==0 (set PY=py -3) else (set PY=python)



%PY% -c "import sys" >nul 2>nul

if errorlevel 1 (

  echo [x] 没找到 Python。请先装 Python 3.10+（安装时勾选 Add to PATH）：

  echo     https://www.python.org/downloads/

  pause

  exit /b 1

)



if not exist ".venv\Scripts\pythonw.exe" (

  echo [1/3] 创建虚拟环境 .venv ...

  %PY% -m venv .venv || (echo [x] 创建虚拟环境失败 & pause & exit /b 1)

)



echo [2/3] 安装依赖（第一次会慢一点）...

".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>nul

".venv\Scripts\python.exe" -m pip install -r requirements.txt

if errorlevel 1 (

  echo [x] 依赖安装失败。如果是网络问题，可加国内镜像重试：

  echo     .venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

  pause

  exit /b 1

)



echo [3/3] 启动大肥鱼（首次会弹出「初次见面」设定窗口）...

start "" ".venv\Scripts\pythonw.exe" run.py

exit /b 0

