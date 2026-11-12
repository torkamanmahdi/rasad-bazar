"""ارسال هشدار به کانال تلگرام: خبرهای پرتأثیر و رویدادهای مهم تقویم اقتصادی."""
import html
import os
from datetime import datetime, timedelta, timezone

import requests

from . import config
from .util import log

DISCLAIMER = "⚠️ این تحلیل خودکار است و توصیه‌ی سرمایه‌گذاری نیست."
_DIRECTION = {"bullish": "▲ صعودی", "bearish": "▼ نزولی", "neutral": "● خنثی"}
_TEHRAN = timezone(timedelta(hours=3, minutes=30))


def enabled():
    return bool(os.environ.get("TG_BOT_TOKEN") and os.environ.get("TG_CHANNEL_ID"))


def _send(text):
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{os.environ['TG_BOT_TOKEN']}/sendMessage",
            json={"chat_id": os.environ["TG_CHANNEL_ID"], "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=20)
        if resp.status_code == 200:
            return True
        log.warning("تلگرام پاسخ %s داد: %s", resp.status_code, resp.text[:160])
    except requests.RequestException as exc:
        log.warning("ارسال به تلگرام ناموفق بود: %s", str(exc)[:120])
    return False


def _esc(text):
    return html.escape(str(text or ""), quote=False)


def news_message(item):
    icon = "🔴" if item["impact"] >= 9 else "🟠"
    lines = [f"{icon} <b>{_esc(item.get('title_fa') or item['title'])}</b>", ""]
    lines += [f"• {_esc(s)}" for s in item.get("summary_fa", [])]
    if item.get("assets"):
        lines.append("")
    for a in item.get("assets", []):
        name = config.ASSET_BY_SYMBOL[a["symbol"]]["name_fa"]
        lines.append(f"📊 <b>{_esc(name)}</b>: {_DIRECTION[a['direction']]} "
                     f"(تأثیر {a['impact']} از ۱۰، اطمینان {round(a['confidence'] * 100)}٪)")
        if a.get("reason_fa"):
            lines.append(f"   {_esc(a['reason_fa'])}")
    lines += ["", f'🔗 <a href="{html.escape(item["url"], quote=True)}">{_esc(item["source"])}</a>',
              "", DISCLAIMER]
    return "\n".join(lines)


def calendar_message(event):
    when = datetime.fromtimestamp(event["ts"], _TEHRAN).strftime("%H:%M")
    lines = [f"📅 <b>رویداد مهم اقتصادی تا دقایقی دیگر</b>", "",
             f"<b>{_esc(event['currency'])}</b> — {_esc(event['title'])}",
             f"🕒 ساعت {when} به وقت تهران"]
    if event.get("forecast"):
        lines.append(f"پیش‌بینی: {_esc(event['forecast'])}")
    if event.get("previous"):
        lines.append(f"قبلی: {_esc(event['previous'])}")
    return "\n".join(lines)


def send_alerts(new_items, calendar, state, now):
    """خبرهای پرتأثیرِ تازه و رویدادهای مهمِ نزدیک را می‌فرستد. تعداد پیام‌های ارسالی را برمی‌گرداند."""
    if not enabled():
        return 0
    sent = 0
    important = sorted((i for i in new_items
                        if i.get("analyzer") == "gemini" and i["impact"] >= config.TELEGRAM_MIN_IMPACT),
                       key=lambda i: -i["impact"])
    for item in important[: config.TELEGRAM_MAX_PER_RUN]:
        sent += _send(news_message(item))

    alerted = state.setdefault("calendar_alerted", [])
    for event in (calendar or {}).get("events", []):
        key = f"{event['ts']}|{event['currency']}|{event['title']}"
        soon = 0 <= event["ts"] - now <= config.CALENDAR_ALERT_MIN * 60
        if (soon and event["impact"] == "high" and key not in alerted
                and event["currency"] in config.CALENDAR_ALERT_CURRENCIES):
            if _send(calendar_message(event)):
                alerted.append(key)
                sent += 1
    state["calendar_alerted"] = alerted[-200:]
    return sent
