#!/usr/bin/env python3
"""Build ticker-level news digest from Google News RSS with simple impact heuristics."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import email.utils
import xml.etree.ElementTree as ET


def _load_watchlist(path: str) -> list[str]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    wl = doc.get("watchlist") if isinstance(doc, dict) else None
    if not isinstance(wl, list) or not wl:
        raise ValueError(f"Invalid watchlist: {path}")
    return [str(x).strip().upper() for x in wl if str(x).strip()]


def _load_company_names(path: str) -> dict[str, str]:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        tickers = (doc.get("tickers") or {}) if isinstance(doc, dict) else {}
        return {k: str((v or {}).get("company") or k) for k, v in tickers.items()}
    except Exception:
        return {}


def _parse_pubdate(s: str | None) -> str | None:
    if not s:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hkt = timezone(timedelta(hours=8))
        return dt.astimezone(hkt).replace(microsecond=0).isoformat()
    except Exception:
        return None


def _impact_from_title(title: str) -> dict:
    t = title.lower()
    pos = ["beats", "beat", "raises guidance", "upgrade", "wins contract", "approval", "buyback", "surge"]
    neg = ["miss", "cuts guidance", "downgrade", "lawsuit", "probe", "sec", "recall", "warning", "plunge", "drop"]
    hi = ["earnings", "guidance", "merger", "acquisition", "lawsuit", "probe", "sec", "contract", "tariff", "ban", "export"]

    sentiment = "neutral"
    if any(k in t for k in pos):
        sentiment = "positive"
    if any(k in t for k in neg):
        sentiment = "negative"

    severity = "low"
    if any(k in t for k in hi):
        severity = "high"
    elif sentiment != "neutral":
        severity = "medium"

    return {"sentiment": sentiment, "severity": severity}


def _ticker_query(ticker: str, company: str) -> str:
    base_t = ticker.replace(".", " ")
    return f"{company} OR {base_t} stock"


def fetch_news(query: str, max_items: int) -> list[dict]:
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=20) as r:
        raw = r.read()
    root = ET.fromstring(raw)
    ch = root.find("channel")
    items = []
    if ch is None:
        return items
    for it in ch.findall("item")[:max_items]:
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = _parse_pubdate(it.findtext("pubDate"))
        src_node = it.find("source")
        source = (src_node.text or "").strip() if src_node is not None and src_node.text else None
        impact = _impact_from_title(title)
        items.append({
            "title": title,
            "url": link,
            "published_hkt": pub,
            "source": source,
            "impact": impact,
        })
    return items


def summarize(items: list[dict]) -> dict:
    pos = sum(1 for x in items if (x.get("impact") or {}).get("sentiment") == "positive")
    neg = sum(1 for x in items if (x.get("impact") or {}).get("sentiment") == "negative")
    hi = sum(1 for x in items if (x.get("impact") or {}).get("severity") == "high")

    if neg > pos and hi >= 1:
        label = "Caution — negative-news skew"
    elif pos > neg and hi >= 1:
        label = "Constructive — positive-news skew"
    elif hi >= 1:
        label = "Watch — high-impact headlines present"
    else:
        label = "Neutral — no strong catalyst signal"

    return {
        "label": label,
        "positive_count": pos,
        "negative_count": neg,
        "high_impact_count": hi,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watchlist", default="watchlist.json")
    ap.add_argument("--fundamentals", default="data/pilot_fundamentals.json")
    ap.add_argument("--output", default="data/cache/ticker_news_digest.json")
    ap.add_argument("--max-items", type=int, default=5)
    args = ap.parse_args()

    wl = _load_watchlist(args.watchlist)
    names = _load_company_names(args.fundamentals)

    hkt = timezone(timedelta(hours=8))
    out = {
        "generated_at": datetime.now(hkt).replace(microsecond=0).isoformat(),
        "source_note": "Google News RSS + heuristic impact scoring (title-based).",
        "tickers": {},
    }

    for t in wl:
        company = names.get(t, t)
        query = _ticker_query(t, company)
        try:
            items = fetch_news(query, args.max_items)
        except Exception:
            items = []
        out["tickers"][t] = {
            "query": query,
            "summary": summarize(items),
            "items": items,
        }
        print(f"news {t}: {len(items)} item(s)")

    p = Path(args.output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
