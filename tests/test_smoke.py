"""تست سریع بدون اینترنت: اعتبارسنجی خروجی هوش مصنوعی و محاسبه‌ی دقت.

اجرا:  python tests/test_smoke.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rasad import ai, outcomes, telegram  # noqa: E402
from main import build_item  # noqa: E402

NOW = 1_800_000_000
HOUR = 3600


def fake_gemini(system_prompt, user_prompt):
    assert "BTC" in system_prompt and "recent_titles" in user_prompt
    return [
        {"i": 0, "relevant": True, "duplicate": False, "title_fa": "فدرال رزرو نرخ بهره را ثابت نگه داشت",
         "summary_fa": ["نرخ بهره بدون تغییر ماند."], "event_type": "monetary_policy", "impact": 8,
         "assets": [
             {"symbol": "btc", "direction": "bullish", "impact": 7, "horizon": "days",
              "confidence": 0.65, "reason_fa": "کاهش فشار نرخ بهره"},
             {"symbol": "DXY", "direction": "bearish", "impact": 14, "horizon": "soon",
              "confidence": 3, "reason_fa": "تضعیف دلار"},
             {"symbol": "DOGE", "direction": "bullish", "impact": 5, "confidence": 0.5},
             {"symbol": "BTC", "direction": "bearish", "impact": 5, "confidence": 0.5},
         ]},
        {"i": 1, "relevant": False},
        {"i": 2, "relevant": True, "duplicate": True, "title_fa": "تکراری"},
        # خبر چهارم عمداً بدون پاسخ مانده است
    ]


def candidate(n):
    return {"title": f"News {n}", "url": f"https://example.com/{n}", "text": "body", "source": "Test",
            "market": "macro", "published_ts": NOW - 60, "keys": [f"k{n}"]}


def main():
    os.environ["GEMINI_API_KEY"] = "test"
    ai._call_gemini = fake_gemini
    results, analyzer = ai.analyze([candidate(i) for i in range(4)], ["old title"])
    assert analyzer == "gemini"
    first, second, third, fourth = results

    # نمادهای ناشناخته و تکراری حذف و مقادیر خارج از بازه اصلاح می‌شوند
    assert [a["symbol"] for a in first["assets"]] == ["BTC", "DXY"], first["assets"]
    dxy = first["assets"][1]
    assert dxy["impact"] == 10 and dxy["confidence"] == 1.0 and dxy["horizon"] == "days"
    assert second["relevant"] is False and third["duplicate"] is True
    assert fourth is None, "خبر بدون پاسخ باید برای تلاش دوباره None بماند"

    # ساخت خبر و ثبت قیمت لحظه‌ی خبر
    prices = {"assets": {
        "BTC": {"price": 100.0, "stale": False, "history": []},
        "DXY": {"price": 50.0, "stale": False, "history": []},
    }}
    item = build_item(candidate(0), first, analyzer, prices, NOW)
    assert item["assets"][0]["price_at"] == 100.0 and item["assets"][0]["outcomes"] == {}

    # یک ساعت بعد: BTC +1٪ (پیش‌بینی صعودی درست)، DXY +1٪ (پیش‌بینی نزولی غلط)
    later = {"assets": {
        "BTC": {"price": 101.0, "stale": False, "history": []},
        "DXY": {"price": 50.5, "stale": False, "history": []},
    }}
    assert outcomes.update([item], later, NOW + HOUR + 60) == 2
    assert item["assets"][0]["outcomes"] == {"1h": 1.0}
    assert item["assets"][1]["outcomes"] == {"1h": 1.0}
    assert outcomes.update([item], later, NOW + HOUR + 120) == 0, "نتیجه نباید دوباره ثبت شود"

    # افق ۴ ساعته از روی تاریخچه (وقتی اجرا با تأخیر انجام شده)
    late = {"assets": {
        "BTC": {"price": 90.0, "stale": False, "history": [[NOW + 4 * HOUR - 600, 100.02], [NOW + 9 * HOUR, 90.0]]},
        "DXY": {"price": 50.0, "stale": True, "history": []},
    }}
    assert outcomes.update([item], late, NOW + 9 * HOUR) == 1
    assert item["assets"][0]["outcomes"]["4h"] == 0.02     # کمتر از آستانه = خنثی
    assert "4h" not in item["assets"][1]["outcomes"]       # قیمتی نبود، بعداً تلاش می‌شود

    s = outcomes.stats([item])
    assert s["overall"]["1h"] == {"n": 2, "hits": 1, "flat": 0, "hit_rate": 50.0, "avg_aligned": 0.0}
    assert s["overall"]["4h"]["n"] == 0 and s["overall"]["4h"]["flat"] == 1
    assert s["by_asset"]["BTC"]["1h"]["hit_rate"] == 100.0
    assert s["by_asset"]["DXY"]["1h"]["hit_rate"] == 0.0

    # خبرهای حالت کلیدواژه‌ای در آمار دقت شمرده نمی‌شوند
    assert outcomes.stats([dict(item, analyzer="keyword")])["overall"]["1h"]["n"] == 0

    # متن پیام تلگرام ساخته می‌شود و HTML خطرناک را خنثی می‌کند
    item["title_fa"] = "تیتر <b>آزمایشی</b>"
    message = telegram.news_message(item)
    assert "&lt;b&gt;" in message and "▲ صعودی" in message and "▼ نزولی" in message

    # حالت بدون کلید: برچسب‌زن کلیدواژه‌ای
    del os.environ["GEMINI_API_KEY"]
    results, analyzer = ai.analyze([dict(candidate(9), title="Bitcoin ETF inflows rise as gold slips")], [])
    assert analyzer == "keyword"
    assert [a["symbol"] for a in results[0]["assets"]] == ["BTC", "XAUUSD"]
    assert all(a["direction"] == "neutral" for a in results[0]["assets"])
    print("OK - all smoke tests passed")


if __name__ == "__main__":
    main()
