# -*- coding: utf-8 -*-
"""
proxy.py — ارسال درخواست به سرویس‌های AI
====================================================================
سه حالت اتصال (قابل انتخاب در تنظیمات):

    direct  → بدون پروکسی
              مناسب Groq، OpenRouter، آوالای و سرویس‌های داخلی

    system  → از پروکسی خودِ ویندوز استفاده می‌کند  (پیش‌فرض)
              اگر سایفون، Hiddify، V2Ray یا هر برنامه‌ای پروکسی سیستم
              را تنظیم کرده باشد، این برنامه هم دقیقاً مثل مرورگر
              از همان مسیر عبور می‌کند.

    manual  → آدرس پروکسی که کاربر خودش وارد کرده

منبع پروکسی سیستم روی ویندوز:
    HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings
        ProxyEnable (DWORD)  — روشن/خاموش
        ProxyServer (REG_SZ) — آدرس
    این همان جایی است که مرورگرها و بیشتر برنامه‌ها می‌خوانند.
"""

import os
import re
import json
import time
import urllib.parse
import urllib.request

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_SYS_CACHE = {"at": 0, "data": None}
_SYS_TTL = 20          # ثانیه — تا تغییر پروکسی سریع دیده شود


def _settings():
    try:
        import backend_server
        return backend_server.get_settings()
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# خواندن پروکسی سیستم
# ---------------------------------------------------------------------------
def _norm_proxy(value, default_scheme="http"):
    """
    یک آدرس پروکسی خام را به شکل استاندارد در می‌آورد.

    چرا لازم است؟ رجیستری ویندوز مقدار را به شکل‌های مختلفی نگه می‌دارد:
        127.0.0.1:12334              ← ساده
        http://127.0.0.1:12334       ← Hiddify و بعضی کلاینت‌ها
        socks5://127.0.0.1:1080

    اگر کورکورانه پیشوند اضافه کنیم، نتیجه http://http://... می‌شود و
    requests سعی می‌کند به هاستی به نام «http» وصل شود:
        ProxyError: Max retries exceeded with url ...
    """
    v = (value or "").strip().strip('"').strip("'")
    if not v:
        return None

    # پیشوندهای تکراری را پاک کن  (http://http://x → x)
    while True:
        m = re.match(r'^(https?|socks[45]?h?)://', v, re.I)
        if not m:
            break
        rest = v[m.end():]
        if re.match(r'^(https?|socks[45]?h?)://', rest, re.I):
            v = rest          # پیشوند تکراری بود، دور بریز
            continue
        scheme = m.group(1).lower()
        v = rest
        default_scheme = scheme
        break

    v = v.strip("/")
    if not v:
        return None

    # socks → socks5h  (حرف h یعنی DNS هم از تونل عبور کند،
    # وگرنه درخواست DNS مستقیم می‌رود و ممکن است فیلتر شود)
    if default_scheme.startswith("socks"):
        if default_scheme in ("socks", "socksh"):
            default_scheme = "socks5h"
        elif not default_scheme.endswith("h"):
            default_scheme += "h"

    return f"{default_scheme}://{v}"


def _read_windows_registry_proxy():
    """پروکسی را مستقیماً از رجیستری ویندوز می‌خواند."""
    if os.name != 'nt':
        return None
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        try:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if not enabled:
                return None
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
        finally:
            winreg.CloseKey(key)

        if not server:
            return None

        # فرمت ممکن است "host:port" یا "http=h:p;socks=h:p" باشد
        server = server.strip()
        if "=" in server:
            parts = {}
            for chunk in server.split(";"):
                if "=" in chunk:
                    k, v = chunk.split("=", 1)
                    parts[k.strip().lower()] = v.strip()
            # SOCKS اولویت دارد چون هم HTTP و هم HTTPS را تونل می‌کند
            if parts.get("socks"):
                u = _norm_proxy(parts["socks"], "socks5h")
                return {"http": u, "https": u} if u else None
            out = {}
            if parts.get("http"):
                out["http"] = _norm_proxy(parts["http"], "http")
            if parts.get("https"):
                out["https"] = _norm_proxy(parts["https"], "http")
            elif out.get("http"):
                out["https"] = out["http"]
            out = {k: v for k, v in out.items() if v}
            return out or None

        u = _norm_proxy(server, "http")
        return {"http": u, "https": u} if u else None
    except FileNotFoundError:
        return None
    except Exception:
        return None


