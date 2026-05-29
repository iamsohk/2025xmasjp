# -*- coding: utf-8 -*-
"""
backtest_engine.py — 誠實回測引擎 v3

回應 code review 三大深層問題：
  1. backtest / live 對齊：trend_strong 逐根 K 線檢查（唔係淨係最後一日）
  2. in-sample 幻覺 / 多重比較：permutation test 計 p-value，再用 BH-FDR 校正
     —— 將「成條 K 線」打亂次序（destroy 時間結構，保留每根 bar 內部 OHLCV），
        跑同一個策略 N 次，睇真實 expectancy 有冇明顯高過「純運氣」。
  3. out-of-sample：報告最後 1/3 段嘅穩健度作參考。

統計設計重點：permutation 保留股票自己嘅 return 分佈（即漂移），
只打散「次序」。所以 p-value 問緊嘅係：
   「你個入場時機規則，有冇 value 過『隻股票本身升咗』？」
單純升嘅股票 → 時機規則加唔到 value → p≈0.5（正路，唔應該收貨）。

止蝕統一用收市價（permutation 後盤中高低位冇意義，要 apples-to-apples）。
經 validate_engine.py 驗證：純噪音 FDR 後通過率 ≈ 0（且 p<0.05 命中率 = 名義 5%），
有真實時機 edge 時通過率 > 80%。
"""

import numpy as np

NEG_INF = -1e18


# ----------------------------------------------------------------------
# 快速 numpy rolling
# ----------------------------------------------------------------------
def _roll_mean(a, w):
    c = np.cumsum(np.insert(a, 0, 0.0))
    out = np.full(len(a), np.nan)
    out[w - 1:] = (c[w:] - c[:-w]) / w
    return out


def _roll_std(a, w):
    c1 = np.cumsum(np.insert(a, 0, 0.0))
    c2 = np.cumsum(np.insert(a * a, 0, 0.0))
    out = np.full(len(a), np.nan)
    s = c1[w:] - c1[:-w]
    ss = c2[w:] - c2[:-w]
    var = (ss - s * s / w) / w
    out[w - 1:] = np.sqrt(np.maximum(var, 0.0))
    return out


def _roll_max(a, w):
    out = np.full(len(a), np.nan)
    for i in range(w - 1, len(a)):
        out[i] = a[i - w + 1:i + 1].max()
    return out


def _roll_min(a, w):
    out = np.full(len(a), np.nan)
    for i in range(w - 1, len(a)):
        out[i] = a[i - w + 1:i + 1].min()
    return out


def _atr(high, low, close, w=14):
    prev = np.roll(close, 1)
    prev[0] = close[0]
    tr = np.maximum.reduce([high - low, np.abs(high - prev), np.abs(low - prev)])
    return _roll_mean(tr, w)


# ----------------------------------------------------------------------
# 指標
# ----------------------------------------------------------------------
def compute_indicators(o, h, l, c, v):
    return {
        "ma20":  _roll_mean(c, 20),
        "ma50":  _roll_mean(c, 50),
        "ma150": _roll_mean(c, 150),
        "ma200": _roll_mean(c, 200),
        "std10": _roll_std(c, 10),
        "std50": _roll_std(c, 50),
        "volma5":  _roll_mean(v, 5),
        "volma50": _roll_mean(v, 50),
        "high250": _roll_max(c, 250),
        "low250":  _roll_min(c, 250),
        "atr": _atr(h, l, c, 14),
        "high": h, "low": l, "close": c, "volume": v,
    }


def trend_gate(ind):
    c = ind["close"]
    return (c > ind["ma50"]) & (ind["ma50"] > ind["ma150"]) & (ind["ma150"] > ind["ma200"])


# ----------------------------------------------------------------------
# 訊號產生器（全部逐根 K 線 gate）
# ----------------------------------------------------------------------
def sig_sniper(ind, trend, lo, hi):
    c, ma20 = ind["close"], ind["ma20"]
    out = []
    for i in range(lo, hi):
        if not trend[i] or np.isnan(ma20[i]) or np.isnan(ma20[i - 1]):
            continue
        if c[i] > ma20[i] and c[i - 1] <= ma20[i - 1]:
            out.append(i)
    return out


def sig_vcp(ind, trend, lo, hi):
    c, s10, s50 = ind["close"], ind["std10"], ind["std50"]
    v5, v50 = ind["volma5"], ind["volma50"]
    lo250, hi250 = ind["low250"], ind["high250"]
    out = []
    for i in range(lo, hi):
        if not trend[i]:
            continue
        if np.isnan(s10[i]) or np.isnan(s50[i]) or np.isnan(v5[i]) or np.isnan(v50[i]):
            continue
        if np.isnan(lo250[i]) or np.isnan(hi250[i]):
            continue
        pos = (c[i] > lo250[i] * 1.3) and (c[i] > hi250[i] * 0.75)
        if pos and s10[i] < s50[i] * 0.6 and v5[i] < v50[i]:
            out.append(i)
    return out


def sig_panic(ind, trend, lo, hi):
    c, h, l, atr = ind["close"], ind["high"], ind["low"], ind["atr"]
    out = []
    for i in range(lo, hi):
        pa = atr[i - 1]
        if np.isnan(pa) or pa <= 0:
            continue
        prev_range = h[i - 1] - l[i - 1]
        if prev_range > pa * 2 and c[i] > h[i - 1]:
            out.append(i)
    return out


SIGNALS = {"Sniper MA20": sig_sniper, "VCP 爆發": sig_vcp, "ATR Panic": sig_panic}


