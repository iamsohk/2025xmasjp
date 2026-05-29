# -*- coding: utf-8 -*-
"""
蘇蘇全自動投資助理 (Soso Trader Commander)
版本：v4.9LB (長橋 MCP/CLI 整合版)
功能：大市共振 + 板塊輪動 + 動能雷達 + 持倉檢查 + Sniper/VCP/Panic 嚴選 + BTC
數據：優先長橋 CLI，後備 Yahoo Finance
"""

import yfinance as yf
import pandas as pd
import numpy as np
import datetime as dt
import warnings
import subprocess
import json
import sys

warnings.simplefilter(action='ignore', category=FutureWarning)

# ==========================================
# 1) 設定中心
# ==========================================
MAX_POSITIONS = 8

MY_HOLDINGS = ["TYL","TSLA","PLTR","GOOG","VT","AMAT","META","FIG"]
MY_PICKS    = ["FUTU","MU","JNJ","GE","GOOG","COST","MRVL","PLTR"]

SECTORS = {
    "XLK":"科技","XLF":"金融","XLV":"醫療","XLE":"能源","XLY":"非必需消費",
    "XLP":"必需消費","XLI":"工業","XLC":"通訊","XLU":"公用","SMH":"半導體"
}

SP100 = [
    "AAPL","ABBV","ABT","ACN","ADBE","AIG","AMD","AMGN","AMT","AMZN","AXP","BA","BAC","BK","BKNG",
    "BLK","BMY","BRK-B","C","CAT","CHTR","CL","CMCSA","COF","COP","COST","CRM","CSCO","CVS","CVX",
    "DE","DHR","DIS","DOW","DUK","EMR","EXC","F","FDX","GD","GE","GILD","GM","GOOG","GOOGL","GS",
    "HD","HON","IBM","INTC","JNJ","JPM","KHC","KO","LIN","LLY","LMT","LOW","MA","MCD","MDLZ","MDT",
    "MET","META","MMM","MO","MRK","MS","MSFT","NEE","NFLX","NKE","NVDA","ORCL","PEP","PFE","PG",
    "PM","PYPL","QCOM","RTX","SBUX","SCHW","SO","SPG","T","TGT","TMO","TMUS","TSLA","TXN","UNH",
    "UNP","UPS","USB","V","VZ","WFC","WMT","XOM"
]

UNIVERSE = list(set(SP100 + MY_PICKS) - set(MY_HOLDINGS))

MIN_WINRATE = 60
MIN_COUNT   = 30
HOLD_DAYS   = 20
STOP_PCT    = 0.10

# ==========================================
# 2) 長橋 CLI 數據層
# ==========================================
_LB_AVAILABLE = None

def lb_available():
    global _LB_AVAILABLE
    if _LB_AVAILABLE is None:
        try:
            r = subprocess.run(["longbridge", "check"], capture_output=True, timeout=5)
            _LB_AVAILABLE = r.returncode == 0
        except Exception:
            _LB_AVAILABLE = False
    return _LB_AVAILABLE

def to_lb_symbol(ticker):
    """Convert Yahoo ticker to Longbridge format."""
    if ticker.endswith(".HK"):
        return ticker
    special = {"BTC-USD": "BTC-USDT.OTC", "BRK-B": "BRK-B.US",
                "^VIX": "VIX.US", "^GSPC": "SPX.US", "^IXIC": "IXIC.US"}
    if ticker in special:
        return special[ticker]
    return f"{ticker}.US"

def lb_get_kline(ticker, period="day", count=500):
    """Fetch OHLCV from Longbridge CLI."""
    if not lb_available():
        return None
    sym = to_lb_symbol(ticker)
    if sym in ("VIX.US", "^VIX"):
        return None  # VIX not available via LB kline
    try:
        r = subprocess.run(
            ["longbridge", "kline", sym, "--period", period,
             "--count", str(count), "--format", "json"],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            return None
        raw = json.loads(r.stdout)
        rows = raw if isinstance(raw, list) else raw.get("candles", raw.get("data", []))
        if not rows:
            return None
        df = pd.DataFrame(rows)
        # Normalize column names
        col_map = {}
        for col in df.columns:
            cl = col.lower()
            if cl in ("timestamp","time","date","datetime"): col_map[col] = "Date"
            elif cl == "open":  col_map[col] = "Open"
            elif cl == "high":  col_map[col] = "High"
            elif cl == "low":   col_map[col] = "Low"
            elif cl in ("close","adj_close"): col_map[col] = "Close"
            elif cl == "volume": col_map[col] = "Volume"
        df = df.rename(columns=col_map)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], unit="s", errors="coerce").fillna(
                pd.to_datetime(df["Date"], errors="coerce"))
            df = df.set_index("Date").sort_index()
        for col in ["Open","High","Low","Close","Volume"]:
            if col not in df.columns:
                df[col] = np.nan
        if "Adj Close" not in df.columns:
            df["Adj Close"] = df["Close"]
        return df.dropna(subset=["Close"])
    except Exception:
        return None

