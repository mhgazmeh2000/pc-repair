# -*- coding: utf-8 -*-
"""
لایهٔ امنیتی سرور محلی — رفع C-1 و C-5

مسئله‌ای که حل می‌کند
─────────────────────
سرور روی 127.0.0.1 گوش می‌دهد و هدر `Access-Control-Allow-Origin: *`
می‌فرستاد. یعنی *هر* صفحهٔ وبی که کاربر باز کند می‌توانست با جاوااسکریپت
به سرور ما درخواست بفرستد و دستور دلخواه اجرا کند — با دسترسی ادمین،
چون برنامه با uac_admin=True اجرا می‌شود.

اثبات عملی (قبل از این ماژول):
    curl -H 'Origin: https://evil.example.com' \
         -d '{"command":"whoami"}' http://127.0.0.1:8080/api/run_tool
    → {"success": true, "command": "whoami"}

سه سد دفاعی
───────────
۱. توکن نشست  — هنگام بالا آمدن سرور تولید می‌شود، داخل HTML تزریق
                می‌شود و در هر درخواست باید برگردد. صفحهٔ مهاجم به آن
                دسترسی ندارد چون Same-Origin Policy اجازهٔ خواندن پاسخ
                HTML ما را نمی‌دهد.
۲. Host        — فقط 127.0.0.1 / localhost پذیرفته می‌شود. جلوی حملات
                DNS rebinding را می‌گیرد.
۳. Origin      — درخواست‌های دارای Origin بیگانه رد می‌شوند.

نکتهٔ طراحی: GETهای بی‌خطر (خود صفحه) توکن نمی‌خواهند، وگرنه مرورگر
نمی‌تواند اولین بار صفحه را باز کند.
"""

import errno
import hmac
import os
import secrets

# ─────────────────────────── توکن نشست ───────────────────────────

# قبلاً توکن در هر اجرای ماژول دوباره ساخته می‌شد — یعنی هر ریاستارت سرور
# (یا اجرای دوبارهٔ exe) توکن را عوض می‌کرد و صفحه‌ای که در مرورگر باز بود
# با «نشست معتبر نیست. صفحه را تازه‌سازی کنید.» از کار می‌افتاد تا کاربر
# دستی رفرش کند. حالا توکن در یک فایل پایدار نگهداری می‌شود تا بین
# ریاستارت‌ها همان بماند.

def _state_dir():
    """پوشهٔ وضعیت برنامه — در exe با uac_admin بالا آمده، مسیرهای
    home کاربر گاهی غیرقابل نوشتن یا متغیرند؛ اینجا از مسیری استفاده
    می‌شود که برنامهٔ اصلی (pc_toolbox_pro) برای WebView2 هم به کار
    می‌برد: %PROGRAMDATA%\\PCRepairToolbox."""
    base = os.environ.get("ProgramData") or os.path.expanduser("~")
    d = os.path.join(base, "PCRepairToolbox")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = os.path.join(os.path.expanduser("~"), ".pcrepairtoolbox")
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            d = os.path.dirname(os.path.abspath(__file__))
    return d


def _load_or_create_token(name, nbytes):
    """توکن را از فایل می‌خواند؛ اگر نبود می‌سازد و ذخیره می‌کند."""
    path = os.path.join(_state_dir(), name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            val = f.read().strip()
        if val:
            return val
    except (OSError, IOError):
        pass
    val = secrets.token_urlsafe(nbytes)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(val)
    except (OSError, IOError):
        pass
    return val


SESSION_TOKEN = _load_or_create_token("session_token", 32)

# نام هدری که رابط کاربری باید بفرستد
TOKEN_HEADER = "X-Toolbox-Token"

# توکن مجزای پیش‌نمایش — فقط برای دو مسیرِ فقط‌خواندنی پیش‌نمایش
# (ws_preview و /dev-asset/) از پارامتر آدرس پذیرفته می‌شود. جدا نگه داشته
# می‌شود تا توکن نشست هیچ‌وقت داخل آدرس/لاگ/تاریخچهٔ مرورگر نیفتد و
# دامنهٔ نفوذ همین دو مسیرِ فقط‌خواندنی باشد.
PREVIEW_TOKEN = _load_or_create_token("preview_token", 24)


def check_preview_token(token):
    if not token or not isinstance(token, str):
        return False
    return hmac.compare_digest(token, PREVIEW_TOKEN)

# مسیرهایی که بدون توکن هم پاسخ می‌گیرند.
# فقط چیزهایی که خواندنی و بی‌خطرند و برای بوت‌استرپ لازم‌اند.
PUBLIC_PATHS = frozenset({
    "/",
    "/index.html",
    "/pc_toolbox_app.html",
    "/favicon.ico",
})

# میزبان‌های مجاز (بخش پورت جدا می‌شود)
ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]", "::1"})


