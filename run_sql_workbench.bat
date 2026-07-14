@echo off
cd /d "%~dp0"
python -m sql_workbench
if errorlevel 1 (
    echo.
    echo 실행 실패. Python이 PATH에 있는지 확인하세요.
    pause
)