def get_system_proxy(force=False):
    """
    پروکسی سیستم را برمی‌گرداند (با کش کوتاه).

    خروجی: dict مثل {"http": "...", "https": "..."} یا None
    """
    now = time.time()
    if not force and _SYS_CACHE["data"] is not None and now - _SYS_CACHE["at"] < _SYS_TTL:
        return _SYS_CACHE["data"]

    proxies = _read_windows_registry_proxy()

    # پشتیبان: متغیرهای محیطی و تنظیمات سیستم‌عامل
    if not proxies:
        env = urllib.request.getproxies()
        if env:
            proxies = {}
            # کلید all_proxy روی هر دو پروتکل اعمال می‌شود
            # (سایفون و بیشتر ابزارهای SOCKS از همین استفاده می‌کنند)
            allp = env.get("all")
            if allp:
                u = _norm_proxy(allp, "socks5h")
                proxies = {"http": u, "https": u} if u else {}
            else:
                for scheme in ("http", "https"):
                    v = env.get(scheme)
                    if v:
                        u = _norm_proxy(v, "http")
                        if u:
                            proxies[scheme] = u
                if "https" not in proxies and "http" in proxies:
                    proxies["https"] = proxies["http"]
            proxies = proxies or None

    _SYS_CACHE["at"] = now
    _SYS_CACHE["data"] = proxies
    return proxies


def system_proxy_info():
    """اطلاعات نمایشی پروکسی سیستم برای رابط کاربری."""
    p = get_system_proxy(force=True)
    if not p:
        return {"found": False, "proxies": None, "proxies_list": []}
    seen, lst = set(), []
    for scheme, url in p.items():
        if url not in seen:
            seen.add(url)
            lst.append(f"{scheme}: {url}")
    return {"found": True, "proxies": p, "proxies_list": lst}


# ---------------------------------------------------------------------------
# انتخاب مسیر
# ---------------------------------------------------------------------------
def _resolve_proxies(mode=None, manual_url=None):
    """بر اساس حالت، دیکشنری proxies را برمی‌گرداند."""
    st = _settings()
    mode = mode or st.get("conn_mode", "system")

    if mode == "direct":
        return None, "مستقیم"

    if mode == "manual":
        url = (manual_url if manual_url is not None
               else st.get("proxy_url", "")).strip()
        if not url:
            return None, "مستقیم (پروکسی دستی خالی است)"
        u = _norm_proxy(url, "socks5h" if "socks" in url.lower() else "http")
        if not u:
            return None, "مستقیم (آدرس پروکسی نامعتبر)"
        return {"http": u, "https": u}, "پروکسی دستی"

    # system
    p = get_system_proxy()
    if not p:
        return None, "مستقیم (پروکسی سیستم تنظیم نشده)"
    return p, "پروکسی سیستم"


def _headers(extra):
    h = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if extra:
        for k, v in extra.items():
            if k.lower() in ('authorization', 'content-type', 'x-api-key',
                             'user-agent', 'anthropic-version'):
                h[k] = v
    return h


def test_connection(mode=None, proxy_url=None, base_url=None, api_key=None,
                    timeout=15):
    """
    تست اتصال به سرویس AI — دو نتیجه جداگانه برمی‌گرداند:

        network_ok : آیا اصلاً به سرور رسیدیم؟ (مسیر/پروکسی سالم است)
        key_ok     : آیا کلید API معتبر است؟

    نسخه قبلی ۴۰۱ و ۴۰۳ را «موفق» می‌شمرد، چون فقط می‌خواست بداند
    پروکسی کار می‌کند. اما کاربر تیک سبز را به‌معنای «کلیدم درست است»
    می‌گرفت. حالا هر دو جدا گزارش می‌شوند.
    """
    proxies, via = _resolve_proxies(mode, proxy_url)
    st = _settings()
    key = api_key if api_key is not None else st.get("api_key", "")

    target = (base_url or st.get("base_url")
              or "https://api.groq.com/openai/v1").rstrip("/")
    if not target.endswith("/models"):
        target = target.split("/chat/completions")[0].rstrip("/") + "/models"

    if proxies:
        sample = next(iter(proxies.values()), "")
        if sample.startswith("socks"):
            try:
                import socks  # noqa: F401
            except ImportError:
                return {"ok": False, "network_ok": False, "key_ok": False,
                        "via": via, "status_kind": "network",
                        "error": "برای پروکسی SOCKS باید PySocks نصب باشد: "
                                 "pip install PySocks"}

    headers = _headers({"Authorization": f"Bearer {key}"} if key else None)

    t0 = time.time()
    try:
        r = requests.get(target, proxies=proxies, timeout=timeout,
                         headers=headers, verify=st.get("verify_tls", True))
        ms = int((time.time() - t0) * 1000)
    except Exception as e:
        return {"ok": False, "network_ok": False, "key_ok": False,
                "via": via, "status_kind": "network",
                "error": f"{type(e).__name__}: {str(e)[:90]}",
                "message": "🌐 به سرویس نرسیدیم — شبکه یا پروکسی را بررسی کنید",
                "latency_ms": int((time.time() - t0) * 1000)}

    try:
        import model_info
        kind, msg = model_info.explain_status(r.status_code, bool(key))
    except Exception:
        kind = "ok" if r.status_code == 200 else "error"
        msg = f"کد پاسخ: {r.status_code}"

    key_ok = (r.status_code == 200)
    return {
        # ok فقط وقتی true است که هم شبکه و هم کلید سالم باشند
        "ok": key_ok,
        "network_ok": True,          # پاسخ گرفتیم، پس مسیر سالم است
        "key_ok": key_ok,
        "has_key": bool(key),
        "status": r.status_code,
        "status_kind": kind,
        "message": msg,
        "via": via,
        "latency_ms": ms,
    }


