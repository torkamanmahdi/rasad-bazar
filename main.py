"""رصد بازار — یک اجرای کامل: قیمت‌ها، تقویم، خبرها، تحلیل، سنجش دقت و هشدار تلگرام.

اجرا:  python main.py
خروجی‌ها در پوشه‌ی data/ ذخیره می‌شوند و index.html آن‌ها را نمایش می‌دهد.
"""
import time

from rasad import ai, config, econ_calendar, news, outcomes, prices, telegram
from rasad.news import clean_url
from rasad.util import log, read_json, setup, short_hash, write_json


def build_item(candidate, result, analyzer, price_data, now):
    assets = []
    for a in result["assets"]:
        market = price_data["assets"].get(a["symbol"])
        # قیمت لحظه‌ی ثبت خبر؛ اگر قیمت آن دارایی کهنه باشد دقتش سنجیده نمی‌شود
        price_at = market["price"] if market and not market.get("stale") else None
        assets.append({**a, "price_at": price_at, "outcomes": {}})
    return {
        "id": short_hash(clean_url(candidate["url"])),
        "title": candidate["title"],
        "title_fa": result["title_fa"],
        "summary_fa": result["summary_fa"],
        "source": candidate["source"],
        "url": candidate["url"],
        "market": candidate["market"],
        "event_type": result["event_type"],
        "impact": result["impact"],
        "assets": assets,
        "analyzer": analyzer,
        "published_ts": candidate["published_ts"],
        "ref_ts": now,
    }


def run():
    setup()
    now = int(time.time())
    state = read_json("state.json", {})
    stored_news = read_json("news.json", [])

    # ۱. قیمت‌ها
    price_data = prices.fetch_all(read_json("prices.json", {}), now)
    write_json("prices.json", price_data)

    # ۲. تقویم اقتصادی
    calendar = econ_calendar.fetch(read_json("calendar.json", {}), now)
    write_json("calendar.json", calendar)

    # ۳. خبرهای تازه
    seen = set(state.get("seen", []))
    candidates = news.collect(seen, now)

    # ۴. تحلیل
    recent_titles = [n["title"] for n in stored_news[:40]]
    ai.PREFERRED = state.get("model")
    results, analyzer = ai.analyze(candidates, recent_titles)
    if ai.LAST_OK:
        state["model"] = ai.LAST_OK
    new_items, failed = [], 0
    seen_order = state.get("seen", [])
    for candidate, result in zip(candidates, results):
        if result is None:
            failed += 1          # دفعه‌ی بعد دوباره تلاش می‌شود
            continue
        seen_order += candidate["keys"]
        if result["relevant"] and not result["duplicate"]:
            new_items.append(build_item(candidate, result, analyzer, price_data, now))
    state["seen"] = seen_order[-4000:]
    log.info("تحلیل (%s): %d خبر اضافه شد، %d رد شد، %d ناموفق", analyzer, len(new_items),
             len(candidates) - len(new_items) - failed, failed)

    all_news = sorted(new_items + stored_news, key=lambda n: -n["ref_ts"])[: config.NEWS_KEEP]

    # ۵. سنجش دقت
    filled = outcomes.update(all_news, price_data, now)
    summary = outcomes.stats(all_news)
    summary.update({"updated": now, "analyzer": analyzer})
    log.info("سنجش دقت: %d نتیجه‌ی تازه ثبت شد", filled)

    # ۶. هشدار تلگرام
    sent = telegram.send_alerts(new_items, calendar, state, now)
    if sent:
        log.info("تلگرام: %d پیام ارسال شد", sent)

    write_json("news.json", all_news)
    write_json("stats.json", summary)
    write_json("state.json", state)
    log.info("پایان. %d خبر در بایگانی.", len(all_news))


if __name__ == "__main__":
    run()
