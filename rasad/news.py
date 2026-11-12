"""جمع‌آوری خبر از فیدهای RSS/Atom و انتخاب خبرهای تازه و غیرتکراری."""
import html
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, urlunparse

from . import config
from .util import get, log, norm_title, short_hash

_ATOM = "{http://www.w3.org/2005/Atom}"


def _strip_html(text):
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text or "", flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(text, now):
    text = (text or "").strip()
    if not text:
        return now
    try:
        dt = parsedate_to_datetime(text)
    except Exception:
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return now
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return min(int(dt.timestamp()), now)


def clean_url(url):
    try:
        p = urlparse(url)
        return urlunparse((p.scheme, p.netloc, p.path, "", "", "")).rstrip("/")
    except Exception:
        return url or ""


def _text(node, *names):
    for name in names:
        child = node.find(name)
        if child is not None and (child.text or "").strip():
            return child.text.strip()
    return ""


def fetch_feed(feed, now):
    """یک فید را می‌خواند و فهرست خبرهایش را برمی‌گرداند (در صورت خطا فهرست خالی)."""
    try:
        root = ET.fromstring(get(feed["url"], timeout=20).content)
    except Exception as exc:
        log.warning("فید %s خوانده نشد: %s", feed["name"], str(exc)[:120])
        return []

    items = []
    nodes = root.findall(".//item") or root.findall(f".//{_ATOM}entry")
    for node in nodes[:40]:
        title = _strip_html(_text(node, "title", f"{_ATOM}title"))
        link = _text(node, "link")
        if not link:
            atom_link = node.find(f"{_ATOM}link")
            link = atom_link.get("href", "") if atom_link is not None else ""
        if not title or not link.startswith("http"):
            continue
        source = feed["name"]
        body = _strip_html(_text(node, "description", f"{_ATOM}summary", f"{_ATOM}content"))
        if feed.get("gnews"):
            # عنوان Google News به شکل «تیتر - نام رسانه» است و متن خبر ندارد
            publisher = _text(node, "source")
            if publisher:
                source = publisher
                if title.endswith(" - " + publisher):
                    title = title[: -len(publisher) - 3]
            body = ""
        items.append({
            "title": title,
            "url": link,
            "text": body[: config.MAX_TEXT_CHARS],
            "source": source,
            "market": feed["market"],
            "published_ts": _parse_date(
                _text(node, "pubDate", f"{_ATOM}published", f"{_ATOM}updated"), now),
        })
    return items


def _too_similar(a, b):
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return False
    return len(ta & tb) / min(len(ta), len(tb)) > 0.75


def collect(seen, now=None):
    """خبرهای تازه‌ای را برمی‌گرداند که قبلاً دیده نشده‌اند.

    seen: مجموعه‌ی هش آدرس‌ها و عنوان‌های پردازش‌شده‌ی قبلی.
    خروجی بین بازارها نوبتی انتخاب می‌شود تا خبرهای پرتعداد کریپتو جای فارکس را نگیرند.
    """
    now = now or int(time.time())
    with ThreadPoolExecutor(max_workers=8) as pool:
        batches = list(pool.map(lambda f: fetch_feed(f, now), config.FEEDS))

    min_ts = now - config.MAX_NEWS_AGE_HOURS * 3600
    fresh, titles = [], []
    for item in sorted((i for b in batches for i in b), key=lambda i: -i["published_ts"]):
        if item["published_ts"] < min_ts:
            continue
        nt = norm_title(item["title"])
        keys = {short_hash(clean_url(item["url"])), short_hash(nt)}
        if keys & seen or any(_too_similar(nt, other) for other in titles):
            continue
        item["keys"] = sorted(keys)
        titles.append(nt)
        fresh.append(item)

    by_market = {}
    for item in fresh:
        by_market.setdefault(item["market"], []).append(item)
    picked = []
    while len(picked) < config.MAX_CANDIDATES and any(by_market.values()):
        for market in ("forex", "macro", "crypto"):
            if by_market.get(market) and len(picked) < config.MAX_CANDIDATES:
                picked.append(by_market[market].pop(0))
    log.info("خبر: %d مورد تازه پیدا شد، %d مورد برای تحلیل انتخاب شد", len(fresh), len(picked))
    return picked
