#!/usr/bin/env python3
"""Local signal pipeline: Yahoo chart data -> technical indicators JSON cache.

No LLM calls. Deterministic local computation for token savings.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def load_watchlist(path: Path) -> List[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        tickers = data.get("watchlist", [])
    elif isinstance(data, list):
        tickers = data
    else:
        raise ValueError("watchlist.json must be a list or object with 'watchlist' key")

    cleaned = []
    for t in tickers:
        if not isinstance(t, str):
            continue
        symbol = t.strip().upper()
        if symbol:
            cleaned.append(symbol)
    return cleaned


def fetch_chart(ticker: str, interval: str = "1d", range_: str = "1y") -> dict:
    params = urllib.parse.urlencode({"interval": interval, "range": range_})
    url = YAHOO_CHART_URL.format(ticker=urllib.parse.quote(ticker)) + f"?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (local-signal-pipeline)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def compact_series(*series: List[Optional[float]]) -> List[Tuple[float, ...]]:
    out: List[Tuple[float, ...]] = []
    for row in zip(*series):
        if any(v is None for v in row):
            continue
        out.append(tuple(float(v) for v in row))
    return out


def sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema_series(values: List[float], period: int) -> List[float]:
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    seed = sum(values[:period]) / period
    out = [seed]
    for price in values[period:]:
        out.append(price * k + out[-1] * (1 - k))
    return out


def rsi14(closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) <= period:
        return None
    gains = []
    losses = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(closes: List[float]) -> Dict[str, Optional[float]]:
    ema12 = ema_series(closes, 12)
    ema26 = ema_series(closes, 26)
    if not ema12 or not ema26:
        return {"macd": None, "signal": None, "hist": None}

    # Align ema12 to ema26 timeline
    offset = len(ema12) - len(ema26)
    ema12_aligned = ema12[offset:]
    macd_line = [a - b for a, b in zip(ema12_aligned, ema26)]
    signal_line = ema_series(macd_line, 9)
    if not signal_line:
        last_macd = macd_line[-1] if macd_line else None
        return {"macd": last_macd, "signal": None, "hist": None}

    hist = macd_line[-1] - signal_line[-1]
    return {"macd": macd_line[-1], "signal": signal_line[-1], "hist": hist}


def atr14(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) <= period:
        return None
    tr: List[float] = []
    for i in range(1, len(closes)):
        h = highs[i]
        l = lows[i]
        prev_c = closes[i - 1]
        tr.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))

    if len(tr) < period:
        return None

    atr = sum(tr[:period]) / period
    for value in tr[period:]:
        atr = (atr * (period - 1) + value) / period
    return atr


def compute_for_ticker(ticker: str, range_: str) -> dict:
    try:
        payload = fetch_chart(ticker, range_=range_)
        result = payload.get("chart", {}).get("result", [])
        if not result:
            raise ValueError("No chart result")

        r0 = result[0]
        quote = (r0.get("indicators", {}).get("quote", [{}]) or [{}])[0]
        rows = compact_series(
            [safe_float(x) for x in quote.get("open", [])],
            [safe_float(x) for x in quote.get("high", [])],
            [safe_float(x) for x in quote.get("low", [])],
            [safe_float(x) for x in quote.get("close", [])],
            [safe_float(x) for x in quote.get("volume", [])],
        )
        if not rows:
            raise ValueError("No valid OHLCV rows")

        opens = [r[0] for r in rows]
        highs = [r[1] for r in rows]
        lows = [r[2] for r in rows]
        closes = [r[3] for r in rows]
        volumes = [r[4] for r in rows]

        macd_vals = macd(closes)

        return {
            "ok": True,
            "latest": {
                "open": opens[-1],
                "high": highs[-1],
                "low": lows[-1],
                "close": closes[-1],
                "volume": volumes[-1],
            },
            "indicators": {
                "sma20": sma(closes, 20),
                "sma50": sma(closes, 50),
                "rsi14": rsi14(closes, 14),
                "macd": macd_vals,
                "atr14": atr14(highs, lows, closes, 14),
            },
            "samples": len(rows),
        }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:  # safety net
        return {"ok": False, "error": f"Unexpected error: {e}"}


def round_floats(obj):
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {k: round_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [round_floats(v) for v in obj]
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate local technical signals from Yahoo chart API")
    parser.add_argument("--watchlist", default="watchlist.json", help="Path to watchlist JSON")
    parser.add_argument("--output", default="data/cache/signals_local.json", help="Output JSON path")
    parser.add_argument("--range", default="1y", help="Yahoo chart range, e.g. 6mo, 1y")
    parser.add_argument("--sleep-ms", type=int, default=120, help="Sleep between ticker requests")
    args = parser.parse_args()

    watchlist_path = Path(args.watchlist)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    tickers = load_watchlist(watchlist_path)
    signals: Dict[str, dict] = {}

    for i, ticker in enumerate(tickers):
        signals[ticker] = compute_for_ticker(ticker, range_=args.range)
        if i < len(tickers) - 1 and args.sleep_ms > 0:
            time.sleep(args.sleep_ms / 1000)

    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "yahoo_chart_v8",
        "count": len(tickers),
        "signals": round_floats(signals),
    }

    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} ({len(tickers)} tickers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
