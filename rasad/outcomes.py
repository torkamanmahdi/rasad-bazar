"""سنجش دقت: قیمت هر دارایی را ۱، ۴ و ۲۴ ساعت بعد از ثبت خبر با قیمت لحظه‌ی ثبت مقایسه می‌کند.

این بخش برای صداقت سیستم است: نشان می‌دهد جهت‌هایی که هوش مصنوعی پیش‌بینی کرده
در عمل چقدر درست از آب درآمده‌اند.
"""
from . import config
from .prices import price_near

GIVE_UP_AFTER = 6 * 86400  # اگر تا این مدت قیمتی پیدا نشد، آن افق بی‌نتیجه بسته می‌شود


def update(news, prices, now):
    """برای افق‌هایی که زمانشان رسیده، درصد تغییر قیمت را ثبت می‌کند. تعداد موارد تازه را برمی‌گرداند."""
    filled = 0
    assets = prices.get("assets", {})
    for item in news:
        for a in item.get("assets", []):
            base = a.get("price_at")
            market = assets.get(a["symbol"])
            if not base or not market:
                continue
            outcomes = a.setdefault("outcomes", {})
            for name, seconds in config.HORIZONS.items():
                if name in outcomes:
                    continue
                target = item["ref_ts"] + seconds
                if now < target:
                    continue
                if now - target <= 1800 and not market.get("stale"):
                    price = market["price"]
                else:
                    price = price_near(market.get("history"), target)
                if price is None:
                    if now - target > GIVE_UP_AFTER:
                        outcomes[name] = None
                    continue
                outcomes[name] = round((price / base - 1) * 100, 3)
                filled += 1
    return filled


def _bucket():
    return {"hits": 0, "misses": 0, "flat": 0, "sum_aligned": 0.0}


def _finish(b):
    decided = b["hits"] + b["misses"]
    total = decided + b["flat"]
    return {
        "n": decided,
        "hits": b["hits"],
        "flat": b["flat"],
        "hit_rate": round(b["hits"] / decided * 100, 1) if decided else None,
        "avg_aligned": round(b["sum_aligned"] / total, 3) if total else None,
    }


def stats(news):
    """نرخ درستی پیش‌بینی جهت، کلی و به تفکیک دارایی.

    فقط خبرهایی که هوش مصنوعی برایشان جهت صعودی یا نزولی داده شمرده می‌شوند.
    «حرکت هم‌جهت» یعنی درصد تغییر قیمت در جهتی که پیش‌بینی شده بود (منفی = خلاف پیش‌بینی).
    """
    overall = {h: _bucket() for h in config.HORIZONS}
    by_asset = {}
    for item in news:
        if item.get("analyzer") != "gemini":
            continue
        for a in item.get("assets", []):
            if a["direction"] not in ("bullish", "bearish"):
                continue
            sign = 1 if a["direction"] == "bullish" else -1
            for name, move in (a.get("outcomes") or {}).items():
                if move is None or name not in overall:
                    continue
                aligned = move * sign
                per_asset = by_asset.setdefault(a["symbol"], {h: _bucket() for h in config.HORIZONS})
                for bucket in (overall[name], per_asset[name]):
                    bucket["sum_aligned"] += aligned
                    if aligned >= config.FLAT_PCT:
                        bucket["hits"] += 1
                    elif aligned <= -config.FLAT_PCT:
                        bucket["misses"] += 1
                    else:
                        bucket["flat"] += 1
    return {
        "overall": {h: _finish(b) for h, b in overall.items()},
        "by_asset": {s: {h: _finish(b) for h, b in hs.items()} for s, hs in sorted(by_asset.items())},
        "flat_pct": config.FLAT_PCT,
    }
