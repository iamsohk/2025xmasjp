# -*- coding: utf-8 -*-
"""
validate_engine.py — 噪音基準實驗（Noise Benchmark）

回應 reviewer 嘅實驗：餵合成股票入 scanner，量度通過率與檢定力。

三組對照：
  • NOISE        純隨機遊走（零序列結構）—— 應該幾乎全部被拒
  • DRIFT-MOM    regime-switching 漂移 —— 有趨勢但時機 edge 弱（誠實的灰色地帶）
  • INJECTED     注入真實「升穿 MA20 後續漲」嘅時機 edge —— 應該大比例通過

驗證標準：
  1. 校正性：NOISE 嘅 permutation p<0.05 命中率 ≈ 名義 5%
  2. 假陽性控制：NOISE 經 permutation+FDR 後通過率 ≈ 0%
  3. 檢定力：INJECTED 經 permutation+FDR 後通過率明顯 > 0%
"""

import numpy as np
import backtest_engine as be

HOLD, STOP, N_DAYS = 20, 0.10, 780
N_STOCKS = 100
N_PERM = 400
FDR_ALPHA = 0.10
MIN_COUNT = 8
SEED = 12345


def gen_noise(n, rng):
    return 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, n)))


def gen_drift_momentum(n, rng, sigma=0.013, p_stay=0.985):
    bull, bear = 0.0025, -0.0015
    state = 1 if rng.random() < 0.6 else 0
    rets = np.empty(n)
    for t in range(n):
        if rng.random() > p_stay:
            state = 1 - state
        rets[t] = rng.normal(bull if state else bear, sigma)
    return 100.0 * np.exp(np.cumsum(rets))


def gen_injected(n, rng, sigma=0.013, boost=0.004):
    """注入真實時機 edge：升穿 MA20 後 15 日有正漂移。"""
    rets = rng.normal(0.0002, sigma, n)
    close = 100 * np.exp(np.cumsum(rets))
    for _ in range(3):
        ma20 = be._roll_mean(close, 20)
        b = rets.copy()
        for i in range(21, n - 1):
            if close[i] > ma20[i] and close[i - 1] <= ma20[i - 1]:
                b[i + 1:min(i + 15, n)] += boost
        close = 100 * np.exp(np.cumsum(b))
    return close


# OLD filter（現行 soso_trader 邏輯複製：trend 只 check 最後一日、訊號唔逐根 gate）
def old_filter_pass(close):
    n = len(close)
    ma20 = be._roll_mean(close, 20)
    ma50 = be._roll_mean(close, 50)
    ma150 = be._roll_mean(close, 150)
    ma200 = be._roll_mean(close, 200)
    if not (close[-1] > ma50[-1] and ma50[-1] > ma150[-1] and ma150[-1] > ma200[-1]):
        return False
    sigs = [i for i in range(50, n - HOLD)
            if not np.isnan(ma20[i]) and not np.isnan(ma20[i - 1])
            and close[i] > ma20[i] and close[i - 1] <= ma20[i - 1]]
    st = be.backtest(close, sigs, HOLD, STOP)
    return st["win"] >= 60 and st["count"] >= 30 and st["exp"] > 0 and st["payoff"] >= 1.5


def run(label, gen_fn, seed):
    rng = np.random.default_rng(seed)
    old_pass = raw_pass = 0
    all_p, cand_p = [], []
    for _ in range(N_STOCKS):
        close = gen_fn(N_DAYS, rng)
        old_pass += int(old_filter_pass(close))
        res = be.evaluate_close(close, be.sig_sniper, hold=HOLD, stop_pct=STOP,
                                min_count=MIN_COUNT, n_perm=N_PERM,
                                seed=int(rng.integers(1 << 30)))
        if res is None:
            continue
        if res["count"] >= MIN_COUNT:
            all_p.append(res["p_value"])
        if res["passed_raw"]:
            raw_pass += 1
            cand_p.append(res["p_value"])
    fdr = int(be.bh_fdr(np.array(cand_p), FDR_ALPHA).sum()) if cand_p else 0
    ap = np.array(all_p) if all_p else np.array([1.0])
    print(f"\n===== {label} ({N_STOCKS} 隻) =====")
    print(f"  OLD filter 通過               : {old_pass:3d} ({old_pass}%)")
    print(f"  NEW 預過濾 (count>={MIN_COUNT} & exp>0): {raw_pass:3d} ({raw_pass}%)")
    print(f"  NEW + permutation + FDR 通過  : {fdr:3d} ({fdr}%)")
    print(f"  p-value 校正檢查: median={np.median(ap):.3f}  p<0.05命中率={ (ap<0.05).mean()*100:.0f}%")
    return dict(old=old_pass, raw=raw_pass, fdr=fdr, psig=(ap < 0.05).mean())


if __name__ == "__main__":
    print(f"實驗：{N_STOCKS} 隻合成股票 × Sniper MA20，{N_DAYS}日，"
          f"hold={HOLD}，stop={STOP:.0%}，n_perm={N_PERM}，FDR={FDR_ALPHA}")
    noise = run("NOISE 純噪音", gen_noise, SEED)
    drift = run("DRIFT-MOM 漂移趨勢", gen_drift_momentum, SEED + 1)
    inj = run("INJECTED 真實時機edge", gen_injected, SEED + 2)

    print("\n" + "=" * 56)
    print("結論：")
    ok_cal = abs(noise["psig"] - 0.05) < 0.05
    ok_fp = noise["fdr"] <= 1
    ok_pw = inj["fdr"] >= 20
    print(f"  [{'✅' if ok_cal else '❌'}] 校正性：噪音 p<0.05 命中率 = {noise['psig']*100:.0f}% (目標≈5%)")
    print(f"  [{'✅' if ok_fp else '❌'}] 假陽性：噪音 FDR 後通過 = {noise['fdr']}% (目標≈0%)")
    print(f"  [{'✅' if ok_pw else '❌'}] 檢定力：真edge FDR後通過 = {inj['fdr']}% (目標>20%)")
    print(f"  灰色地帶：漂移趨勢 FDR後通過 = {drift['fdr']}% "
          "（時機規則加唔到 value over 漂移，係誠實結果）")
    print("=" * 56)
