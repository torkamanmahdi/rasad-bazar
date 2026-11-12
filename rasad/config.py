"""تنظیمات پروژه: دارایی‌ها، منابع خبر و پارامترها.

برای اضافه‌کردن دارایی یا منبع خبر جدید فقط همین فایل را ویرایش کنید.
"""

# ───────────── دارایی‌ها ─────────────
# provider: منبع قیمت  |  code: نماد نزد آن منبع  |  alt: نماد نزد منبع پشتیبان (OKX)
# keywords: فقط وقتی کلید هوش مصنوعی تنظیم نشده برای برچسب‌زدن ساده استفاده می‌شود.
ASSETS = [
    dict(symbol="BTC", name_fa="بیت‌کوین", market="crypto", unit="$", decimals=0,
         provider="binance", code="BTCUSDT", alt="BTC-USDT", keywords=["bitcoin", "btc"]),
    dict(symbol="ETH", name_fa="اتریوم", market="crypto", unit="$", decimals=2,
         provider="binance", code="ETHUSDT", alt="ETH-USDT", keywords=["ethereum", "ether", "eth"]),
    dict(symbol="SOL", name_fa="سولانا", market="crypto", unit="$", decimals=2,
         provider="binance", code="SOLUSDT", alt="SOL-USDT", keywords=["solana", "sol"]),
    dict(symbol="XRP", name_fa="ریپل", market="crypto", unit="$", decimals=4,
         provider="binance", code="XRPUSDT", alt="XRP-USDT", keywords=["xrp", "ripple"]),
    dict(symbol="BNB", name_fa="بی‌ان‌بی", market="crypto", unit="$", decimals=1,
         provider="binance", code="BNBUSDT", alt="BNB-USDT", keywords=["bnb", "binance coin"]),
    dict(symbol="EURUSD", name_fa="یورو / دلار", market="forex", unit="", decimals=4,
         provider="yahoo", code="EURUSD=X", keywords=["eur/usd", "eurusd", "euro", "ecb"]),
    dict(symbol="GBPUSD", name_fa="پوند / دلار", market="forex", unit="", decimals=4,
         provider="yahoo", code="GBPUSD=X",
         keywords=["gbp/usd", "gbpusd", "pound", "sterling", "bank of england", "boe"]),
    dict(symbol="USDJPY", name_fa="دلار / ین", market="forex", unit="", decimals=2,
         provider="yahoo", code="JPY=X", keywords=["usd/jpy", "usdjpy", "yen", "bank of japan", "boj"]),
    dict(symbol="DXY", name_fa="شاخص دلار", market="forex", unit="", decimals=2,
         provider="yahoo", code="DX-Y.NYB",
         keywords=["dollar index", "dxy", "us dollar", "federal reserve", "fomc", "fed"]),
    dict(symbol="XAUUSD", name_fa="طلا (اونس)", market="commodity", unit="$", decimals=1,
         provider="yahoo", code="GC=F", keywords=["gold", "xau", "xau/usd", "bullion"]),
    dict(symbol="OIL", name_fa="نفت برنت", market="commodity", unit="$", decimals=2,
         provider="yahoo", code="BZ=F", keywords=["oil", "brent", "crude", "wti", "opec"]),
    dict(symbol="USDTIRT", name_fa="تتر / تومان", market="iran", unit="تومان", decimals=0,
         provider="wallex", code="USDTTMN", keywords=["rial", "toman"]),
]
ASSET_BY_SYMBOL = {a["symbol"]: a for a in ASSETS}

# ───────────── منابع خبر (RSS) ─────────────
# market: crypto | forex | macro   —   gnews=True یعنی جست‌وجوی Google News
_GN = "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q="
FEEDS = [
    dict(name="Cointelegraph", market="crypto", url="https://cointelegraph.com/rss"),
    dict(name="The Block", market="crypto", url="https://www.theblock.co/rss.xml"),
    dict(name="Decrypt", market="crypto", url="https://decrypt.co/feed"),
    dict(name="CryptoSlate", market="crypto", url="https://cryptoslate.com/feed/"),
    dict(name="CoinDesk", market="crypto", url="https://www.coindesk.com/arc/outboundfeeds/rss/"),
    dict(name="investingLive", market="forex", url="https://investinglive.com/feed/news"),
    dict(name="Federal Reserve", market="macro", url="https://www.federalreserve.gov/feeds/press_all.xml"),
    dict(name="ECB", market="macro", url="https://www.ecb.europa.eu/rss/press.html"),
    dict(name="Bank of England", market="macro", url="https://www.bankofengland.co.uk/rss/news"),
    dict(name="Google News", market="forex", gnews=True,
         url=_GN + '("EUR/USD"+OR+"GBP/USD"+OR+"USD/JPY"+OR+"dollar+index"+OR+forex)+when:6h'),
    dict(name="Google News", market="forex", gnews=True,
         url=_GN + '("gold+price"+OR+"XAU/USD"+OR+"Brent+crude"+OR+"oil+prices"+OR+OPEC)+when:6h'),
    dict(name="Google News", market="macro", gnews=True,
         url=_GN + '("Federal+Reserve"+OR+FOMC+OR+"Bank+of+Japan"+OR+"inflation+data"+OR+"nonfarm+payrolls")+when:6h'),
]

# ───────────── پارامترها ─────────────
MAX_NEWS_AGE_HOURS = 12      # خبرهای قدیمی‌تر از این نادیده گرفته می‌شوند
MAX_CANDIDATES = 15          # حداکثر خبر تازه در هر اجرا (یک درخواست به هوش مصنوعی)
MAX_TEXT_CHARS = 700         # طول متن هر خبر که برای هوش مصنوعی فرستاده می‌شود
NEWS_KEEP = 400              # تعداد خبری که در news.json نگه داشته می‌شود
HISTORY_DAYS = 7             # طول تاریخچه‌ی قیمت (ساعتی)
CALENDAR_REFRESH_MIN = 60    # فاصله‌ی به‌روزرسانی تقویم اقتصادی
CALENDAR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CNY", "CHF", "CAD", "AUD"]

TELEGRAM_MIN_IMPACT = 7      # حداقل تأثیر برای ارسال خبر به تلگرام
TELEGRAM_MAX_PER_RUN = 5
CALENDAR_ALERT_MIN = 30      # چند دقیقه قبل از رویداد مهم هشدار بدهد
CALENDAR_ALERT_CURRENCIES = ["USD", "EUR", "GBP", "JPY"]

# سنجش دقت
HORIZONS = {"1h": 3600, "4h": 4 * 3600, "24h": 24 * 3600}
FLAT_PCT = 0.05              # حرکت کمتر از این (درصد) «خنثی» حساب می‌شود، نه درست و نه غلط

EVENT_TYPES = [
    "monetary_policy", "economic_data", "regulation", "etf_institutional", "security_hack",
    "exchange_listing", "geopolitics", "corporate", "market_move", "technical_analysis", "other",
]
