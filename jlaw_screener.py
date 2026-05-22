#!/usr/bin/env python3
"""
J Law Stage 2 Weekly Screener — Longbridge Edition
Data: Longbridge CLI (primary) → yfinance (fallback)
Logic: STRATEGY_MANUAL.md v2026-05-21
"""

import json, subprocess, sys, math, argparse, statistics
from datetime import datetime, date
from typing import Optional, List, Dict, Tuple

# ── Universe ───────────────────────────────────────────────────────────────

UNIVERSE_SP500_TOP50 = [
    "NVDA.US","AAPL.US","MSFT.US","AMZN.US","GOOGL.US","AVGO.US",
    "META.US","TSLA.US","WMT.US","LLY.US","JPM.US","MU.US","AMD.US",
    "XOM.US","V.US","JNJ.US","ORCL.US","COST.US","CSCO.US","MA.US",
    "CAT.US","CVX.US","ABBV.US","NFLX.US","BAC.US","UNH.US","KO.US",
    "LRCX.US","PG.US","PLTR.US","AMAT.US","HD.US","MS.US","PM.US",
    "GE.US","MRK.US","TXN.US","GS.US","RTX.US","LIN.US","WFC.US",
    "KLAC.US","AXP.US","TMUS.US","IBM.US","QCOM.US","INTC.US",
    "ADBE.US","CRM.US","NOW.US",
]

# ── Data layer ─────────────────────────────────────────────────────────────