# ==========================================
# 3) 工具函數
# ==========================================
def get_data(ticker, period="2y"):
    # 1) Try Longbridge CLI
    count_map = {"1y": 260, "2y": 520, "3y": 780, "3mo": 65}
    lb_count = count_map.get(period, 520)
    df = lb_get_kline(ticker, "day", lb_count)
    if df is not None and len(df) >= 25:
        return df

    # 2) Fallback: Yahoo Finance
    try:
        df = yf.download(ticker, period=period, progress=False, auto_adjust=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if "Adj Close" in df.columns:
            df["Close"] = df["Adj Close"]
        if "Close" not in df.columns:
            return None
        df = df.dropna()
        return df if len(df) >= 25 else None
    except Exception:
        return None

def calc_indicators(df):
    df = df.copy()
    df["MA20"]  = df["Close"].rolling(20).mean()
    df["MA50"]  = df["Close"].rolling(50).mean()
    df["MA150"] = df["Close"].rolling(150).mean()
    df["MA200"] = df["Close"].rolling(200).mean()
    df["High250"] = df["Close"].rolling(250).max()
    df["Low250"]  = df["Close"].rolling(250).min()

    delta = df["Close"].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    rs = up.rolling(14).mean() / (down.rolling(14).mean() + 1e-12)
    df["RSI"] = 100 - (100 / (1 + rs))

    h, l, c = df["High"], df["Low"], df["Close"]
    prev_c = c.shift(1)
    tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()

    df["STD10"]   = df["Close"].rolling(10).std()
    df["STD50"]   = df["Close"].rolling(50).std()
    df["VolMA5"]  = df["Volume"].rolling(5).mean()
    df["VolMA50"] = df["Volume"].rolling(50).mean()
    return df

def honest_backtest(df, entry_indices, hold_days=20, stop_pct=0.10):
    wins = 0; total = 0; win_rs = []; loss_rs = []
    c = df["Close"].values
    l = df["Low"].values
    n = len(c)
    for idx in entry_indices:
        if idx + hold_days >= n:
            continue
        entry = float(c[idx])
        stop  = entry * (1 - stop_pct)
        if np.min(l[idx+1:idx+hold_days+1]) < stop:
            loss_rs.append(-stop_pct)
            total += 1
            continue
        r = (float(c[idx+hold_days]) - entry) / entry
        if r > 0:
            wins += 1
            win_rs.append(r)
        else:
            loss_rs.append(r)
        total += 1
    if total == 0:
        return 0, 0, 0, 0
    wr       = wins / total
    avg_win  = float(np.mean(win_rs))        if win_rs  else 0.0
    avg_loss = float(abs(np.mean(loss_rs)))  if loss_rs else 0.0
    payoff   = round(avg_win / avg_loss, 2)  if avg_loss > 0 else 0.0
    expectancy = round((wr * avg_win - (1 - wr) * avg_loss) * 100, 2)
    return round(wr * 100, 1), total, expectancy, payoff

# ==========================================
# 4) 模組
# ==========================================
def check_market_resonance():
    print("🔍 檢查大市共振 (QQQ+SPY+VIX)...")
    qqq = get_data("QQQ", "1y")
    spy = get_data("SPY", "1y")
    vix = get_data("^VIX", "1y")

    if qqq is None or spy is None or vix is None:
        return "數據不足", "⚠️ 無法判斷", False, np.nan

    qqq = calc_indicators(qqq)
    spy = calc_indicators(spy)

    q_p    = float(qqq["Close"].iloc[-1])
    q_ma50 = float(qqq["MA50"].iloc[-1])
    q_ma200= float(qqq["MA200"].iloc[-1])
    s_p    = float(spy["Close"].iloc[-1])
    s_ma50 = float(spy["MA50"].iloc[-1])
    v_p    = float(vix["Close"].iloc[-1])

    if q_p < q_ma200:
        return "🔴 熊市 (Risk Off)", f"QQQ跌穿年線，現金為王 (VIX:{v_p:.2f})", False, v_p

    score = sum([q_p > q_ma50, s_p > s_ma50])
    if score == 2: return "🟢 全面 Risk On", f"趨勢強勁 (VIX:{v_p:.2f})", True, v_p
    elif score == 1: return "🟡 震盪 (Neutral)", f"分歧市況 (VIX:{v_p:.2f})", True, v_p
    else: return "🔴 轉弱 (Warning)", f"動能減弱 (VIX:{v_p:.2f})", False, v_p

def check_sectors():
    print("📊 掃描板塊輪動中...")
    sector_perf = []
    for ticker, name in SECTORS.items():
        df = get_data(ticker, "1y")
        if df is None or len(df) < 25:
            continue
        ret = (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[-20]) - 1) * 100
        sector_perf.append({"Code": ticker, "Name": name, "Perf": ret})

    if not sector_perf:
        return "N/A", "N/A"

    df_sec = pd.DataFrame(sector_perf).sort_values("Perf", ascending=False)
    top_str  = ", ".join([r["Name"] for _, r in df_sec.head(3).iterrows()])
    weak_str = ", ".join([r["Name"] for _, r in df_sec.tail(3).iterrows()])
    return top_str, weak_str

