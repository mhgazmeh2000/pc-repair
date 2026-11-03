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


def _parse_proxy_server(server):
    """
    مقدار ProxyServer رجیستری را به دیکشنری requests تبدیل می‌کند.

    فرمت‌های پشتیبانی‌شده:
        "127.0.0.1:8080"                                   (همهٔ پروتکل‌ها)
        "http=127.0.0.1:8080;https=127.0.0.1:8080;socks=..."
    اولویت: https → http → socks. چون همهٔ مقصدهای برنامه HTTPS
    هستند و HTTP proxy به PySocks هم نیاز ندارد، فقط وقتی socks سر
    آخر است از آن استفاده می‌کنیم (مثلاً وقتی ابزاری فقط socks ثبت
    کرده باشد).
    """
    server = (server or "").strip()
    if not server:
        return None

    if "=" not in server:
        u = _norm_proxy(server, "http")
        return {"http": u, "https": u} if u else None

    parts = {}
    for chunk in server.split(";"):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k.strip().lower()] = v.strip()

    out = {}
    if parts.get("https"):
        out["https"] = _norm_proxy(parts["https"], "http")
    if parts.get("http"):
        out["http"] = _norm_proxy(parts["http"], "http")
    if not out.get("https") and out.get("http"):
        out["https"] = out["http"]
    if not out:                                  # فقط socks= ثبت شده
        u = _norm_proxy(parts.get("socks") or "", "socks5h")
        if u:
            out = {"http": u, "https": u}
    out = {k: v for k, v in out.items() if v}
    return out or None


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
        return _parse_proxy_server(server)
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


# الگوهای آداپتورهای تونل/VPN رایج — فقط برای «اطلاع‌رسانی» UI.
# این ابزارها (Psiphon حالت VPN، VPN خود ویندوز، VeePN، WireGuard،
# OpenVPN و...) تونل شبکه می‌سازند نه پروکسی HTTP/SOCKS؛ درخواست‌های
# مستقیم برنامه به‌طور شفاف از route ویندوز و تونل عبور می‌کنند.
_TUN_PATTERNS = [
    (re.compile(r'veepn', re.I), "VeePN"),
    (re.compile(r'psiphon', re.I), "Psiphon"),
    # Hotspot Shield: نام آداپتورش هیچ‌کدام از واژه‌های رایج VPN را ندارد
    (re.compile(r'hotspot|anchorfree|hsstap|hsswd|\bhss\b', re.I),
     "Hotspot Shield"),
    (re.compile(r'wireguard|wintun', re.I), "WireGuard/Wintun"),
    (re.compile(r'openvpn|tun-?tap|tap-?windows', re.I), "OpenVPN/TAP"),
    # VPN خود ویندوز (Settings→VPN): آداپتور WAN Miniport است، وقتی هم
    # وصل نیست اصلاً آداپتور ندارد (برایش rasdial/Get-VpnConnection
    # را هم می‌خوانیم — پایین‌تر).
    (re.compile(r'wan.?miniport|ikev2|\bl2tp\b|sstp|pptp', re.I),
     "VPN ویندوز"),
    (re.compile(r'\bvpn\b|vpn-|openconnect|cisco anyconnect', re.I),
     "VPN سیستمی"),
    (re.compile(r'hiddify|v2ray|sing-?box|clash', re.I), "ابزار تونل"),
]


def _tun_kind(adapter_name):
    """نوع ابزار تونل را از نام/توضیح آداپتور حدس می‌زند."""
    for pat, label in _TUN_PATTERNS:
        if pat.search(adapter_name or ""):
            return label
    return None


def _detect_tun_vpns():
    """
    فهرست آداپتورهای تونل/VPN فعال — صرفاً اطلاع‌رسانی.

    خروجی: {"detected": bool, "adapters": [{"name","kind"}], "kinds": [...]}
    """
    if os.name != "nt":
        return {"detected": False, "adapters": [], "kinds": []}
    try:
        import subprocess
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
               "Get-NetAdapter -IncludeHidden | Where-Object { $_.Status -eq 'Up' } | Select-Object Name, InterfaceDescription | ConvertTo-Json -Compress"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=7,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        import json as _json
        rows = []
        try:
            data = _json.loads(r.stdout or "[]")
            rows = data if isinstance(data, list) else [data]
        except Exception:
            rows = []
        adapters, kinds = [], []
        for row in rows:
            if not isinstance(row, dict):
                continue
            for field in ("Name", "InterfaceDescription"):
                val = str(row.get(field) or "")
                kind = _tun_kind(val)
                if kind and val:
                    adapters.append({"name": val, "kind": kind})
                    if kind not in kinds:
                        kinds.append(kind)
                    break
        return {"detected": bool(adapters), "adapters": adapters[:6],
                "kinds": kinds}
    except Exception:
        return {"detected": False, "adapters": [], "kinds": []}


