"""تحلیل خبرها با Gemini: ترجمه، خلاصه، و اثر احتمالی روی هر دارایی.

اگر GEMINI_API_KEY تنظیم نشده باشد، یک برچسب‌زن ساده‌ی کلیدواژه‌ای جایش کار می‌کند
(بدون ترجمه و بدون جهت) تا بقیه‌ی سیستم قابل اجرا و آزمایش باشد.
"""
import json
import os
import random
import re
import time

import requests

from . import config
from .util import log

# اگر مدلی وجود نداشته باشد (404) خودکار از فهرست کنار گذاشته می‌شود.
# با متغیر GEMINI_MODELS (جداشده با کاما) می‌توانید فهرست را عوض کنید.
DEFAULT_MODELS = ["gemini-flash-latest", "gemini-3.8-flash", "gemini-3.7-flash",
                  "gemini-3.5-flash", "gemini-flash-lite-latest", "gemini-2.5-flash"]
# مدلی که آخرین بار جواب داده اول امتحان می‌شود تا وقت روی مدل‌های شلوغ تلف نشود.
# main.py این دو مقدار را در state.json نگه می‌دارد.
PREFERRED = None
LAST_OK = None
_API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_PROMPT = """You are a financial-markets news analyst for a Persian-language market radar \
covering crypto, forex, gold and oil. For every news item you receive, judge whether it matters \
to traders and how it is likely to affect the tracked assets.

Tracked assets (use ONLY these symbols):
__ASSETS__

Direction convention: "bullish" means the quoted price of that symbol is likely to RISE.
- EURUSD / GBPUSD bullish = euro / pound strengthens against the dollar.
- USDJPY bullish = dollar strengthens against the yen.
- DXY bullish = US dollar strengthens broadly.
- USDTIRT bullish = Iranian toman weakens (tether costs more tomans).

Return a JSON array with exactly one object per input item, in the same order:
{
  "i": <the item's index>,
  "relevant": true|false,
  "duplicate": true|false,
  "title_fa": "<fluent, neutral Persian headline, max 110 chars>",
  "summary_fa": ["<fact 1 in Persian>", "<fact 2 in Persian>"],
  "event_type": "<one of: __EVENT_TYPES__>",
  "impact": <integer 1-10, overall market importance>,
  "assets": [
    {"symbol": "<tracked symbol>", "direction": "bullish|bearish|neutral",
     "impact": <integer 1-10>, "horizon": "intraday|days|weeks",
     "confidence": <number 0-1>, "reason_fa": "<one short Persian sentence: why>"}
  ]
}

Rules:
- relevant=false for promotions, sponsored posts, giveaways, listicles, generic explainers, \
price-prediction clickbait, and stories with no bearing on the tracked assets. For those, the \
other fields may be empty.
- duplicate=true if the item reports the same event as a title in "recent_titles" or as an \
earlier item in this batch.
- List at most 3 assets, only those materially affected. An empty list is fine.
- When a story reports a price move that has ALREADY happened ("gold slips", "oil drops"), do not simply echo it. Judge whether the driver is likely to keep moving the price from here, and lower the confidence accordingly.
- Be conservative. Use "neutral" when the direction is unclear or already priced in. Never \
invent facts beyond the provided text. Confidence above 0.7 only for clear, direct, \
well-understood effects (e.g. a surprise rate decision).
- Impact scale: 9-10 market-wide shock (surprise central-bank move, major exchange collapse or \
hack, war escalation); 7-8 major data surprise, ETF/regulatory decision, large institutional \
move; 4-6 notable but contained; 1-3 routine commentary or technical analysis.
- Persian text must be natural and use standard financial terms. Keep tickers and proper \
names in Latin script where that is the norm (BTC, ETF, Fed, CPI).
- Output the JSON array only."""


def enabled():
    return bool(os.environ.get("GEMINI_API_KEY"))


def _models():
    custom = [m.strip() for m in os.environ.get("GEMINI_MODELS", "").split(",") if m.strip()]
    models = custom or list(DEFAULT_MODELS)
    if PREFERRED in models:
        models.remove(PREFERRED)
        models.insert(0, PREFERRED)
    return models


def _parse_json(text):
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