def check_momentum():
    print("⚡ 掃描全場動能排行 (5日/20日)...")
    mom_data = []
    for t in UNIVERSE:
        df = get_data(t, "3mo")
        if df is None or len(df) < 25:
            continue
        p = float(df["Close"].iloc[-1])
        ret_5d  = (p / float(df["Close"].iloc[-5])  - 1) * 100
        ret_20d = (p / float(df["Close"].iloc[-20]) - 1) * 100
        mom_data.append({"Ticker": t, "5d%": round(ret_5d,1), "20d%": round(ret_20d,1)})

    if not mom_data:
        return pd.DataFrame(), pd.DataFrame()

    df_mom = pd.DataFrame(mom_data)
    return df_mom.sort_values("20d%", ascending=False).head(5), \
           df_mom.sort_values("20d%", ascending=True).head(3)

def check_holdings():
    print("💼 檢查持倉健康度...")
    report = []
    current_count = len(MY_HOLDINGS)

    if current_count >= MAX_POSITIONS:
        discipline_msg = f"⚠️ 持倉爆額 ({current_count}/{MAX_POSITIONS})！❌ 暫時停止買入，只准賣出。"
        can_buy = False
    else:
        discipline_msg = f"✅ 額度正常 ({current_count}/{MAX_POSITIONS})，可尋找機會。"
        can_buy = True

    for t in MY_HOLDINGS:
        df = get_data(t, "1y")
        if df is None:
            continue
        df = calc_indicators(df)
        p    = float(df["Close"].iloc[-1])
        ma20 = float(df["MA20"].iloc[-1])
        ma50 = float(df["MA50"].iloc[-1])

        if np.isnan(ma20) or np.isnan(ma50):
            continue

        if p > ma20:   status, act = "🟢 強勢", "持有"
        elif p > ma50: status, act = "🟡 回調", "觀察"
        else:          status, act = "🔴 轉弱", "止蝕/減倉"

        report.append([t, status, round(p,2), act])

    return pd.DataFrame(report, columns=["Ticker","Status","Price","Action"]), discipline_msg, can_buy

def run_scan():
    print(f"🚀 啟動三重策略掃描 (Win>={MIN_WINRATE}% & Count>={MIN_COUNT} & Exp>0 & Payoff>=1.5)...")
    sniper_list, vcp_list, panic_list = [], [], []

    for t in UNIVERSE:
        df = get_data(t, "3y")
        if df is None or len(df) < 250:
            continue
        df = calc_indicators(df)

        c     = df["Close"]
        p     = float(c.iloc[-1])
        atr   = float(df["ATR"].iloc[-1])
        ma20  = df["MA20"]
        ma50  = df["MA50"]
        ma150 = df["MA150"]
        ma200 = df["MA200"]

        if any(np.isnan([ma20.iloc[-1], ma50.iloc[-1], ma150.iloc[-1], ma200.iloc[-1], atr])):
            continue

        trend_strong = (p > ma50.iloc[-1]) and (ma50.iloc[-1] > ma150.iloc[-1]) and (ma150.iloc[-1] > ma200.iloc[-1])

        # Sniper
        if trend_strong:
            sigs = [i for i in range(50, len(df)-HOLD_DAYS)
                    if c.iloc[i] > ma20.iloc[i] and c.iloc[i-1] <= ma20.iloc[i-1]]
            wr, cnt, exp, payoff = honest_backtest(df, sigs, HOLD_DAYS, STOP_PCT)
            if wr >= MIN_WINRATE and cnt >= MIN_COUNT and exp > 0 and payoff >= 1.5:
                sniper_list.append({"Ticker":t,"Price":p,"WinRate":wr,"Count":cnt,"Exp%":exp,"Payoff":payoff,"Setup":"Sniper MA20","Stop":round(p-2*atr,2)})

        # VCP
        vcp_pos = (p > float(df["Low250"].iloc[-1]) * 1.3) and (p > float(df["High250"].iloc[-1]) * 0.75)
        if trend_strong and vcp_pos:
            sigs = [i for i in range(60, len(df)-HOLD_DAYS)
                    if df["STD10"].iloc[i] < df["STD50"].iloc[i]*0.6 and df["VolMA5"].iloc[i] < df["VolMA50"].iloc[i]]
            wr, cnt, exp, payoff = honest_backtest(df, sigs, HOLD_DAYS, STOP_PCT)
            if wr >= MIN_WINRATE and cnt >= MIN_COUNT and exp > 0 and payoff >= 1.5:
                vcp_list.append({"Ticker":t,"Price":p,"WinRate":wr,"Count":cnt,"Exp%":exp,"Payoff":payoff,"Setup":"VCP 爆發","Stop":round(p-2*atr,2)})

        # ATR Panic
        sigs = []
        for i in range(30, len(df)-HOLD_DAYS):
            prev_range = float(df["High"].iloc[i-1] - df["Low"].iloc[i-1])
            prev_atr   = float(df["ATR"].iloc[i-1])
            if prev_atr <= 0 or np.isnan(prev_atr):
                continue
            if prev_range > prev_atr*2 and float(c.iloc[i]) > float(df["High"].iloc[i-1]):
                sigs.append(i)
        wr, cnt, exp, payoff = honest_backtest(df, sigs, HOLD_DAYS, STOP_PCT)
        if wr >= MIN_WINRATE and cnt >= MIN_COUNT and exp > 0 and payoff >= 1.5:
            panic_list.append({"Ticker":t,"Price":p,"WinRate":wr,"Count":cnt,"Exp%":exp,"Payoff":payoff,"Setup":"ATR Panic","Stop":round(float(df["Low"].iloc[-1]),2)})

    return pd.DataFrame(sniper_list), pd.DataFrame(vcp_list), pd.DataFrame(panic_list)