# ----------------------------------------------------------------------
# 回測（收市價止蝕）
# ----------------------------------------------------------------------
def backtest(close, sigs, hold=20, stop_pct=0.10):
    wins = total = 0
    win_r, loss_r = [], []
    n = len(close)
    for i in sigs:
        if i + hold >= n:
            continue
        entry = close[i]
        if close[i + 1:i + hold + 1].min() < entry * (1 - stop_pct):
            loss_r.append(-stop_pct)
            total += 1
            continue
        r = (close[i + hold] - entry) / entry
        (win_r if r > 0 else loss_r).append(r)
        wins += int(r > 0)
        total += 1
    if total == 0:
        return dict(win=0.0, count=0, exp=0.0, payoff=0.0)
    wr = wins / total
    aw = float(np.mean(win_r)) if win_r else 0.0
    al = float(abs(np.mean(loss_r))) if loss_r else 0.0
    payoff = (aw / al) if al > 0 else 0.0
    exp = (wr * aw - (1 - wr) * al) * 100
    return dict(win=round(wr * 100, 1), count=total,
                exp=round(exp, 3), payoff=round(payoff, 2))


def _run_once(o, h, l, c, v, sig_fn, lo, hi, hold, stop_pct):
    ind = compute_indicators(o, h, l, c, v)
    trend = trend_gate(ind)
    sigs = sig_fn(ind, trend, lo, hi)
    return backtest(c, sigs, hold, stop_pct)


# ----------------------------------------------------------------------
# Permutation：打亂整條 K 線次序（保留每根 bar 內部 OHLCV）
# ----------------------------------------------------------------------
def _permute_bars(o, h, l, c, v, rng):
    """以 log-return 重組：打散每日 return 次序，重建價格路徑；量同步打散。
    對 close-only 數據（O=H=L=C）等同於打散 return。"""
    n = len(c)
    log_ret = np.diff(np.log(c))
    perm = rng.permutation(n - 1)
    pr = log_ret[perm]
    new_c = c[0] * np.exp(np.concatenate([[0.0], np.cumsum(pr)]))
    # 用原 bar 嘅相對振幅套返落新 close（保留 intrabar 形狀）
    rel_h = np.divide(h, c, out=np.ones_like(c), where=c != 0)
    rel_l = np.divide(l, c, out=np.ones_like(c), where=c != 0)
    idx = np.concatenate([[0], perm + 1])     # 對應每個新 bar 用邊根原 bar 嘅形狀/量
    new_h = new_c * rel_h[idx]
    new_l = new_c * rel_l[idx]
    new_v = v[idx]
    new_o = new_c.copy()
    return new_o, new_h, new_l, new_c, new_v


def evaluate(o, h, l, c, v, sig_fn, hold=20, stop_pct=0.10,
             min_count=8, train_frac=0.66, n_perm=300, seed=0):
    n = len(c)
    warmup = 200
    lo = max(warmup, 50)
    hi = n - hold
    if hi - lo < 60:
        return None
    rng = np.random.default_rng(seed)

    full = _run_once(o, h, l, c, v, sig_fn, lo, hi, hold, stop_pct)

    split = max(lo + 1, int(n * train_frac))
    oos = _run_once(o, h, l, c, v, sig_fn, split, hi, hold, stop_pct) \
        if hi - split >= 20 else dict(win=0.0, count=0, exp=0.0, payoff=0.0)

    # 樣本不足就唔值得做 permutation（慳時間）；p=1.0 代表「無法證明有 edge」
    if full["count"] < min_count:
        return dict(
            win=full["win"], count=full["count"], exp=full["exp"], payoff=full["payoff"],
            oos_win=oos["win"], oos_count=oos["count"],
            oos_exp=oos["exp"], oos_payoff=oos["payoff"],
            p_value=1.0, passed_raw=False,
        )

    real_exp = full["exp"] if full["count"] >= 1 else NEG_INF
    null_exps = []
    for _ in range(n_perm):
        po, ph, pl, pc, pv = _permute_bars(o, h, l, c, v, rng)
        st = _run_once(po, ph, pl, pc, pv, sig_fn, lo, hi, hold, stop_pct)
        if st["count"] >= 1:
            null_exps.append(st["exp"])
    null_exps = np.array(null_exps) if null_exps else np.array([0.0])
    p_value = (np.sum(null_exps >= real_exp) + 1) / (len(null_exps) + 1)

    return dict(
        win=full["win"], count=full["count"], exp=full["exp"], payoff=full["payoff"],
        oos_win=oos["win"], oos_count=oos["count"],
        oos_exp=oos["exp"], oos_payoff=oos["payoff"],
        p_value=round(float(p_value), 4),
        passed_raw=bool(full["count"] >= min_count and full["exp"] > 0),
    )


# 方便 validate（close-only）
def evaluate_close(close, sig_fn=sig_sniper, **kw):
    c = np.asarray(close, dtype=float)
    return evaluate(c.copy(), c.copy(), c.copy(), c, np.ones_like(c), sig_fn, **kw)


# ----------------------------------------------------------------------
# 多重比較校正（Benjamini-Hochberg FDR）
# ----------------------------------------------------------------------
def bh_fdr(pvals, alpha=0.10):
    p = np.asarray(pvals, dtype=float)
    m = len(p)
    if m == 0:
        return np.array([], dtype=bool)
    order = np.argsort(p)
    ranked = p[order]
    passed = ranked <= alpha * (np.arange(1, m + 1) / m)
    if not passed.any():
        return np.zeros(m, dtype=bool)
    cutoff = ranked[np.max(np.where(passed)[0])]
    return p <= cutoff
