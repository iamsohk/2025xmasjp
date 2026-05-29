@echo off
chcp 65001 >nul
title 蘇蘇指揮官 v4.9LB
cd /d "%~dp0"

echo ==========================================
echo  蘇蘇指揮官 v4.9LB 啟動中...
echo ==========================================

:: 檢查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到 Python，請先安裝：
    echo    https://www.python.org/downloads/
    echo    安裝時記得勾選 "Add Python to PATH"
    pause
    exit /b 1
)

:: 安裝依賴
echo 📦 檢查依賴套件...
python -c "import yfinance, pandas, numpy" >nul 2>&1
if errorlevel 1 (
    echo 安裝中，請稍等...
    python -m pip install yfinance pandas numpy --quiet
)

echo.
python soso_trader.py

echo.
pause
