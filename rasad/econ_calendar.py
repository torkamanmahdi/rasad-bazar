"""تقویم اقتصادی هفته‌ی جاری از فید رایگان Forex Factory."""
from datetime import datetime

from . import config
from .util import get, log

URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


def fetch(previous, now):
    """تقویم را حداکثر هر CALENDAR_REFRESH_MIN دقیقه یک بار تازه می‌کند (فید محدودیت درخواست دارد)."""
    previous = previous or {}
    if previous.get("events") and now - previous.get("updated", 0) < config.CALENDAR_REFRESH_MIN * 60:
        return previous
    try:
        rows = get(URL).json()
    except Exception as exc:
        log.warning("تقویم اقتصادی گرفته نشد: %s", str(exc)[:120])
        return previous
    events = []
    for row in rows:
        if row.get("country") not in config.CALENDAR_CURRENCIES:
            continue
        if row.get("impact") not in ("High", "Medium", "Low"):
            continue
        try:
            ts = int(datetime.fromisoformat(row["date"]).timestamp())
        except Exception:
            continue
        events.append({
            "ts": ts,
            "title": row.get("title", ""),
            "currency": row["country"],
            "impact": row["impact"].lower(),
            "forecast": row.get("forecast") or "",
            "previous": row.get("previous") or "",
        })
    events.sort(key=lambda e: e["ts"])
    log.info("تقویم اقتصادی: %d رویداد", len(events))
    return {"updated": now, "events": events}
