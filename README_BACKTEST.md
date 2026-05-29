# 誠實回測引擎 (Honest Backtesting Engine)

> 一個唔會自己呃自己嘅選股回測系統。
> 核心唔係「揾到靚 pattern」，而係**證明嗰個 pattern 跑贏運氣**。

## 背景：點解要重寫

原本嘅 `soso_trader.py` 用簡單勝率門檻（`Win>=60% & Count>=30`）做篩選。一位
reviewer 做咗個實驗踢爆佢：**餵 100 隻純隨機（零 edge）嘅假股票入去，都有 ~16% 通過
「誠實回測」**，數字仲靚過真實股票。問題唔係嗰幾個 bug，而係 backtesting 本身嘅幻覺：

1. **In-sample 幻覺**：喺同一段歷史揾規律、又用同一段歷史驗證 = 睇住答案做卷。
2. **多重比較 (multiple testing)**：掃 100 隻 × 3 策略 = 300 次測試，純靠彩數都會有十幾廿次「碰啱」。
3. **backtest / live 對齊 bug**：`trend_strong` 只 check 最後一日，但訊號收集橫跨 3 年（包括當年唔喺強趨勢嘅日子）。

## 解決方案

`backtest_engine.py` —— 三個武器對應三個問題：

| 問題 | 武器 |
|------|------|
| backtest/live 對齊 | `trend_gate` **逐根 K 線**檢查，訊號收集同實盤入場條件一致 |
| in-sample 幻覺 | **Permutation test**：打散股票自己嘅 return 次序（保留分佈、destroy 時序），跑同一策略 N 次，計真實 expectancy 喺「純運氣分佈」入面嘅 p-value |
| 多重比較 | **Benjamini-Hochberg FDR** 校正整個候選家族 |

### Permutation test 嘅關鍵洞見

打散 return **保留咗股票自己嘅漂移（drift）**，只係打散咗「次序」。所以 p-value 問緊嘅係：

> 「你個入場時機規則，有冇 value 過『隻股票本身升咗』？」

一隻純粹係慢慢升嘅股票，時機規則加唔到 value → p ≈ 0.5 → **唔應該收貨**。
呢個正正係對付「靠 beta 扮 alpha」嘅照妖鏡。

止蝕統一用**收市價**（permutation 後盤中高低位冇意義，要 apples-to-apples）。

## 驗證結果（`validate_engine.py`）

100 隻合成股票 × Sniper MA20，780 日，n_perm=400，FDR=0.10：

| 輸入類型 | OLD filter 通過 | NEW (permutation+FDR) 通過 | p<0.05 命中率 |
|----------|----------------|---------------------------|--------------|
| **純噪音** (零 edge) | 4% ❌ 被呃 | **0%** ✅ | **5%**（= 名義值，完美校正）|
| **漂移趨勢** (有升幅冇時機 edge) | 4% | 0%（誠實：drift ≠ timing edge）| — |
| **真實時機 edge** (注入) | 24% ❌ 走漏 | **78%** ✅ | 68% |

**結論**：新引擎喺兩個維度都完勝舊版 ——
- 拒絕噪音：0% vs 4%
- 捕捉真 edge：78% vs 24%

舊版嘅 `Win>=60 & Payoff>=1.5` 硬門檻**同時**漏噪音入嚟、又擋真 edge 出去。

## 點樣跑

```bash
pip install numpy pandas
python3 validate_engine.py     # 跑噪音基準實驗，~6 分鐘
python3 soso_trader.py         # 實盤掃描（需 yfinance / 長橋 CLI 數據）
```

## 檔案

- `backtest_engine.py` — 引擎（指標 / 訊號 / 回測 / permutation / FDR）
- `validate_engine.py` — 噪音基準實驗（可重現上表）
- `soso_trader.py` — 蘇蘇指揮官 v5.0LB，已整合引擎
- `soso_colab.ipynb` — Google Colab 自包含版本

## 誠實聲明

- 本工具僅供學習 / 研究，唔構成投資建議。
- **空結果係好事**：如果某日掃描「冇任何 setup 通過統計顯著校正」，唔係 bug，
  係市場根本冇你想像中咁多 easy edge。一個成日叫你買嘅 scanner 多數係氹你；
  一個成日話「冇符合」嘅 scanner 先可能係誠實。
- Permutation test 證明嘅係「有冇序列結構 edge」，唔等於未來一定 work；
  歷史顯著 ≠ 未來保證。真正落注前請自行 out-of-sample 持續監察。
