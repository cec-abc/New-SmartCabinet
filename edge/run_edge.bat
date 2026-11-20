@echo off
chcp 936 >nul
setlocal

rem 边缘机一键启动脚本：双击即可运行。
rem 边缘机是后台服务，没有图形界面，周期帧由服务进程持续发送。

cd /d "%~dp0.."

echo ============================================================
echo   智能工具柜 边缘机 启动程序
echo ============================================================
echo   工作目录 : %CD%
echo   配置文件 : edge\config\config.ini
echo   日志目录 : logs\
echo   周期帧   : 连上上位机后每 3 秒发一帧 periodic
echo ------------------------------------------------------------
echo   停止方式 : 在本窗口按 Ctrl+C
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没有找到 python 命令，请先安装 Python 3.9 或以上并加入 PATH。
    pause
    exit /b 1
)

python -m edge.main
set EXITCODE=%ERRORLEVEL%

echo.
echo ============================================================
echo   边缘机已退出，退出码 %EXITCODE%
echo ============================================================
pause
endlocal
