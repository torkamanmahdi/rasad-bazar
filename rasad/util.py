"""ابزارهای مشترک: درخواست HTTP، خواندن/نوشتن JSON، بارگذاری .env."""
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
log = logging.getLogger("rasad")

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_session = None


def setup():
    """لاگ، خروجی UTF-8 (برای ترمینال ویندوز) و متغیرهای .env را آماده می‌کند."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    load_env()
    DATA.mkdir(exist_ok=True)


def load_env(path=ROOT / ".env"):
    """فایل .env را (اگر باشد) می‌خواند. متغیرهای موجود محیط را بازنویسی نمی‌کند."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def session():
    global _session
    if _session is None:
        s = requests.Session()
        retry = Retry(total=2, backoff_factor=0.6, status_forcelist=[500, 502, 503, 504],
                      allowed_methods=["GET"])
        s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=20))
        s.headers.update({"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"})
        _session = s
    return _session


def get(url, timeout=15, **kwargs):
    resp = session().get(url, timeout=timeout, **kwargs)
    resp.raise_for_status()
    return resp


def read_json(name, default):
    path = DATA / name
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("خواندن %s ناموفق بود: %s", name, exc)
        return default


def write_json(name, data):
    """نوشتن اتمی: اول فایل موقت، بعد جایگزینی؛ تا فایل نیمه‌کاره نماند."""
    path = DATA / name
    fd, tmp = tempfile.mkstemp(dir=str(DATA), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def norm_title(text):
    """عنوان را برای مقایسه یکدست می‌کند (حروف کوچک، بدون علائم)."""
    text = re.sub(r"[^\w\s]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def short_hash(text):
    return hashlib.md5((text or "").encode("utf-8")).hexdigest()[:12]
