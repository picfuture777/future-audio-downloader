@echo off
chcp 65001 >nul
setlocal

rem ============================================================
rem  future音频下载器 · 同步到打包版
rem
rem  用途：改完 musicdl_gui.py 后双击本文件，把新代码同步到
rem        打包输出目录，不必重新打包 exe。
rem ============================================================

set SRC=%~dp0
set DST=%~dp0打包输出\future音频下载器

echo.
echo 正在同步到打包版...
echo.

if not exist "%DST%\future音频下载器.exe" (
    echo [错误] 找不到打包目录：
    echo        %DST%
    echo.
    echo 请先完成一次打包。
    echo.
    pause
    exit /b 1
)

copy /Y "%SRC%musicdl_gui.py" "%DST%\musicdl_gui.py" >nul
if errorlevel 1 (
    echo [失败] musicdl_gui.py 复制失败。
    echo        可能是打包版正在运行，请先关掉程序再试。
    echo.
    pause
    exit /b 1
)
echo   已更新 musicdl_gui.py

if exist "%SRC%使用说明.txt" (
    copy /Y "%SRC%使用说明.txt" "%DST%\使用说明.txt" >nul
    echo   已更新 使用说明.txt
)

if exist "%SRC%config.json" (
    copy /Y "%SRC%config.json" "%DST%\config.json" >nul
    echo   已更新 config.json
)

echo.
echo 同步完成。双击下面这个就是新版：
echo   %DST%\future音频下载器.exe
echo.
pause
