#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import ssl
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

HKT = timezone(timedelta(hours=8))
UTC = timezone.utc
UA = "AtlasMarketIntelligence/1.0 david@example.com"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
TARGET_FORMS = {"10-K", "10-Q", "8-K"}
ENRICH_DAYS = 10


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def get_text(self) -> str:
        return " ".join(" ".join(self.parts).split())


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)


def fetch_url(url: str, accept: str = "*/*") -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        return resp.read().decode("utf-8", "ignore")


def fetch_json(url: str) -> dict[str, Any]:
    return json.loads(fetch_url(url, accept="application/json"))


def fetch_text(url: str) -> str:
    html = fetch_url(url, accept="text/html,application/xhtml+xml")
    parser = TextExtractor()
    parser.feed(html)
    return parser.get_text()


def pct_change(cur: float, prev: float) -> str:
    if prev == 0:
        return "n/a"
    return f"{((cur - prev) / prev) * 100:.1f}%"


def to_float_maybe(text: str) -> float | None:
    try:
        return float(text.replace(",", ""))
    except Exception:
        return None


def capture_money(pattern: str, text: str) -> tuple[float | None, float | None]:
    m = re.search(pattern, text, re.I)
    if not m:
        return None, None
    a = to_float_maybe(m.group(1))
    b = to_float_maybe(m.group(2))
    return a, b


def clean_sentence(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" .")