def _lb_kline(sym: str, period: str = "week", count: int = 260) -> Optional[List[Dict]]:
    """Call Longbridge CLI; return candle list or None."""
    try:
        r = subprocess.run(
            ["longbridge", "kline", sym, "--period", period,
             "--count", str(count), "--format", "json"],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
        raw = json.loads(r.stdout)
        if isinstance(raw, list):
            return raw
        for key in ("candles", "data", "klines", "items"):
            if key in raw and isinstance(raw[key], list):
                return raw[key]
    except Exception:
        pass
    return None


def _to_yf(sym: str) -> str:
    """Convert LB symbol to yfinance ticker."""
    if sym.endswith(".US"):
        return sym[:-3]
    return sym  # HK / others pass through as-is


def _yf_weekly(sym: str, count: int = 260) -> List[Dict]:
    """yfinance weekly candles fallback."""
    try:
        import yfinance as yf
        import pandas as pd
        df = yf.download(_to_yf(sym), period="6y", interval="1wk",
                         progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        result = []
        for idx, row in df.iterrows():
            result.append({
                "timestamp": str(idx.date() if hasattr(idx, "date") else idx),
                "open":   float(row["Open"]),
                "high":   float(row["High"]),
                "low":    float(row["Low"]),
                "close":  float(row["Close"]),
                "volume": int(row["Volume"]) if row["Volume"] > 0 else 0,
            })
        return result[-count:]
    except Exception:
        return []


def get_candles(sym: str, count: int = 260) -> Tuple[List[Dict], str]:
    """Return (candles, source). Source is 'Longbridge' or 'yfinance'."""
    data = _lb_kline(sym, "week", count)
    if data and len(data) >= 80:
        return data, "Longbridge"
    data = _yf_weekly(sym, count)
    if data:
        return data, "yfinance"
    return [], "none"


# ── Helpers ────────────────────────────────────────────────────────────────

def _c(candles): return [x["close"]  for x in candles]
def _h(candles): return [x["high"]   for x in candles]
def _l(candles): return [x["low"]    for x in candles]
def _v(candles): return [x["volume"] for x in candles]
def _o(candles): return [x["open"]   for x in candles]

def sma(vals: list, n: int) -> Optional[float]:
    if len(vals) < n:
        return None
    return sum(vals[-n:]) / n

def is_rising(vals: list, lookback: int = 4) -> bool:
    if len(vals) < lookback + 1:
        return False
    return vals[-1] > vals[-(lookback + 1)]


# ── Earnings window ────────────────────────────────────────────────────────

def check_earnings_window(sym: str, future_days: int = 10) -> bool:
    try:
        import yfinance as yf
        cal = yf.Ticker(_to_yf(sym)).calendar
        if cal is None:
            return False
        dates = cal.get("Earnings Date", []) if isinstance(cal, dict) else (
            cal["Earnings Date"].tolist() if hasattr(cal, "columns") and "Earnings Date" in cal.columns else []
        )
        today = date.today()
        for d in dates:
            dd = d.date() if hasattr(d, "date") else d
            if -2 <= (dd - today).days <= future_days:
                return True
    except Exception:
        pass
    return False


# ── Fundamental sanity ─────────────────────────────────────────────────────

def get_fundamentals(sym: str) -> Dict:
    out = {"pe": None, "unprofitable": False}
    try:
        import yfinance as yf
        info = yf.Ticker(_to_yf(sym)).info or {}
        pe = info.get("trailingPE") or info.get("forwardPE")
        out["pe"] = round(pe, 1) if pe else None
        ni = info.get("netIncomeToCommon")
        if ni is not None and ni < 0:
            out["unprofitable"] = True
    except Exception:
        pass
    return out


# ── Market environment ─────────────────────────────────────────────────────

def market_status(benchmark: str = "SPY.US") -> str:
    candles, _ = get_candles(benchmark, 260)
    if len(candles) < 210:
        return "UNKNOWN"
    c = _c(candles)
    price  = c[-1]
    ma200  = sma(c, 200)
    ma50   = sma(c, 50)
    rise50 = is_rising(c, 4)
    if not ma200 or not ma50:
        return "UNKNOWN"
    if price > ma200 and price > ma50 and rise50:
        return "NORMAL"
    elif price < ma200:
        return "FROZEN"
    else:
        return "CAUTION"


# ── Core analysis ──────────────────────────────────────────────────────────

def analyse(sym: str,
            bench_candles: List[Dict],
            account_size: float = 100_000,
            risk_pct: float = 0.005) -> Dict:

    candles, source = get_candles(sym, 260)

    base = {
        "symbol": sym, "source": source, "decision": "SKIP",
        "score": 0, "tags": [], "score_breakdown": [],
        "close": None, "stop": None, "stop_pct": None, "shares": None,
        "buy_rules_match": False, "earnings_window": False,
        "fundamental": {}, "rs_score": None, "rs_rank": None, "rs_rank_total": None,
        "ma10": None, "ma20": None, "ma50": None, "ma200": None,
        "distance_52h": None, "vol_ratio": None, "error": None,
    }

    if len(candles) < 80:
        base["error"] = "insufficient_data"
        base["tags"].append("insufficient_data")
        return base

    c = _c(candles); h = _h(candles); l = _l(candles)
    v = _v(candles); o = _o(candles)

    price  = c[-1]
    ma10   = sma(c, 10)
    ma20   = sma(c, 20)
    ma50   = sma(c, 50)  if len(c) >= 50  else None
    ma200  = sma(c, 200) if len(c) >= 200 else None

    base.update({
        "close": round(price, 2),
        "ma10":  round(ma10, 2)  if ma10  else None,
        "ma20":  round(ma20, 2)  if ma20  else None,
        "ma50":  round(ma50, 2)  if ma50  else None,
        "ma200": round(ma200, 2) if ma200 else None,
    })

    # 52W stats
    h52 = max(h[-52:]) if len(h) >= 52 else max(h)
    l52 = min(l[-52:]) if len(l) >= 52 else min(l)
    dist_52h = (price / h52 - 1) * 100
    base["distance_52h"] = round(dist_52h, 1)

    score = 0
    tags  = base["tags"]
    bd    = base["score_breakdown"]

    # ── Stage 2 ────────────────────────────────────────────────────────────
    stage2 = False
    if ma50 and ma200 and len(c) >= 54:
        ma50_prev = sma(c[:-4], 50)
        ma50_rising = ma50_prev is not None and ma50 > ma50_prev
        stage2 = (
            price > ma50 > ma200
            and ma50_rising
            and price >= h52 * 0.75
            and price >= l52 * 1.25
        )
    if stage2:
        score += 25; tags.append("stage2"); bd.append(("Stage 2", +25))

    # ── Trend Alignment ─────────────────────────────────────────────────────
    ma_stack = (ma10 and ma20 and ma50 and ma200
                and price > ma10 > ma20 > ma50 > ma200)
    if ma_stack:
        score += 15; tags.append("ma_stack"); bd.append(("MA Stack", +15))

    # ── RS Score ────────────────────────────────────────────────────────────
    bc = _c(bench_candles)
    rs_score = None
    if len(bc) >= 52 and len(c) >= 52:
        def ret(series, n): return series[-1] / series[-n] - 1 if len(series) >= n else 0
        rs_score = round((
            (ret(c, 13) - ret(bc, 13)) * 0.5 +
            (ret(c, 26) - ret(bc, 26)) * 0.3 +
            (ret(c, 52) - ret(bc, 52)) * 0.2
        ) * 100, 2)
        base["rs_score"] = rs_score
    if rs_score is not None and rs_score > 0:
        score += 20; tags.append("rs_leader"); bd.append(("RS Leader", +20))

    # ── Volume ──────────────────────────────────────────────────────────────
    vol_ratio = None
    if len(v) >= 20:
        avg20 = sma(v, 20)
        if avg20 and avg20 > 0:
            vol_ratio = v[-1] / avg20
    base["vol_ratio"] = round(vol_ratio, 2) if vol_ratio else None
    vol_confirmed = vol_ratio is not None and vol_ratio >= 1.5
    if vol_confirmed:
        score += 10; tags.append("volume_confirmed"); bd.append(("Volume", +10))

    # ── Breakout ────────────────────────────────────────────────────────────
    breakout = False
    stop = None
    if len(h) >= 14 and vol_confirmed:
        h13 = max(h[-14:-1])
        if price > h13 * 1.005:
            breakout = True
            stop = h13 * 0.97
    if breakout:
        score += 20; tags.append("breakout"); bd.append(("Breakout", +20))

    # ── Pullback ────────────────────────────────────────────────────────────
    pullback = False
    if stage2 and not breakout:
        near20 = (ma20 and abs(price - ma20) / ma20 <= 0.035 and c[-1] > o[-1])
        near50 = (ma50 and abs(price - ma50) / ma50 <= 0.040 and c[-1] > o[-1])
        pullback = near20 or near50
    if pullback:
        score += 15; tags.append("pullback"); bd.append(("Pullback", +15))
        candidates = []
        if ma20: candidates.append(ma20 * 0.97)
        if ma50: candidates.append(ma50 * 0.98)
        valid = [s for s in candidates if s < price]
        stop = max(valid) if valid else price * 0.92

    # Default stop
    if stop is None:
        stop = (ma50 * 0.98) if ma50 else (price * 0.92)

    # ── Bullish Candle ──────────────────────────────────────────────────────
    if c[-1] > o[-1] and (c[-1] / o[-1] - 1) >= 0.02:
        score += 5; tags.append("bullish_candle"); bd.append(("Bullish Candle", +5))

    # ── Distribution Warning ─────────────────────────────────────────────────
    if c[-1] < o[-1] and (o[-1] / c[-1] - 1) >= 0.03 and vol_confirmed:
        score -= 25; tags.append("distribution_warning"); bd.append(("Distribution", -25))

    # ── VCP-like ────────────────────────────────────────────────────────────
    if len(h) >= 13 and len(l) >= 13:
        def avg_rng(a, b):
            rs = [h[i] - l[i] for i in range(a, b)]
            return statistics.mean(rs) if rs else 0
        n = len(h)
        r3 = avg_rng(n-3, n); r8 = avg_rng(n-8, n-3); r13 = avg_rng(n-13, n-8)
        if r3 < r8 < r13:
            score += 5; tags.append("vcp_like"); bd.append(("VCP-like", +5))

    # ── Earnings Window ──────────────────────────────────────────────────────
    earnings = check_earnings_window(sym)
    base["earnings_window"] = earnings
    if earnings:
        score -= 20; tags.append("earnings_window"); bd.append(("Earnings Window", -20))

    score = max(0, min(100, score))
    base["score"] = score

    # ── Stop & MRA ──────────────────────────────────────────────────────────
    stop_pct = (price - stop) / price * 100
    base["stop"]     = round(stop, 2)
    base["stop_pct"] = round(stop_pct, 1)

    if stop < price:
        risk_amt  = account_size * risk_pct
        rps       = price - stop
        shares    = int(risk_amt / rps)
        cap       = int(account_size * 0.10 / price)
        if shares > cap:
            tags.append("position_cap")
            shares = cap
        base["shares"] = shares

    # ── Fundamentals ────────────────────────────────────────────────────────
    fund = get_fundamentals(sym)
    base["fundamental"] = fund
    if fund.get("unprofitable"):
        tags.append("unprofitable")

    # ── Decision ────────────────────────────────────────────────────────────
    rs_beats = rs_score is not None and rs_score > 0
    if stage2 and (breakout or pullback) and rs_beats and score >= 65 and not earnings:
        base["decision"] = "BUY_CANDIDATE"
    elif stage2 and score >= 45:
        base["decision"] = "WATCH"
    else:
        base["decision"] = "SKIP"

    return base


# ── Post-processing ────────────────────────────────────────────────────────

def fill_rs_ranks(results: List[Dict]) -> None:
    ranked = sorted(
        [(r, r["rs_score"]) for r in results if r["rs_score"] is not None],
        key=lambda x: -x[1]
    )
    n = len(ranked)
    for i, (r, _) in enumerate(ranked):
        r["rs_rank"] = i + 1
        r["rs_rank_total"] = n


def apply_market_status(results: List[Dict], mstatus: str) -> None:
    for r in results:
        if mstatus == "FROZEN" and r["decision"] == "BUY_CANDIDATE":
            r["decision"] = "WATCH"
            r["tags"].append("market_frozen")
        elif mstatus == "CAUTION" and r["decision"] == "BUY_CANDIDATE":
            r["decision"] = "WATCH"
            r["tags"].append("market_caution")


def mark_buy_rules(results: List[Dict], mstatus: str) -> None:
    for r in results:
        rk = r.get("rs_rank")
        if (r["score"] >= 80
                and rk is not None and rk <= 10
                and "stage2" in r["tags"]
                and not r["earnings_window"]
                and mstatus == "NORMAL"
                and r["distance_52h"] is not None and r["distance_52h"] >= -15
                and r["stop_pct"] is not None and r["stop_pct"] <= 12):
            r["buy_rules_match"] = True


# ── Markdown report ────────────────────────────────────────────────────────

def render_md(results: List[Dict], mstatus: str, benchmark: str,
              account_size: float, risk_pct: float) -> str:
    now  = datetime.now().strftime("%Y-%m-%d %H:%M")
    buy  = [r for r in results if r["decision"] == "BUY_CANDIDATE"]
    wtch = [r for r in results if r["decision"] == "WATCH"]
    skip = [r for r in results if r["decision"] == "SKIP"]

    lines = [
        f"# J Law Stage 2 Weekly Screener",
        f"> {now}  |  Benchmark: {benchmark}  |  Market: **{mstatus}**"
        f"  |  Account: ${account_size:,.0f}  |  Risk/trade: {risk_pct*100:.1f}%\n",
        f"## Summary: {len(buy)} BUY_CANDIDATE | {len(wtch)} WATCH | {len(skip)} SKIP\n",
    ]

    def tbl(title, rows):
        if not rows:
            return
        lines.append(f"## {title}\n")
        lines.append("| Symbol | Score | RS | Close | Stop | Stop% | Shs | Tags |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
        for r in sorted(rows, key=lambda x: -x["score"]):
            sym   = f"**{r['symbol']}** ✓" if r.get("buy_rules_match") else r["symbol"]
            rk    = f"#{r['rs_rank']}/{r['rs_rank_total']}" if r.get("rs_rank") else "—"
            close = f"${r['close']:.2f}" if r["close"] else "—"
            stp   = f"${r['stop']:.2f}" if r["stop"] else "—"
            stpp  = f"{r['stop_pct']:.1f}%" if r["stop_pct"] else "—"
            shs   = str(r["shares"]) if r["shares"] else "—"
            tgs   = " ".join(f"`{t}`" for t in r["tags"]
                             if t not in ("stage2", "ma_stack", "rs_leader"))
            lines.append(f"| {sym} | {r['score']} | {rk} | {close} | {stp} | {stpp} | {shs} | {tgs} |")
        lines.append("")

    tbl("BUY_CANDIDATE", buy)
    tbl("WATCH", wtch)
    tbl("SKIP (Stage 2)", [r for r in skip if "stage2" in r["tags"]])

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="J Law Stage 2 Weekly Screener")
    p.add_argument("--symbols", nargs="*")
    p.add_argument("--benchmark",      default="SPY.US")
    p.add_argument("--account-size",   type=float, default=100_000)
    p.add_argument("--risk-per-trade", type=float, default=0.005)
    p.add_argument("--out",            default=None)
    p.add_argument("--format", choices=["md", "json"], default="md")
    args = p.parse_args()

    symbols = args.symbols or UNIVERSE_SP500_TOP50

    print(f"[*] Market check ({args.benchmark})...", file=sys.stderr)
    mstatus = market_status(args.benchmark)
    print(f"[*] Market: {mstatus}", file=sys.stderr)

    bench_candles, _ = get_candles(args.benchmark, 260)

    results = []
    for i, sym in enumerate(symbols, 1):
        print(f"[{i:2d}/{len(symbols)}] {sym}...        ", file=sys.stderr, end="\r")
        results.append(analyse(sym, bench_candles, args.account_size, args.risk_per_trade))

    fill_rs_ranks(results)
    apply_market_status(results, mstatus)
    mark_buy_rules(results, mstatus)

    output = (json.dumps(results, indent=2, default=str)
              if args.format == "json"
              else render_md(results, mstatus, args.benchmark,
                             args.account_size, args.risk_per_trade))

    if args.out:
        import os; os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        open(args.out, "w").write(output)
        print(f"\n[*] → {args.out}", file=sys.stderr)
    else:
        print("\n" + output)


if __name__ == "__main__":
    main()
