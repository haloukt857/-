@echo off
REM Windows 双击执行：强制终止本项目相关进程 + 重置数据库（默认备份 + 保留地区）
setlocal
set DIR=%~dp0
cd /d "%DIR%\.." || exit /b 1

where python 1>nul 2>nul && (set PY=python) || (set PY=python3)

echo [INFO] 正在查找并终止运行中的进程(run.py/bot.py)...
for /f "tokens=2 delims==;" %%P in ('powershell -NoProfile -Command "Get-CimInstance Win32_Process ^| Where-Object { ($_.CommandLine -match 'run\.py|bot\.py') -and ($_.CommandLine -match [regex]::Escape('%CD%')) } ^| ForEach-Object { $_.ProcessId }"') do (
  echo   - 终止 PID %%P
  powershell -NoProfile -Command "Stop-Process -Id %%P -Force -ErrorAction SilentlyContinue" 1>nul 2>nul
)

%PY% tools\reset_all_data.py --yes --preserve-regions %*

echo.
echo 完成。按任意键关闭...
pause >nul
endlocal
