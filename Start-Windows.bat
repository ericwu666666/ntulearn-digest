@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 双击运行：第一次自动安装，然后弹出浏览器窗口让你登录 NTULearn，最后打开看板。
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY goto nopython
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul || goto nopython
if not exist ".venv\Scripts\ntulearn.exe" (
  echo 第一次运行，正在安装，大约需要半分钟……
  %PY% -m venv .venv || goto failed
  ".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -e . || goto failed
)
if "%~1"=="" (
  ".venv\Scripts\ntulearn.exe" go
) else (
  ".venv\Scripts\ntulearn.exe" %*
)
echo.
pause
exit /b 0

:nopython
echo 需要 Python 3.9 或更新版本：https://www.python.org/downloads/
echo 安装时记得勾选 Add python.exe to PATH。
pause
exit /b 1

:failed
echo 安装失败，请检查网络后重试。
pause
exit /b 1
