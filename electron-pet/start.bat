@echo off
cd /d "%~dp0"
echo === AI 小助手 - Electron 桌面宠物 ===
echo.
echo 正在检查依赖...
where npm >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [错误] 未找到 npm，请先安装 Node.js：https://nodejs.org/
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo 首次运行，正在安装依赖（可能需要几分钟）...
    call npm install
    if %ERRORLEVEL% neq 0 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)

echo 启动 Electron 应用...
npx electron .
if %ERRORLEVEL% neq 0 (
    echo [错误] 启动失败
    pause
)