# ---------------------------------------------------------------------------
# ارسال درخواست اصلی
# ---------------------------------------------------------------------------
def _is_transient(exc):
    """خطاهای گذرای شبکه که با یک تلاش مجدد معمولاً حل می‌شوند."""
    return type(exc).__name__ in (
        "ReadTimeout", "ConnectTimeout", "Timeout", "ConnectionError",
        "SSLError", "ChunkedEncodingError", "IncompleteRead",
        "RemoteDisconnected", "ConnectionResetError", "ProtocolError",
        "ProxyError", "NewConnectionError", "MaxRetryError")


def forward_ai_request(url, headers, payload=None, method='POST', use_socks=None):
    """
    درخواست را با حالت اتصال انتخابی ارسال می‌کند.

    اگر حالت «پروکسی سیستم» باشد و پروکسی جواب ندهد، یک بار هم
    مستقیم امتحان می‌شود (و برعکس) — چون کاربر ممکن است وسط کار
    سایفون را ببندد یا باز کند. خطاهای گذرا (مثل ReadTimeout) یک بار
    همان مسیر دوباره امتحان می‌شوند.
    """
    st = _settings()
    verify = st.get("verify_tls", True)
    timeout = int(st.get("request_timeout", 45))
    req_headers = _headers(headers)

    proxies, via = _resolve_proxies()
    attempts = []

    def _send(px):
        s = requests.Session()
        s.trust_env = False          # کنترل کامل با ما باشد
        s.headers.update(req_headers)
        if method.upper() == "GET":
            res = s.get(url, proxies=px, timeout=timeout, verify=verify)
        else:
            res = s.post(url, json=payload, proxies=px, timeout=timeout, verify=verify)
        # اگر سرویس‌دهنده charset نفرستد، requests ISO-8859-1 حدس می‌زند و
        # متن فارسی/فارسی-عربی mojibake می‌شود. پاسخ AI همیشه UTF-8 است.
        if not res.encoding or res.encoding.lower() in ("iso-8859-1", "latin-1", "latin1"):
            res.encoding = "utf-8"
        return res

    # مسیر اصلی (با یک retry برای خطای گذرا) سپس مسیر جایگزین
    routes = [(proxies, via, 2)]
    alt_px = None if proxies else get_system_proxy()
    alt_via = "مستقیم" if proxies else "پروکسی سیستم"
    if alt_px or proxies:
        routes.append((alt_px, alt_via, 1))

    for px, label, tries in routes:
        for _attempt in range(tries):
            try:
                res = _send(px)
                return {"status": res.status_code, "data": res.text,
                        "via": label, "fallback": label != via}
            except Exception as e:
                msg = f"{label}: {type(e).__name__}: {str(e)[:70]}"
                # از تکرارِ یک خطای یکسان (retry همان مسیر) در پیام نهایی پرهیز کن
                if not attempts or attempts[-1] != msg:
                    attempts.append(msg)
                if not _is_transient(e):
                    break   # خطای غیرگذرا — تلاش دوباره بی‌فایده است

    return {"status": 0,
            "error": "ارتباط برقرار نشد. " + " | ".join(attempts),
            "attempts": attempts}


