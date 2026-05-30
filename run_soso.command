#!/bin/bash
# 蘇蘇指揮官啟動器 (Mac 雙擊此檔案)
cd "$(dirname "$0")"

echo "=========================================="
echo " 蘇蘇指揮官 v5.0LB 啟動中..."
echo "=========================================="

# 檢查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python3，請先安裝："
    echo "   https://www.python.org/downloads/"
    read -p "按 Enter 關閉..."
    exit 1
fi

# 安裝依賴（只在第一次）
echo "📦 檢查依賴套件..."
python3 -c "import yfinance, pandas, numpy" 2>/dev/null || \
    python3 -m pip install yfinance pandas numpy --quiet

echo ""
python3 soso_trader.py

echo ""
read -p "✅ 完成！按 Enter 關閉視窗..."