def _call_gemini(system_prompt, user_prompt):
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {"response_mime_type": "application/json", "temperature": 0.2},
    }
    headers = {"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json"}
    models = _models()
    for attempt in range(2):
        for model in list(models):
            try:
                resp = requests.post(_API.format(model=model), json=payload, headers=headers, timeout=60)
            except requests.RequestException as exc:
                log.warning("خطای شبکه در %s: %s", model, str(exc)[:100])
                continue
            if resp.status_code == 200:
                try:
                    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError, ValueError):
                    text = ""
                parsed = _parse_json(text)
                if isinstance(parsed, list):
                    global LAST_OK
                    LAST_OK = model
                    return parsed
                log.warning("خروجی %s قابل خواندن نبود", model)
            elif resp.status_code == 404:
                log.warning("مدل %s وجود ندارد؛ کنار گذاشته شد", model)
                models.remove(model)
            elif resp.status_code in (429, 500, 503):
                log.warning("مدل %s پاسخ %s داد؛ مدل بعدی", model, resp.status_code)
                time.sleep(2 + attempt * 3 + random.random())
            else:
                log.error("خطای Gemini %s در %s: %s", resp.status_code, model, resp.text[:200])
        if not models:
            break
    return None


def _clamp_int(value, low, high, default):
    try:
        return max(low, min(high, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _clean(result):
    """خروجی مدل را اعتبارسنجی می‌کند تا فقط مقادیر مجاز وارد داده‌ها شود."""
    assets, used = [], set()
    for a in result.get("assets") or []:
        if not isinstance(a, dict):
            continue
        symbol = str(a.get("symbol", "")).upper().strip()
        if symbol not in config.ASSET_BY_SYMBOL or symbol in used:
            continue
        used.add(symbol)
        direction = a.get("direction") if a.get("direction") in ("bullish", "bearish", "neutral") else "neutral"
        try:
            confidence = max(0.0, min(1.0, float(a.get("confidence", 0))))
        except (TypeError, ValueError):
            confidence = 0.0
        assets.append({
            "symbol": symbol,
            "direction": direction,
            "impact": _clamp_int(a.get("impact"), 1, 10, 3),
            "horizon": a.get("horizon") if a.get("horizon") in ("intraday", "days", "weeks") else "days",
            "confidence": round(confidence, 2),
            "reason_fa": str(a.get("reason_fa") or "")[:240],
        })
        if len(assets) == 3:
            break
    summary = result.get("summary_fa") or []
    if isinstance(summary, str):
        summary = [summary]
    return {
        "relevant": bool(result.get("relevant", True)),
        "duplicate": bool(result.get("duplicate", False)),
        "title_fa": str(result.get("title_fa") or "")[:160],
        "summary_fa": [str(s)[:300] for s in summary if s][:3],
        "event_type": result.get("event_type") if result.get("event_type") in config.EVENT_TYPES else "other",
        "impact": _clamp_int(result.get("impact"), 1, 10, 3),
        "assets": assets,
    }


def _analyze_gemini(candidates, recent_titles):
    asset_lines = "\n".join(f"- {a['symbol']}: {a['name_fa']} ({a['market']})" for a in config.ASSETS)
    system = (SYSTEM_PROMPT.replace("__ASSETS__", asset_lines)
              .replace("__EVENT_TYPES__", ", ".join(config.EVENT_TYPES)))
    user = json.dumps({
        "recent_titles": recent_titles[:40],
        "items": [{"i": i, "title": c["title"], "source": c["source"], "market": c["market"],
                   "text": c["text"]} for i, c in enumerate(candidates)],
    }, ensure_ascii=False)
    raw = _call_gemini(system, user)
    if raw is None:
        return [None] * len(candidates)
    by_index = {}
    for r in raw:
        if isinstance(r, dict) and isinstance(r.get("i"), int):
            by_index[r["i"]] = _clean(r)
    return [by_index.get(i) for i in range(len(candidates))]


def _analyze_keywords(candidates):
    out = []
    for c in candidates:
        text = f" {c['title']} {c['text']} ".lower()
        assets = []
        for a in config.ASSETS:
            if any(re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", text) for k in a["keywords"]):
                assets.append({"symbol": a["symbol"], "direction": "neutral", "impact": 3,
                               "horizon": "days", "confidence": 0.0, "reason_fa": ""})
        out.append({"relevant": bool(assets), "duplicate": False, "title_fa": "", "summary_fa": [],
                    "event_type": "other", "impact": 3, "assets": assets[:3]})
    return out


def analyze(candidates, recent_titles):
    """برای هر خبر یک نتیجه برمی‌گرداند؛ None یعنی تحلیل ناموفق بود و دفعه‌ی بعد دوباره تلاش شود.

    خروجی دوم نام تحلیل‌گر است: "gemini" یا "keyword".
    """
    if not candidates:
        return [], ("gemini" if enabled() else "keyword")
    if enabled():
        return _analyze_gemini(candidates, recent_titles), "gemini"
    return _analyze_keywords(candidates), "keyword"