def _parse_rasdial(text):
    """
    خروجی rasdial را پارس می‌کند — نام VPNهای «وصل‌شده».

    نمونهٔ خروجی وصل:
        Connected to Work VPN
        Command completed successfully.
    خروجی قطع:
        No connections
    """
    conns = []
    for line in (text or "").splitlines():
        line = line.strip()
        if line.lower().startswith("connected to "):
            name = line[len("connected to "):].strip()
            if name:
                conns.append(name)
    return conns


def _parse_vpn_json(text):
    """خروجی JSONِ Get-VpnConnection را پارس می‌کند (نام + وضعیت)."""
    import json as _json
    try:
        d = _json.loads(text or "[]")
    except Exception:
        return []
    if isinstance(d, dict):
        d = [d]
    out = []
    for row in d:
        if isinstance(row, dict):
            name = str(row.get("Name") or "").strip()
            status = str(row.get("ConnectionStatus") or "").strip()
            if name:
                out.append({"name": name, "status": status})
    return out


def _detect_windows_vpn():
    """
    VPNهای بخش Settings ← Network & internet ← VPN ویندوز (RAS).

    برخلاف ابزارهای ثالث، این VPNها وقتی وصل نباشند آداپتوری ندارند؛
    پس منبع درست خود RAS است:
      rasdial          → فهرست وصل‌شده‌ها (سبک، همه‌جا هست)
      Get-VpnConnection → همهٔ پیکربندی‌شده‌ها + وضعیت (قطع/وصل)

    خروجی: {"connected": [نام...], "configured": [{name,status}...]}
    """
    res = {"connected": [], "configured": []}
    if os.name != "nt":
        return res
    import subprocess
    try:
        r = subprocess.run(
            ["rasdial"], capture_output=True, text=True, timeout=7,
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        res["connected"] = _parse_rasdial(r.stdout or "")
    except Exception:
        pass
    try:
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
               "Get-VpnConnection | Select-Object Name,ConnectionStatus "
               "| ConvertTo-Json -Compress"]
        r2 = subprocess.run(cmd, capture_output=True, text=True, timeout=7,
                            errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        res["configured"] = _parse_vpn_json(r2.stdout or "")
    except Exception:
        pass
    return res


def _detect_veepn():
    """سازگاری با نسخه‌های قبل — فقط VeePN را گزارش می‌دهد."""
    t = _detect_tun_vpns()
    names = [a["name"] for a in t["adapters"] if a["kind"] == "VeePN"]
    return {"detected": bool(names), "details": names[:5]}


def system_proxy_info():
    """اطلاعات نمایشی پروکسی سیستم و سازگاری VPN برای رابط کاربری."""
    p = get_system_proxy(force=True)
    veepn = _detect_veepn()
    tun = _detect_tun_vpns()
    wvpn = _detect_windows_vpn()

    adapters = list(tun["adapters"])
    kinds = list(tun["kinds"])
    # VPN وصل‌شدهٔ خود ویندوز هم عملاً یک تونل فعال است
    for name in wvpn.get("connected", []):
        adapters.append({"name": name, "kind": "VPN ویندوز"})
        if "VPN ویندوز" not in kinds:
            kinds.append("VPN ویندوز")

    base = {"veepn": veepn, "tun_vpns": adapters, "tun_kinds": kinds,
            "windows_vpn": wvpn}
    if not p:
        return dict(base, found=False, proxies=None, proxies_list=[])
    seen, lst = set(), []
    for scheme, url in p.items():
        if url not in seen:
            seen.add(url)
            lst.append(f"{scheme}: {url}")
    return dict(base, found=True, proxies=p, proxies_list=lst)


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


def _is_local_target(url):
    """
    آیا مقصد همین سیستم است؟ (Ollama/LM Studio روی 127.0.0.1)

    درخواست به مقصد محلی هرگز نباید از پروکسی عبور کند — پروکسیِ
    خارجی نه‌تنها کمکی نمی‌کند، بلکه خطاهای عجیبی مثل
    «400 The plain HTTP request was sent to HTTPS port» می‌دهد.
    """
    try:
        from urllib.parse import urlparse
        h = (urlparse(url).hostname or "").lower()
        return h in ("127.0.0.1", "localhost", "::1", "0.0.0.0")
    except Exception:
        return False


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

    # مقصد محلی (Ollama/LM Studio) — هرگز از پروکسی عبور نکن
    if proxies and _is_local_target(target):
        proxies, via = None, "مستقیم (مقصد محلی)"

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


def forward_ai_request(url, headers, payload=None, method='POST',
                       use_socks=None, timeout=None):
    """
    درخواست را با حالت اتصال انتخابی ارسال می‌کند.

    اگر حالت «پروکسی سیستم» باشد و پروکسی جواب ندهد، یک بار هم
    مستقیم امتحان می‌شود (و برعکس) — چون کاربر ممکن است وسط کار
    سایفون را ببندد یا باز کند. خطاهای گذرا (مثل ReadTimeout) یک بار
    همان مسیر دوباره امتحان می‌شوند.

    timeout: مهلت اختصاصی این درخواست (ثانیه). برای کاوشِ سریع
    رایگان‌بودن مدل‌ها استفاده می‌شود تا مسیرهای مرده ۱۸۰ ثانیه
    کاربر را معطل نکنند.
    """
    st = _settings()
    verify = st.get("verify_tls", True)
    # تحلیل‌های Defender/GPU و خروجی DISM ممکن است زمان زیادی برای پاسخ
    # اول مدل نیاز داشته باشند. حداقل ۱۸۰ ثانیه از HTTP 0 ناشی از
    # ReadTimeout کوتاه جلوگیری می‌کند. اگر فراخواننده مهلت اختصاصی
    # داده باشد (کاوش مدل)، همان اعمال می‌شود.
    try:
        default_timeout = max(180, int(st.get("request_timeout", 180)))
    except (TypeError, ValueError):
        default_timeout = 180
    if timeout is None:
        timeout = default_timeout
    else:
        # مهلت صریحِ فراخواننده (کاوش مدل) عیناً اعمال می‌شود؛
        # فقط مقدار نامعتبر به پیش‌فرض برمی‌گردد.
        try:
            timeout = int(timeout)
            if timeout < 1:
                timeout = default_timeout
        except (TypeError, ValueError):
            timeout = default_timeout
    req_headers = _headers(headers)

    proxies, via = _resolve_proxies()

    # مقصد محلی (Ollama/LM Studio) — پروکسی بی‌معنا و مضر است؛ حتی
    # مسیر جایگزین (پروکسی سیستم) هم برای مقصد محلی امتحان نشود.
    local_tgt = _is_local_target(url)
    if proxies and local_tgt:
        proxies, via = None, "مستقیم (مقصد محلی)"
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
    alt_px = None if (proxies or local_tgt) else get_system_proxy()
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
                msg = f"{label}: {type(e).__name__}: {str(e)[:160]}"
                # از تکرارِ یک خطای یکسان (retry همان مسیر) در پیام نهایی پرهیز کن
                if not attempts or attempts[-1] != msg:
                    attempts.append(msg)
                # ReadTimeout یعنی «کل مهلت (مثلاً ۱۸۰ ثانیه) هیچ بایتی
                # نیامد» — تلاش دوباره روی همان مسیر فقط چند دقیقهٔ دیگر
                # معطل کاربر می‌شود. مسیر جایگزین (اگر باشد) امتحان می‌شود.
                if type(e).__name__ == "ReadTimeout":
                    break
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

    # مقصد محلی (Ollama/LM Studio) — از پروکسی عبور نکن و مسیر جایگزین
    # (پروکسی سیستم) را هم برایش امتحان نکن.
    local_tgt = _is_local_target(url)
    if proxies and local_tgt:
        proxies, via = None, "مستقیم (مقصد محلی)"

    # استریم: فقط اتصال سقف کوتاه دارد. برای خواندن پاسخ سقف زمانی نمی‌گذاریم؛
    # مدل‌های reasoning یا حلقهٔ NEED_INFO ممکن است بیش از چند دقیقه پیش از
    # اولین/آخرین توکن زمان ببرند. کاربر از UI می‌تواند درخواست را لغو کند.
    stream_timeout = (min(timeout, 10), None)

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
    alt_px = None if (proxies or local_tgt) else get_system_proxy()
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