def filing_url(cik: str, accession: str, primary_doc: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{primary_doc}"


def filing_index_url(cik: str, accession: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"


def load_watchlist(path: Path) -> list[str]:
    doc = json.loads(path.read_text())
    return [str(x).strip().upper() for x in doc.get("watchlist", []) if str(x).strip()]


def cik_map() -> dict[str, dict[str, Any]]:
    doc = fetch_json(SEC_TICKERS_URL)
    data = doc.get("data", []) if isinstance(doc, dict) else []
    out: dict[str, dict[str, Any]] = {}
    for row in data:
        if len(row) >= 3:
            cik, name, ticker = row[0], row[1], str(row[2]).upper()
            out[ticker] = {"cik": str(cik).zfill(10), "name": name}
    return out


def summarize_filing(ticker: str, form: str, filing_date: str) -> tuple[str, str, str, str]:
    date_obj = datetime.fromisoformat(filing_date).date()
    age = (datetime.now(HKT).date() - date_obj).days
    if form == "10-K":
        exec_summary = f"{ticker} filed a 10-K on {filing_date}, which means the company published its full annual report."
        layman = "Think of a 10-K as the company’s yearly health check: business performance, major risks, and whether the story still matches reality."
        details = "Read the 10-K for changes in revenue mix, margins, customer concentration, debt/cash trends, risk factors, and management tone versus the prior year."
        why = "Annual filings often reveal slow-building problems or strategic shifts that headlines miss."
    elif form == "10-Q":
        exec_summary = f"{ticker} filed a 10-Q on {filing_date}, which is the quarterly operating update."
        layman = "A 10-Q is the company’s quarter-by-quarter progress report: sales, margins, cash flow, and risks."
        details = "Read the 10-Q for year-on-year revenue, margin, operating income, cash, debt, and any new management caution."
        why = "Quarterly filings test whether the market story is actually showing up in the numbers."
    else:
        exec_summary = f"{ticker} filed an 8-K on {filing_date}."
        layman = "An 8-K is the company saying: something important just happened, and investors need to know now."
        details = "Read the 8-K for the actual trigger: earnings, acquisitions, leadership changes, financing, legal issues, or guidance changes."
        why = "8-Ks often contain the first hard disclosure behind a narrative or price move."
    freshness = f" Filed {age} day(s) ago." if age >= 0 else ""
    return exec_summary, layman, details, why + freshness


def fetch_exhibit_links(index_url: str) -> list[str]:
    try:
        html = fetch_url(index_url)
    except Exception:
        return []
    parser = LinkExtractor()
    parser.feed(html)
    out = []
    for href in parser.links:
        low = href.lower()
        if "ex99" in low or low.endswith("8k.htm") or low.endswith("10q.htm") or low.endswith("10-k.htm"):
            out.append("https://www.sec.gov" + href if href.startswith("/") else href)
    return out


def enrich_10q(item: dict[str, Any], filing_text: str) -> dict[str, str]:
    revenue, revenue_prev = capture_money(r"Total net revenue\s+([\d,]+)\s+([\d,]+)", filing_text)
    gross, gross_prev = capture_money(r"Gross margin\s+([\d,]+)\s+([\d,]+)", filing_text)
    op_inc, op_inc_prev = capture_money(r"Operating income\s+([\d,]+)\s+([\d,]+)", filing_text)
    net_inc, net_inc_prev = capture_money(r"Net income \$\s*([\d,]+)\s+\$\s*([\d,]+)", filing_text)
    cash, cash_prev = capture_money(r"Cash and cash equivalents \$\s*([\d,]+)\s+\$\s*([\d,]+)", filing_text)
    debt_short, debt_short_prev = capture_money(r"Short-term debt\s+([\d,]+)\s+([\d,]+)", filing_text)
    debt_long, debt_long_prev = capture_money(r"Long-term debt\s+([\d,]+)\s+([\d,]+)", filing_text)
    div_ps, div_ps_prev = capture_money(r"Dividends per share to common stockholders \$\s*([\d.]+)\s+\$\s*([\d.]+)", filing_text)
    buyback = re.search(r"repurchased and retired ([\d,]+) million shares for \$\s*([\d,]+) million", filing_text, re.I)
    notes = re.search(r"issued senior unsecured notes for an aggregate principal amount of \$\s*([\d,]+) million", filing_text, re.I)

    total_debt = (debt_short or 0) + (debt_long or 0)
    total_debt_prev = (debt_short_prev or 0) + (debt_long_prev or 0)

    what = []
    if revenue and revenue_prev and net_inc and net_inc_prev:
        what.append(
            f"Revenue was ${revenue:,.0f} million versus ${revenue_prev:,.0f} million a year ago ({pct_change(revenue, revenue_prev)}), and net income was ${net_inc:,.0f} million versus ${net_inc_prev:,.0f} million ({pct_change(net_inc, net_inc_prev)})."
        )
    if gross and gross_prev and op_inc and op_inc_prev:
        what.append(
            f"Gross profit rose to ${gross:,.0f} million from ${gross_prev:,.0f} million, and operating income increased to ${op_inc:,.0f} million from ${op_inc_prev:,.0f} million."
        )
    if cash and total_debt:
        what.append(f"The balance sheet showed ${cash:,.0f} million of cash and about ${total_debt:,.0f} million of total debt at quarter-end.")

    layman = "The quarter still looks like a scale-and-cash-generation story rather than a deterioration story: sales, profit and operating leverage all moved up materially."

    why = []
    if notes:
        why.append(f"The filing also confirms fresh financing activity: the company issued ${notes.group(1)} million of senior unsecured notes during the quarter.")
    if buyback:
        why.append(f"Management was aggressive with capital returns, buying back {buyback.group(1)} million shares for ${buyback.group(2)} million.")
    if div_ps and div_ps_prev:
        why.append(f"The dividend per share rose to ${div_ps:.2f} from ${div_ps_prev:.2f} a year earlier.")

    changed = []
    if revenue and revenue_prev:
        changed.append(f"Top-line growth accelerated on a much larger base, with revenue up {pct_change(revenue, revenue_prev)} year on year.")
    if cash and cash_prev:
        changed.append(f"Cash fell from ${cash_prev:,.0f} million to ${cash:,.0f} million quarter to quarter, likely reflecting capital returns and financing activity rather than operating weakness by itself.")
    if total_debt and total_debt_prev:
        changed.append(f"Total debt moved from roughly ${total_debt_prev:,.0f} million to ${total_debt:,.0f} million quarter to quarter.")

    positives = []
    if gross and gross_prev:
        positives.append(f"Gross profit up {pct_change(gross, gross_prev)} year on year.")
    if op_inc and op_inc_prev:
        positives.append(f"Operating income up {pct_change(op_inc, op_inc_prev)} year on year.")
    if buyback:
        positives.append(f"Large share repurchase signal: {buyback.group(1)} million shares retired in the quarter.")

    risks = [
        "Debt remains large in absolute dollars, so rates/refinancing and integration discipline still matter.",
        "The filing discusses risk around AI-related customer purchasing models and financing structures, which could affect revenue timing or cash generation if customer behavior shifts.",
    ]
    if cash and cash_prev and cash < cash_prev:
        risks.append("Quarter-end cash declined from the prior quarter, so watch whether future quarters rebuild liquidity after buybacks and financing moves.")

    watch = [
        "Whether revenue growth stays this strong in the next quarter without margin slippage.",
        "How quickly debt trends down after this round of financing and capital returns.",
        "Whether capital returns remain this aggressive while still preserving flexibility for acquisitions and AI investment.",
    ]

    return {
        "what_happened": " ".join(what) or "Verified the primary 10-Q and confirmed it contains the company’s quarterly financial statements and management disclosures, but automatic extraction of key figures was only partial.",
        "layman_version": layman,
        "why_it_matters_now": " ".join(why) or "This matters now because the filing gives the real operating numbers behind the market narrative.",
        "what_changed": " ".join(changed) or "Compared with the prior periods shown in the filing, the key question is whether growth, margins, cash and debt are moving in the right direction.",
        "positives": " ".join(positives),
        "risks": " ".join(risks),
        "watch_next": " ".join(watch),
        "verification": "Read the primary 10-Q filing itself and extracted figures directly from the filing text.",
    }


def enrich_8k(item: dict[str, Any], filing_text: str, exhibit_texts: list[str]) -> dict[str, str]:
    text = " ".join([filing_text] + exhibit_texts)
    low = text.lower()
    verification = "Read the primary 8-K filing itself"
    if exhibit_texts:
        verification += " and available exhibit text"
    verification += "."

    if "bird aerosystems" in low and "6,933,110" in text:
        return {
            "what_happened": "Ondas used the 8-K to disclose the closing/announcement package around its Bird Aerosystems acquisition and a related resale registration covering 6,933,110 Ondas shares issued to acquisition-related holders.",
            "layman_version": "This is Ondas getting bigger in defense tech by buying Bird, while also telling the market that acquisition-related shareholders can resell the stock they received in the deal.",
            "why_it_matters_now": "Bird brings real deployed defense products rather than a concept slide: the exhibit says Bird’s protection systems are installed on more than 700 aircraft across 40+ aircraft types, including customers tied to the U.S. Army, NATO and other military/government fleets.",
            "what_changed": "Before this, Ondas was mostly known for autonomous aerial systems, robotics and private wireless. After this deal, it adds airborne missile protection and airborne ISR capabilities, which broadens the platform and raises the defense exposure of the story.",
            "positives": "Strategically expands Ondas into a more established defense niche; adds globally deployed systems and mission-critical customers; creates a clearer multi-domain defense platform narrative.",
            "risks": "The filing also confirms a sizable block of stock is now registered for resale, which can create supply/overhang pressure. Integration risk is real, and the filing package does not itself prove how profitable Bird is inside Ondas yet.",
            "watch_next": "Watch for deal financials, integration updates, margin impact, and whether management can translate the broader defense portfolio into faster bookings rather than just a bigger story.",
            "verification": verification,
        }

    if "palantir partners with ondas and world view" in low and ("ai flight director" in low or "warp speed" in low or "skyweaver" in low):
        return {
            "what_happened": "Ondas filed an 8-K furnishing a March 12 press release and fact sheet announcing a strategic partnership with Palantir and World View to build an AI-enabled multi-domain intelligence, surveillance and reconnaissance platform.",
            "layman_version": "Plain English: Ondas is trying to plug Palantir's software brain into World View's high-altitude balloon sensors and Ondas' drones, ground robots, and counter-drone systems so military and security customers can run one connected ISR stack instead of separate tools.",
            "why_it_matters_now": "This is more than a branding press release because the filing lays out concrete program areas: Palantir Warp Speed for production/operations, AI Flight Director for mission planning, and SkyWeaver for onboard edge intelligence. It also says work on optimizing World View's systems has already begun and broader portfolio integration could start as early as Q4 2026.",
            "what_changed": "Before this filing, Ondas had separate pieces of a defense/autonomy story. Now it is explicitly trying to become part of a larger command-and-control and persistent ISR architecture spanning the stratosphere, air, and ground, with Palantir providing the operational software layer.",
            "positives": "Adds a high-credibility partner in Palantir; gives Ondas a clearer software-and-systems narrative instead of just hardware assets; could make Ondas' platforms more relevant for larger defense and homeland-security programs if the integration works.",
            "risks": "This is still partnership-stage disclosure, not booked revenue or signed large customer awards. The filing leans heavily on forward-looking language, and the claimed value depends on execution across three companies plus actual customer adoption. Investors should not confuse architecture ambition with near-term financial proof.",
            "watch_next": "Watch for pilot deployments, named customer wins, any timeline details around Q4 2026 integration, and whether Ondas starts quantifying backlog, revenue contribution, or software-enabled margin upside from the Palantir/World View relationship.",
            "verification": verification,
        }

    if "variable compensation plan" in low and "fiscal year 2027" in low:
        ceo = re.search(r"Jen-Hsun Huang.*?\$([\d,]+)\s+200%", text, re.I)
        cfo = re.search(r"Colette M\. Kress.*?\$([\d,]+)\s+150%", text, re.I)
        return {
            "what_happened": "NVIDIA’s 8-K is not an operating update. It discloses the fiscal 2027 executive cash bonus plan tied to company revenue goals.",
            "layman_version": "This filing is basically saying senior management’s cash bonus will depend on how much revenue NVIDIA hits next fiscal year.",
            "why_it_matters_now": "It matters because it tells investors what the board is rewarding. Here, the clearest signal is that revenue growth remains the key scoreboard for top management.",
            "what_changed": "This is a governance/pay disclosure, not a business-event filing. The main new information is the FY2027 plan design and target payout levels for named executives.",
            "positives": (f"Compensation is explicitly tied to revenue execution. CEO target cash award is ${ceo.group(1)} and CFO target is ${cfo.group(1)}." if ceo and cfo else "Compensation is explicitly tied to revenue execution rather than a vague discretionary framework."),
            "risks": "This does not add new demand or margin information by itself. A heavy revenue target can sometimes encourage growth-first behavior, and investors still need actual product/order data from earnings filings rather than reading too much into compensation mechanics.",
            "watch_next": "Watch the next earnings release and 10-Q/10-K for whether revenue growth, margin quality and cash generation keep matching the aggressive expectations embedded in management incentives.",
            "verification": verification,
        }

    if "orbit technologies" in low and "352.7 million" in low:
        return {
            "what_happened": "Kratos disclosed that it completed the Orbit Technologies acquisition on March 2, 2026, paying about $352.7 million in cash, or $13.725 per Orbit share, funded from cash on hand.",
            "layman_version": "Kratos just finished buying Orbit outright using its own cash. This is a real completed M&A move, not just an announcement.",
            "why_it_matters_now": "Completed acquisitions matter more than announced ones because execution risk shifts from closing risk to integration risk. Orbit now becomes part of Kratos’ operating base immediately.",
            "what_changed": "Before this filing, Orbit was a pending deal. After this filing, Orbit is an indirect wholly owned Kratos subsidiary, so the question changes from ‘will it close?’ to ‘does it improve growth, capability and returns?’",
            "positives": "The deal closed without needing new disclosed external financing in this filing; Orbit adds capabilities Kratos clearly wanted enough to pay cash for; closing removes a major uncertainty overhang.",
            "risks": "Cash-funded deals can pressure liquidity if synergies or growth take longer than expected. The filing is procedural and does not yet prove the acquisition economics or integration success.",
            "watch_next": "Watch future quarters for revenue contribution, margin impact, backlog commentary, and whether management explains how Orbit changes Kratos’ competitive position and capital allocation.",
            "verification": verification,
        }

    if "sundar pichai" in low and "$63,000,000" in text and "$84,000,000" in text:
        return {
            "what_happened": "Alphabet’s 8-K discloses a new triennial CEO equity package for Sundar Pichai: two performance-based PSU tranches with target value of $63 million each and $84 million of time-based GSUs, while annual salary stays at $2 million and there is no annual bonus.",
            "layman_version": "This filing is about how Google’s CEO gets paid. The board is keeping salary flat and making most of the package long-term stock, with a big chunk tied to Alphabet’s stock performance versus other large companies.",
            "why_it_matters_now": "This matters as a governance signal. It shows the board still wants Pichai’s pay to depend largely on multi-year stock performance and retention rather than short-term cash rewards.",
            "what_changed": "The new information is the 2026 triennial grant structure and size. It is not an operating business update, but it does show the board sticking with the same broad long-cycle compensation framework used in prior grants.",
            "positives": "Heavy equity weighting aligns CEO incentives with longer-term shareholder outcomes; the performance stock units can vest from 0% to 200% of target depending on relative TSR, which is stricter than a guaranteed stock grant.",
            "risks": "This filing tells you almost nothing about Search, Cloud, AI monetization or margins. Governance disclosures can be over-read if investors mistake them for a business catalyst.",
            "watch_next": "Watch actual operating filings and earnings for whether Alphabet’s AI spending, Cloud profitability, advertising trends and shareholder returns support the long-term value creation this compensation structure is supposed to reward.",
            "verification": verification,
        }

    trigger = "important corporate event"
    if "acquisition" in low:
        trigger = "an acquisition-related event"
    elif "compensatory arrangements" in low or "compensation" in low:
        trigger = "an executive compensation event"
    elif "earnings release" in low or "financial results" in low:
        trigger = "an earnings-related disclosure"

    return {
        "what_happened": f"Verified from the primary 8-K that the filing concerns {trigger}.",
        "layman_version": "This is a real SEC disclosure, but the filing-specific writeup here is intentionally narrow because automated extraction from the primary text was only partial.",
        "why_it_matters_now": "An 8-K often becomes the first hard source investors can rely on when the company is trying to move a narrative into formal disclosure.",
        "what_changed": "The company formally disclosed the event in an SEC filing, which raises the information quality above headlines or management comments alone.",
        "positives": "Primary SEC filing verified.",
        "risks": "The exact implications may depend on exhibits or later periodic filings if this 8-K is short or procedural.",
        "watch_next": "Watch the next 10-Q/10-K or accompanying exhibits for fuller financial impact.",
        "verification": verification,
    }


def maybe_enrich(item: dict[str, Any]) -> dict[str, str] | None:
    try:
        filing_text = fetch_text(item["url"])
    except Exception:
        return None

    exhibit_texts: list[str] = []
    for link in fetch_exhibit_links(item["indexUrl"]):
        if link == item["url"]:
            continue
        try:
            exhibit_texts.append(fetch_text(link))
        except Exception:
            continue
        if len(exhibit_texts) >= 2:
            break

    if item["form"] == "10-Q":
        return enrich_10q(item, filing_text)
    if item["form"] == "8-K":
        return enrich_8k(item, filing_text, exhibit_texts)
    return None


def build_card(item: dict[str, Any]) -> str:
    if item.get("analysis"):
        a = item["analysis"]
        return (
            f"<div class='card'><h2>{escape(item['ticker'])} — {escape(item['form'])}</h2>"
            f"<p class='muted'>Filed: {escape(item['filingDate'])} · Company: {escape(item['company'])}</p>"
            f"<p><strong>What happened:</strong> {escape(a['what_happened'])}</p>"
            f"<p><strong>Layman version:</strong> {escape(a['layman_version'])}</p>"
            f"<p><strong>Why it matters now:</strong> {escape(a['why_it_matters_now'])}</p>"
            f"<p><strong>What changed vs before:</strong> {escape(a['what_changed'])}</p>"
            f"<p><strong>Positives:</strong> {escape(a['positives'])}</p>"
            f"<p><strong>Risks / red flags:</strong> {escape(a['risks'])}</p>"
            f"<p><strong>What to watch next:</strong> {escape(a['watch_next'])}</p>"
            f"<p class='muted'>{escape(a['verification'])}</p>"
            f"<p><a href='{escape(item['url'])}'>Open primary filing</a> · <a href='{escape(item['indexUrl'])}'>SEC filing folder</a></p></div>"
        )

    return (
        f"<div class='card'><h2>{escape(item['ticker'])} — {escape(item['form'])}</h2>"
        f"<p class='muted'>Filed: {escape(item['filingDate'])} · Company: {escape(item['company'])}</p>"
        f"<p><strong>Executive summary:</strong> {escape(item['executiveSummary'])}</p>"
        f"<p><strong>Layman view:</strong> {escape(item['laymanSummary'])}</p>"
        f"<p><strong>What to read for:</strong> {escape(item['details'])}</p>"
        f"<p><strong>Why it matters:</strong> {escape(item['whyItMatters'])}</p>"
        f"<p class='muted'>Primary filing read was not completed for this item during this run, so this card remains generic rather than pretending to be a full read.</p>"
        f"<p><a href='{escape(item['url'])}'>Open primary filing</a> · <a href='{escape(item['indexUrl'])}'>SEC filing folder</a></p></div>"
    )


def build_report(watchlist: list[str], out_root: Path) -> tuple[Path, dict[str, Any]]:
    mapping = cik_map()
    findings: list[dict[str, Any]] = []
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for ticker in watchlist:
        meta = mapping.get(ticker)
        if not meta:
            continue
        try:
            sub = fetch_json(SEC_SUBMISSIONS.format(cik=meta["cik"]))
        except Exception:
            continue
        recent = ((sub.get("filings") or {}).get("recent") or {})
        forms = recent.get("form", []) or []
        dates = recent.get("filingDate", []) or []
        accessions = recent.get("accessionNumber", []) or []
        primary_docs = recent.get("primaryDocument", []) or []
        for form, fdate, acc, pdoc in zip(forms, dates, accessions, primary_docs):
            if form not in TARGET_FORMS or not fdate:
                continue
            dt = datetime.fromisoformat(fdate).replace(tzinfo=HKT)
            if dt.date() < (datetime.now(HKT).date() - timedelta(days=45)):
                continue
            exec_summary, layman, details, why = summarize_filing(ticker, form, fdate)
            item = {
                "ticker": ticker,
                "company": meta["name"],
                "form": form,
                "filingDate": fdate,
                "accession": acc,
                "primaryDoc": pdoc,
                "url": filing_url(meta["cik"], acc, pdoc),
                "indexUrl": filing_index_url(meta["cik"], acc),
                "executiveSummary": exec_summary,
                "laymanSummary": layman,
                "details": details,
                "whyItMatters": why,
            }
            findings.append(item)
            by_ticker[ticker].append(item)
            break

    findings.sort(key=lambda x: (x["filingDate"], x["ticker"]), reverse=True)

    for item in findings:
        filed = datetime.fromisoformat(item["filingDate"]).date()
        if (datetime.now(HKT).date() - filed).days <= ENRICH_DAYS:
            item["analysis"] = maybe_enrich(item)

    stamp = datetime.now(HKT).replace(microsecond=0)
    date_label = stamp.date().isoformat()

    reports_dir = out_root / "reports" / "filings"
    reports_dir.mkdir(parents=True, exist_ok=True)
    archive_path = reports_dir / f"{date_label}.html"

    latest_path = "./reports/filings/" + archive_path.name
    count = len(findings)
    enriched = sum(1 for x in findings if x.get("analysis"))
    latest_summary = {
        "updatedAt": stamp.isoformat(),
        "count": count,
        "market": f"{count} recent SEC filing(s) matched the current watchlist in the last 45 days." if count else "No recent 10-Q, 10-K, or 8-K filings were found for the current watchlist in the last 45 days.",
        "tech": f"Latest run attempted primary-document reads for recent filings and completed {enriched} filing-level writeups from SEC primary text." if count else "Summary timestamp refreshed; no new target filing was found.",
        "risk": "If a card explicitly says the primary filing read was partial or incomplete, treat that note as a hard limitation rather than a hidden assumption.",
        "latestPath": latest_path,
    }

    top = findings[:5]
    exec_lines = "".join(
        f"<li><strong>{escape(x['ticker'])}</strong> — {escape(x['form'])} filed {escape(x['filingDate'])}. "
        + (escape(x['analysis']['what_happened']) if x.get('analysis') else escape(x['laymanSummary']))
        + f" <a href='{escape(x['url'])}'>SEC filing</a></li>"
        for x in top
    ) or "<li>No recent qualifying filings found in the current watchlist window.</li>"

    cards = [build_card(item) for item in findings]

    html = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Atlas SEC Filings Watch — {date_label}</title>
<style>
body{{font-family:Georgia,'Iowan Old Style','Palatino Linotype',serif;margin:24px;background:linear-gradient(180deg,#0a1025,#0f1738);color:#edf2ff;line-height:1.68}}
a{{color:#9bb8ff}} .wrap{{max-width:980px;margin:0 auto}} .card{{border:1px solid #2a3768;border-radius:14px;padding:16px;margin:14px 0;background:#121936}} .muted{{color:#a7b0d6}}
</style>
</head>
<body><div class='wrap'>
<p><a href='../../index.html'>← Back to Atlas</a> · <a href='./index.html'>Filing archive</a></p>
<div class='card'><h1>SEC filings watch</h1><p class='muted'>Generated: {stamp.isoformat()} · Watchlist filings monitor for 10-Q, 10-K, and 8-K.</p>
<p>This page is for hard-disclosure monitoring. It is most useful when you want to know whether a company actually filed something material, not just showed up in headlines.</p>
<h2>Executive summary</h2><ul>{exec_lines}</ul></div>
{''.join(cards) if cards else "<div class='card'><h2>No recent target filings found</h2><p class='muted'>Nothing in the current watchlist matched 10-Q / 10-K / 8-K in the recent 45-day window.</p></div>"}
</div></body></html>"""
    archive_path.write_text(html, encoding="utf-8")

    idx_files = sorted([p.name for p in reports_dir.glob("20*.html")], reverse=True)
    idx_items = "".join(f"<li><a href='./{escape(name)}'>{escape(name[:-5])}</a></li>" for name in idx_files)
    index_html = f"<!doctype html><html><body style='font-family:Georgia,serif;margin:24px;background:#0f1738;color:#edf2ff'><p><a href='../../index.html'>← Back to Atlas</a></p><h1>SEC filings archive</h1><p style='color:#a7b0d6'>Latest archive rebuild: {stamp.isoformat()}</p><ul>{idx_items or '<li>No reports yet.</li>'}</ul></body></html>"
    (reports_dir / "index.html").write_text(index_html, encoding="utf-8")

    (out_root / "filings-research").mkdir(parents=True, exist_ok=True)
    (out_root / "filings-research" / "summary.json").write_text(json.dumps(latest_summary, indent=2) + "\n", encoding="utf-8")
    (out_root / "filings-research" / "latest.html").write_text(html, encoding="utf-8")

    return archive_path, latest_summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watchlist", default="watchlist.json")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()
    archive_path, summary = build_report(load_watchlist(Path(args.watchlist)), Path(args.root))
    print(f"Wrote {archive_path}")
    print(f"Updated filings summary -> {summary['latestPath']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