def check_btc():
    print("🪙 檢查 Crypto...")
    df = get_data("BTC-USD", "2y")
    if df is None:
        return "N/A", "N/A"
    df_w = df.resample("W").last()
    if len(df_w) < 60:
        return f"${float(df_w['Close'].iloc[-1]):,.0f}", "N/A"
    ma50 = float(df_w["Close"].rolling(50).mean().iloc[-1])
    p    = float(df_w["Close"].iloc[-1])
    halving = dt.datetime(2024, 4, 20)
    days = (dt.datetime.now() - halving).days
    status = "🐂 牛市" if p > ma50 else "🐻 震盪"
    return f"${p:,.0f}", f"{status} | 減半後 {days} 天"

# ==========================================
# 5) 主程式
# ==========================================
def main():
    print("\n" + "="*58)
    print(f"🫡 蘇蘇指揮官報告 v4.9LB | {dt.date.today()}")
    if lb_available():
        print("   📡 數據源：長橋 CLI ✅ (已登入)")
    else:
        print("   📡 數據源：Yahoo Finance (長橋未登入)")
    print("="*58)

    m_status, m_msg, market_ok, vix_val = check_market_resonance()
    print(f"\n🌡️ 大市：{m_status}\n   👉 {m_msg}")

    top, weak = check_sectors()
    print(f"\n📊 板塊：🔥 {top} | ❄️ {weak}")

    df_top_mom, df_weak_mom = check_momentum()
    print(f"\n⚡ 動能雷達：")
    if not df_top_mom.empty:
        print(f"   📈 最強 Top 5 (20日)：{', '.join(df_top_mom['Ticker'].tolist())}")
    if not df_weak_mom.empty:
        print(f"   📉 最弱 Top 3 (20日)：{', '.join(df_weak_mom['Ticker'].tolist())}")

    df_h, disc_msg, allow_buy = check_holdings()
    print(f"\n💼 持倉狀態：\n   {disc_msg}")
    if not df_h.empty:
        print(df_h.to_string(index=False, header=False))

    if market_ok:
        if not allow_buy:
            print("\n👀 提示：持倉已滿，以下只供「眼看手勿動」(Window Shopping)。")

        df_s, df_v, df_p = run_scan()

        def show(df, title):
            print(f"\n{title}")
            if df is None or df.empty:
                print("   (無符合條件)")
                return
            df = df.sort_values(["Exp%","WinRate","Count"], ascending=[False,False,False]).head(3)
            print(df[["Ticker","Price","WinRate","Count","Exp%","Payoff","Stop"]].to_string(index=False))

        show(df_s, "🛡️【Sniper 狙擊】(誠實回測通過)")
        show(df_v, "⚔️【VCP 爆發】(誠實回測通過)")
        show(df_p, "⚡【ATR Panic】(誠實回測通過)")
    else:
        print("\n🛑 掃描暫停：大市風險高 (紅燈)，保留現金。")

    bp, bs = check_btc()
    print(f"\n🪙 BTC：{bp} | {bs}")

    print("\n" + "="*58)
    print("🧘‍♂️ 任務完成：深呼吸兩下，呼氣一下；放低電話，陪老婆囡囡。")
    print("="*58)

if __name__ == "__main__":
    main()
