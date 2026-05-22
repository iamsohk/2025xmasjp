#!/usr/bin/env python3
"""
J Law Screener — Flask web server
Usage: python3 app.py [port]   (default: 8000)
"""

import json, sys
from flask import Flask, jsonify, request, send_from_directory
from jlaw_screener import (
    UNIVERSE_SP500_TOP50,
    get_candles, market_status,
    analyse, fill_rs_ranks, apply_market_status, mark_buy_rules,
)

app = Flask(__name__, static_folder=".", static_url_path="")


@app.route("/")
def index():
    return send_from_directory(".", "screener.html")


@app.route("/api/market")
def api_market():
    benchmark = request.args.get("benchmark", "SPY.US")
    status = market_status(benchmark)
    candles, _ = get_candles(benchmark, 10)
    latest = candles[-1] if candles else {}
    return jsonify({
        "status": status,
        "benchmark": benchmark,
        "price": latest.get("close"),
    })


@app.route("/api/scan", methods=["POST"])
def api_scan():
    body         = request.get_json() or {}
    symbols      = body.get("symbols", UNIVERSE_SP500_TOP50)
    benchmark    = body.get("benchmark", "SPY.US")
    account_size = float(body.get("account_size", 100_000))
    risk_pct     = float(body.get("risk_per_trade", 0.005))

    mstatus      = market_status(benchmark)
    bench_c, _   = get_candles(benchmark, 260)

    results = []
    for sym in symbols:
        results.append(analyse(sym, bench_c, account_size, risk_pct))

    fill_rs_ranks(results)
    apply_market_status(results, mstatus)
    mark_buy_rules(results, mstatus)

    return jsonify({"market_status": mstatus, "benchmark": benchmark, "results": results})


@app.route("/api/stock/<symbol>")
def api_stock(symbol):
    candles, source = get_candles(symbol, 260)
    if not candles:
        return jsonify({"error": "no data"}), 404
    return jsonify({"symbol": symbol, "source": source, "candles": candles[-52:]})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"[*] J Law Screener → http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