def forward_ai_stream(url, headers, payload=None, use_socks=None):
    """
    درخواست استریمی (SSE) به سرویس AI برای نمایش زندهٔ پاسخ.

    تفاوت با forward_ai_request: با stream=True می‌فرستد و هر رویداد
    `data: ...` را yield می‌کند تا هندلر سرور بتواند قطعه‌قطعه به فرانت
    بفرستد. مثل forward_ai_request، اگر پروکسی انتخابی جواب ندهد یک
    بار هم مسیر جایگزین امتحان می‌شود.

    خروجی هر yield یک دیکشنری است:
        {"type": "data", "data": "<JSON خام>"}
        {"type": "done", ...}              → data: [DONE]
        {"type": "http_error", "status": ..., "body": ...}
        {"type": "error", "error": str}
    """
    st = _settings()
    verify = st.get("verify_tls", True)
    timeout = int(st.get("request_timeout", 45))
    req_headers = _headers(headers)
    payload = dict(payload or {})
    payload["stream"] = True

    proxies, via = _resolve_proxies()

    # استریم: کانکت کوتاه (حداکثر ۱۰ ثانیه) ولی خواندن بلند — مدل ممکن است
    # قبل از اولین توکن مدتی فکر کند؛ یک عدد واحد برای استریم باعث
    # «Read timed out»های بی‌مورد در پاسخ‌های کند می‌شد.
    stream_timeout = (min(timeout, 10), max(timeout, 120))

    def _send(px):
        s = requests.Session()
        s.trust_env = False          # کنترل کامل با ما باشد
        s.headers.update(req_headers)
        with s.post(url, json=payload, proxies=px, timeout=stream_timeout,
                    verify=verify, stream=True) as r:
            # همین مشکل رمزگذاری: بدون charset، requests با ISO-8859-1 دیکد
            # می‌کند و پاسخ فارسی/فارسی-عربی به شکل Ø³ÙØ§Ù... درمی‌آید.
            if not r.encoding or r.encoding.lower() in ("iso-8859-1", "latin-1", "latin1"):
                r.encoding = "utf-8"
            if r.status_code != 200:
                yield {"type": "http_error", "status": r.status_code,
                       "body": (r.text or "")[:400]}
                return
            for raw in r.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                line = raw.strip()
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    yield {"type": "done"}
                    return
                yield {"type": "data", "data": data}

    # مسیر اصلی (با یک retry برای خطای گذرا) سپس مسیر جایگزین.
    # مهم: اگر بخشی از پاسخ قبلاً به فرانت رفته باشد، retry/fallback متن را
    # تکرار می‌کند — پس فقط وقتی چیزی تحویل نشده دوباره امتحان می‌کنیم.
    routes = [(proxies, via, 2)]
    alt_px = None if proxies else get_system_proxy()
    alt_via = "مستقیم" if proxies else "پروکسی سیستم"
    if alt_px or proxies:
        routes.append((alt_px, alt_via, 1))

    # «delivered» یعنی چیزی به UI رسیده. توجه: یک رویداد data ممکن است فقط
    # reasoning داشته باشد (بدون متن قابل‌نمایش) — در آن حالت هم retry
    # نمی‌کنیم چون تکرار، متنِ فکرکردنِ قبلی را دوباره نشان می‌دهد.
    delivered = False
    errors = []
    for px, label, tries in routes:
        for _attempt in range(tries):
            try:
                for ev in _send(px):
                    if ev.get("type") == "data":
                        delivered = True
                    yield ev
                return
            except Exception as e:
                msg = f"{label}: {type(e).__name__}: {str(e)[:70]}"
                if not errors or errors[-1] != msg:
                    errors.append(msg)
                if delivered:
                    # پاسخ ناقص تحویل شده — ادامه با retry یعنی متن تکراری
                    yield {"type": "error",
                           "error": "ارتباط با سرویس AI قطع شد (پاسخ ناقص). "
                                    + errors[-1]}
                    return
                if not _is_transient(e):
                    break   # خطای غیرگذرا — مسیر بعدی را امتحان کن

    yield {"type": "error",
           "error": "ارتباط با سرویس AI برقرار نشد. " + " | ".join(errors)}


if __name__ == "__main__":
    print("پروکسی سیستم:", json.dumps(system_proxy_info(), ensure_ascii=False, indent=2))
    for m in ("direct", "system"):
        print(f"\nتست حالت «{m}»:", test_connection(mode=m, timeout=8))
