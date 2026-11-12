"""دریافت قیمت و تاریخچه‌ی ساعتی دارایی‌ها.

هر تابع منبع، فهرستی از [زمان بسته‌شدن کندل (ثانیه)، قیمت بسته‌شدن] برمی‌گرداند.
- کریپتو: Binance (دامنه‌ی data-api که از آمریکا هم باز است) و در صورت خطا OKX
- فارکس، طلا، نفت: Yahoo Finance
- تتر/تومان: Wallex
"""
import time
from concurrent.futures import ThreadPoolExecutor

from . import config
from .util import get, log

HOUR = 3600


def _binance(asset, now):
    rows = get("https://data-api.binance.vision/api/v3/klines",
               params={"symbol": asset["code"], "interval": "1h",
                       "limit": config.HISTORY_DAYS * 24 + 2}).json()
    return [[int(r[0]) // 1000 + HOUR, float(r[4])] for r in rows]


def _okx(asset, now):
    out, after = [], None
    for _ in range(2):  # هر درخواست حداکثر ۱۰۰ کندل می‌دهد
        params = {"instId": asset["alt"], "bar": "1H", "limit": 100}
        if after:
            params["after"] = after
        rows = get("https://www.okx.com/api/v5/market/candles", params=params).json()["data"]
        if not rows:
            break
        out += [[int(r[0]) // 1000 + HOUR, float(r[4])] for r in rows]
        after = rows[-1][0]
    return sorted(out)


def _yahoo(asset, now):
    data = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{asset['code']}",
               params={"interval": "1h", "range": f"{config.HISTORY_DAYS}d"}).json()
    result = data["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    hist = [[int(t) + HOUR, float(c)] for t, c in zip(result["timestamp"], closes) if c is not None]
    last = result["meta"].get("regularMarketPrice")
    last_time = result["meta"].get("regularMarketTime")
    if last and last_time and hist and last_time > hist[-1][0] - HOUR:
        hist[-1] = [int(last_time), float(last)]
    return hist


def _wallex(asset, now):
    data = get("https://api.wallex.ir/v1/udf/history",
               params={"symbol": asset["code"], "resolution": "60",
                       "from": now - config.HISTORY_DAYS * 86400, "to": now}).json()
    return [[int(t) + HOUR, float(c)] for t, c in zip(data["t"], data["c"])]


_PROVIDERS = {"binance": [_binance, _okx], "yahoo": [_yahoo], "wallex": [_wallex]}


def _fetch_one(asset, now):
    for fn in _PROVIDERS[asset["provider"]]:
        try:
            hist = fn(asset, now)
            # زمان‌ها یکتا و صعودی می‌شوند (کندل در حال تشکیل به «اکنون» بریده می‌شود)
            window_start = now - config.HISTORY_DAYS * 86400 - HOUR
            hist = sorted({min(t, now): p for t, p in sorted(hist) if t > window_start}.items())
            if len(hist) < 3:
                raise ValueError("تاریخچه خالی است")
            digits = asset["decimals"] + 1
            hist = [[t, round(p, digits)] for t, p in hist]
            price = hist[-1][1]
            # تغییر ۲۴ ساعته: آخرین قیمتِ ثبت‌شده در ۲۴ ساعت پیش یا قبل از آن
            past = [p for t, p in hist if t <= now - 86400]
            change = round((price / past[-1] - 1) * 100, 2) if past and past[-1] else None
            return {"price": price, "change_24h": change, "history": hist,
                    "source": fn.__name__.strip("_"), "updated": hist[-1][0], "stale": False}
        except Exception as exc:
            log.warning("قیمت %s از %s گرفته نشد: %s", asset["symbol"], fn.__name__.strip("_"), exc)
    return None


def fetch_all(previous, now=None):
    """قیمت همه‌ی دارایی‌ها را می‌گیرد. اگر منبعی خطا داد، داده‌ی قبلی با برچسب stale می‌ماند."""
    now = now or int(time.time())
    prev_assets = (previous or {}).get("assets", {})
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda a: _fetch_one(a, now), config.ASSETS))
    assets = {}
    for asset, res in zip(config.ASSETS, results):
        if res is None:
            res = prev_assets.get(asset["symbol"])
            if not res:
                continue
            res = dict(res, stale=True)
        meta = {k: asset[k] for k in ("name_fa", "market", "unit", "decimals")}
        assets[asset["symbol"]] = {**meta, **res}
    ok = sum(1 for a in assets.values() if not a["stale"])
    log.info("قیمت‌ها: %d از %d دارایی به‌روز شد", ok, len(config.ASSETS))
    return {"updated": now, "assets": assets}


def price_near(history, ts, tolerance=5400):
    """نزدیک‌ترین قیمت ثبت‌شده به زمان ts؛ اگر فاصله بیش از tolerance ثانیه باشد None."""
    best = None
    for t, p in history or []:
        if best is None or abs(t - ts) < abs(best[0] - ts):
            best = (t, p)
    if best and abs(best[0] - ts) <= tolerance:
        return best[1]
    return None