def _host_only(host_header):
    """جدا کردن نام میزبان از پورت. IPv6 داخل [] است."""
    if not host_header:
        return ""
    h = host_header.strip()
    if h.startswith("["):                      # [::1]:8080
        end = h.find("]")
        return h[:end + 1] if end != -1 else h
    return h.split(":", 1)[0]                  # 127.0.0.1:8080


def check_host(host_header):
    """آیا هدر Host به میزبان محلی اشاره می‌کند؟"""
    return _host_only(host_header) in ALLOWED_HOSTS


def check_origin(origin_header, port):
    """
    Origin خالی مجاز است: درخواست‌های same-origin و curl آن را نمی‌فرستند.
    اگر Origin هست، باید دقیقاً به سرور خودمان اشاره کند.
    """
    if not origin_header:
        return True
    o = origin_header.strip().rstrip("/")
    allowed = set()
    for scheme in ("http", "https"):
        for host in ("127.0.0.1", "localhost"):
            allowed.add(f"{scheme}://{host}:{port}")
            allowed.add(f"{scheme}://{host}")
    return o in allowed


def check_token(token_value):
    """مقایسهٔ زمان‌ثابت تا نشت اطلاعات از راه زمان‌سنجی رخ ندهد."""
    if not token_value:
        return False
    return hmac.compare_digest(str(token_value), SESSION_TOKEN)


def _query_param(query, key):
    """استخراج سادهٔ یک پارامتر از رشتهٔ query — بدون وابستگی به urllib."""
    if not query:
        return ""
    for part in query.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            if k == key:
                return v
    return ""


def authorize(path, headers, port, method="GET", query=""):
    """
    دروازهٔ اصلی. خروجی: (مجاز؟, پیام خطا)

    ترتیب بررسی از ارزان به گران است تا درخواست‌های آشکارا نامعتبر
    زود رد شوند.
    """
    # OPTIONS برای preflight — بدنه ندارد و کاری نمی‌کند
    if method == "OPTIONS":
        return True, ""

    if not check_host(headers.get("Host", "")):
        return False, "دسترسی فقط از روی همین رایانه مجاز است."

    if not check_origin(headers.get("Origin", ""), port):
        return False, "مبدأ درخواست معتبر نیست."

    # صفحهٔ اصلی باید بدون توکن باز شود، وگرنه UI هرگز بالا نمی‌آید
    if path in PUBLIC_PATHS:
        return True, ""

    token = headers.get(TOKEN_HEADER, "")
    # پیش‌نمایش زندهٔ داخل iframe نمی‌تواند هدر سفارشی بفرستد؛ توکن مجزای
    # پیش‌نمایش (نه توکن نشست) از پارامتر آدرس پذیرفته می‌شود.
    if path == "/api/ws_preview" or path.startswith("/dev-asset/"):
        if token:
            if check_token(token):
                return True, ""
        elif check_preview_token(_query_param(query, "token")):
            return True, ""
        return False, "نشست معتبر نیست. صفحه را تازه‌سازی کنید."

    if not check_token(token):
        return False, "نشست معتبر نیست. صفحه را تازه‌سازی کنید."

    return True, ""


def inject_token(html_text):
    """
    تزریق توکن داخل HTML قبل از ارسال.

    چرا امن است: صفحهٔ مهاجم می‌تواند به آدرس ما درخواست بفرستد، اما
    Same-Origin Policy اجازه نمی‌دهد *پاسخ* را بخواند. پس توکن را
    هرگز نمی‌بیند.
    """
    tag = (
        '<script>window.__TOOLBOX_TOKEN__ = "%s";\n'
        'window.__TOOLBOX_PREVIEW_TOKEN__ = "%s";</script>\n'
        % (SESSION_TOKEN, PREVIEW_TOKEN)
    )
    lower = html_text.lower()
    idx = lower.find("<head>")
    if idx != -1:
        cut = idx + len("<head>")
        return html_text[:cut] + "\n" + tag + html_text[cut:]
    # اگر <head> نبود، ابتدای فایل
    return tag + html_text


# ──────────────────── رمزنگاری کلید API (C-5) ────────────────────
#
# روی ویندوز از DPAPI استفاده می‌کنیم: کلید رمزنگاری به حساب کاربری
# ویندوز گره می‌خورد. یعنی اگر کسی فایل app_settings.json را کپی کند و
# روی رایانهٔ دیگری ببرد، نمی‌تواند بازش کند — و کاربر هم لازم نیست
# رمز جداگانه‌ای به خاطر بسپارد.
#
# روی سیستم‌های غیرویندوزی (توسعه/تست) رمزنگاری در دسترس نیست؛ در آن
# حالت مقدار دست‌نخورده می‌ماند و صادقانه گزارش می‌شود.

_ENC_PREFIX = "enc:v1:"


def _dpapi_available():
    if os.name != "nt":
        return False
    try:
        import win32crypt  # noqa: F401
        return True
    except Exception:
        return False


def encrypt_secret(plain):
    """رمزنگاری. اگر ممکن نباشد، همان متن خام برمی‌گردد."""
    if not plain or plain.startswith(_ENC_PREFIX):
        return plain
    if not _dpapi_available():
        return plain
    try:
        import base64
        import win32crypt
        blob = win32crypt.CryptProtectData(
            plain.encode("utf-8"), "PCRepairToolbox", None, None, None, 0
        )
        return _ENC_PREFIX + base64.b64encode(blob).decode("ascii")
    except Exception:
        return plain


def decrypt_secret(stored):
    """بازگشایی. مقادیر رمزنشدهٔ قدیمی بدون تغییر برمی‌گردند."""
    if not stored or not stored.startswith(_ENC_PREFIX):
        return stored
    if not _dpapi_available():
        return ""          # رمز شده ولی نمی‌توانیم بازش کنیم
    try:
        import base64
        import win32crypt
        raw = base64.b64decode(stored[len(_ENC_PREFIX):])
        _desc, data = win32crypt.CryptUnprotectData(raw, None, None, None, 0)
        return data.decode("utf-8")
    except Exception:
        return ""


def mask_secret(value):
    """
    نمایش ایمن برای رابط کاربری: gsk_abc...wxyz
    کاربر باید بتواند تشخیص دهد کدام کلید ذخیره شده، بدون افشای آن.
    """
    if not value:
        return ""
    plain = decrypt_secret(value) if value.startswith(_ENC_PREFIX) else value
    if not plain:
        return "••••••••"
    if len(plain) <= 12:
        return plain[:2] + "•" * (len(plain) - 2)
    return f"{plain[:6]}…{plain[-4:]}"


def is_encrypted(value):
    return bool(value) and str(value).startswith(_ENC_PREFIX)


# ─────────────── ناشناس‌سازی داده‌های تشخیصی (ص-۳) ───────────────
#
# گزارش‌های تشخیصی نام کاربری، نام رایانه و مسیرهای خانگی را در بر
# دارند و همهٔ اینها به سرور هوش مصنوعی می‌رود. برای عیب‌یابی لازم
# نیستند، پس پیش از ارسال جایگزین می‌شوند.

def _real_identifiers():
    """شناسه‌های واقعی این دستگاه که باید پنهان شوند."""
    ids = {}
    try:
        user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
        if user and len(user) >= 3:
            ids["user"] = user
    except Exception:
        pass
    try:
        import socket
        host = socket.gethostname()
        if host and len(host) >= 3:
            ids["host"] = host
    except Exception:
        pass
    return ids


def anonymize(text):
    """
    جایگزینی شناسه‌های شخصی با برچسب عمومی.
    ترتیب مهم است: اول مسیرها (طولانی‌تر) بعد نام تنها.
    """
    if not text:
        return text
    out = str(text)
    ids = _real_identifiers()

    user = ids.get("user")
    if user:
        # مسیرها با هر دو نوع اسلش
        for sep in ("\\", "/"):
            out = out.replace(f"C:{sep}Users{sep}{user}", f"C:{sep}Users{sep}<USER>")
            out = out.replace(f"c:{sep}users{sep}{user.lower()}", f"c:{sep}users{sep}<USER>")
        # نام کاربری تنها (مثلاً در خروجی whoami)
        out = out.replace(user, "<USER>")
        if user.lower() != user:
            out = out.replace(user.lower(), "<USER>")

    host = ids.get("host")
    if host:
        out = out.replace(host, "<PC>")
        if host.lower() != host:
            out = out.replace(host.lower(), "<PC>")

    # SIDها: S-1-5-21-... را تا سه بخش آخر می‌بُریم
    import re
    out = re.sub(r"S-1-5-21-[\d-]+", "S-1-5-21-<SID>", out)

    return out


def anonymize_messages(messages):
    """اعمال ناشناس‌سازی روی آرایهٔ پیام‌های چت."""
    if not messages:
        return messages
    result = []
    for m in messages:
        if isinstance(m, dict) and isinstance(m.get("content"), str):
            mm = dict(m)
            mm["content"] = anonymize(m["content"])
            result.append(mm)
        else:
            result.append(m)
    return result
