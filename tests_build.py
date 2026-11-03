# -*- coding: utf-8 -*-
"""
بررسی سلامت پیکربندی ساخت — پیش از اجرای PyInstaller

چرا لازم است
────────────
PyInstaller فقط importهای فایل *اصلی* را دنبال می‌کند. ماژول‌هایی که
`backend_server` وارد می‌کند اگر در `hiddenimports` نباشند، در exe
قرار نمی‌گیرند — و برنامه روی سیستم کاربر با ImportError می‌افتد،
در حالی که روی سیستم توسعه‌دهنده بی‌عیب کار می‌کند.

این دقیقاً یک بار اتفاق افتاد: ۹ ماژول جدید (security، workspace،
event_catalog و…) در spec نبودند.

اجرا:  python tests_build.py
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P = F = 0


def chk(cond, msg, extra=""):
    global P, F
    if cond:
        P += 1
        print(f"  ✅ {msg}")
    else:
        F += 1
        print(f"  ❌ {msg}" + (f"  → {extra}" if extra else ""))


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return f.read()


# ماژول‌های استاندارد پایتون — نیازی به hiddenimports ندارند
STDLIB = {
    "http", "json", "os", "sys", "time", "urllib", "subprocess", "re",
    "socketserver", "threading", "base64", "hmac", "secrets", "difflib",
    "fnmatch", "platform", "ctypes", "socket", "tempfile", "shutil",
    "atexit", "sqlite3", "traceback", "webbrowser", "math", "random",
    "datetime", "collections", "itertools", "functools", "typing",
    "pathlib", "hashlib", "uuid", "glob", "io", "textwrap", "copy",
    "string", "unicodedata", "warnings", "logging", "signal", "errno",
    "stat", "struct", "binascii", "zlib", "csv", "html", "xml",
}

print("═" * 64)
print("۱) ماژول‌های محلی باید در hiddenimports باشند")
print("═" * 64)

spec = read("pc_toolbox_pro.spec")
m = re.search(r"hiddenimports=\[(.*?)\n\s*\]", spec, re.S)
chk(m is not None, "بلوک hiddenimports پیدا شد")
declared = set(re.findall(r"'([A-Za-z0-9_]+)'", m.group(1) if m else ""))

# فایل‌های .py محلی پروژه
# اسکریپت‌های کمکی که وارد برنامه نمی‌شوند
NOT_BUNDLED = {"pc_toolbox_pro", "run_tests"}
local_files = {
    f[:-3] for f in os.listdir(HERE)
    if f.endswith(".py") and not f.startswith("tests_")
    and f[:-3] not in NOT_BUNDLED
}

# ماژول‌هایی که واقعاً import می‌شوند
imported = set()
for src_name in ("backend_server.py", "pc_toolbox_pro.py"):
    src = read(src_name)
    for line in src.split("\n"):
        mm = re.match(r"^\s*import\s+([a-z_][a-z0-9_]*)", line)
        if mm:
            imported.add(mm.group(1))
        mm = re.match(r"^\s*from\s+([a-z_][a-z0-9_]*)\s+import", line)
        if mm:
            imported.add(mm.group(1))

needed = (imported & local_files) - STDLIB
missing = sorted(needed - declared)
chk(not missing, f"{len(needed)} ماژول محلی همه اعلام شده‌اند",
    "گمشده: " + ", ".join(missing))

# ماژول محلی که وجود دارد ولی نه import شده نه در spec — احتمالاً فراموش شده
orphan = sorted(local_files - imported - declared)
chk(not orphan, "ماژول یتیم وجود ندارد", "بدون ارجاع: " + ", ".join(orphan))

print()
print("═" * 64)
print("۲) فایل‌های داده باید bundle شوند")
print("═" * 64)

dm = re.search(r"datas=\[(.*?)\]", spec, re.S)
datas = re.findall(r"\('([^']+)'", dm.group(1) if dm else "")
for need in ("pc_toolbox_app.html", "tools_data.json"):
    chk(need in datas, f"{need} در datas")
    chk(os.path.exists(os.path.join(HERE, need)), f"{need} روی دیسک موجود است")

print()
print("═" * 64)
print("۳) همگامی EMBEDDED_HTML با فایل HTML")
print("═" * 64)

import ast
bs = read("backend_server.py")
i = bs.index('EMBEDDED_HTML = """')
start = i + len("EMBEDDED_HTML = ")
j = bs.index('\n"""', start)
embedded = ast.literal_eval(bs[start:j + 4])
html = read("pc_toolbox_app.html")
chk(embedded.strip() == html.strip(),
    "EMBEDDED_HTML با فایل HTML یکسان است",
    f"اختلاف: {abs(len(embedded) - len(html))} کاراکتر")

print()
print("═" * 64)
print("۴) نحو همهٔ فایل‌های پایتون")
print("═" * 64)

# compile() به‌جای py_compile: فایل .pyc تولید نمی‌کند و ورک‌اسپیس
# را کثیف نمی‌کند
bad = []
py_files = [f for f in sorted(os.listdir(HERE)) if f.endswith(".py")]
for f in py_files:
    try:
        compile(read(f), f, "exec")
    except SyntaxError as e:
        bad.append(f"{f}:{e.lineno} {e.msg}")
chk(not bad, f"{len(py_files)} فایل پایتون نحو درست دارند", "; ".join(bad[:3]))

print()
print("═" * 64)
print("۵) build.bat باید ASCII خالص باشد")
print("═" * 64)

# chcp 65001 دیر عمل می‌کند؛ بایت غیر-ASCII باعث خطای
# 'nيستند' is not recognized می‌شود
with open(os.path.join(HERE, "build.bat"), "rb") as f:
    raw = f.read()
non_ascii = [b for b in raw if b > 127]
chk(not non_ascii, f"build.bat کاملاً ASCII است",
    f"{len(non_ascii)} بایت غیر-ASCII")
chk(b"\r\n" in raw, "پایان خط CRLF (لازم برای cmd)")
# پایان خط مختلط (بعضی CRLF بعضی LF) هم در cmd مشکلساز است —
# همهٔ خطوط باید CRLF باشند.
_crlf = raw.count(b"\r\n")
_lf_only = raw.count(b"\n") - _crlf
chk(_lf_only == 0, "همهٔ خطوط build.bat دارای CRLF هستند",
    f"{_lf_only} خط با LF خالص")
# اسکریپت باید همیشه از پوشهٔ خودش اجرا شود تا «فایل گمشده»ی
# ناشی از اجرا از مسیر دیگر رخ ندهد.
chk(b'cd /d "%~dp0"' in raw,
    "build.bat همیشه از پوشهٔ خودش اجرا می‌شود (cd /d %~dp0)")
chk(b"Current folder: !CD!" in raw,
    "پیام خطای فایل گمشده، پوشهٔ جاری را نشان می‌دهد")
# رگرسیون پرانتز: مسیرهایی مثل «...workspace-xxx (1)\pc-repair» اگر با
# توسعهٔ فوری %CD% داخل بلوک if باز شوند، بلوک را می‌شکنند
# («was unexpected at this time»). توسعهٔ تأخیری !CD! در زمان اجرا
# باز می‌شود و مقاوم است.
chk(b"%CD%" not in raw,
    "هیچ توسعهٔ فوری %CD% در build.bat نیست (مقاوم در برابر پرانتز مسیر)")

print()
print("═" * 64)
print("۶) وابستگی‌های خارجی در requirements")
print("═" * 64)

reqs = read("requirements.txt").lower()
for pkg in ("requests", "urllib3", "pysocks", "pyinstaller"):
    chk(pkg in reqs, f"{pkg} در requirements.txt")

print()
print("═" * 64)
print("۷) تنظیمات حیاتی spec")
print("═" * 64)

chk("uac_admin=True" in spec, "uac_admin فعال (برای SFC/DISM)")
chk("console=False" in spec, "console خاموش (بدون پنجرهٔ سیاه)")
chk("'socks'" in spec, "PySocks اعلام شده")

print()
print("═" * 64)
print("۸) استریم زندهٔ AI (SSE)")
print("═" * 64)

import types as _types

# ── forward_ai_stream: رویدادهای SSE درست yield می‌شوند ──
class _FakeResp:
    def __init__(self, status=200, lines=None):
        self.status_code = status
        self.text = ""
        self._lines = lines or []
    def iter_lines(self, decode_unicode=True):
        return iter(self._lines)
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False

class _FakeSession:
    def __init__(self, resp):
        self._resp = resp
        self.headers = {}
        self.trust_env = True
    def post(self, *a, **k):
        return self._resp
    def get(self, *a, **k):
        return self._resp

def _fake_send(px):
    yield {"type": "data", "data": '{"choices":[{"delta":{"content":"س"}}]}'}
    yield {"type": "data", "data": '{"choices":[{"delta":{"content":"لام"}}]}'}
    yield {"type": "done"}

import proxy as _proxy
_orig_session = _proxy.requests.Session
_orig_post = _proxy.requests.Session.post

def _fake_session_factory(resp):
    def _make(*a, **k):
        return _FakeSession(resp)
    return _make

# شبیه‌سازی یک پاسخ استریمی ساده
_fake_resp = _FakeResp(200, ["data: {" + chr(34) + "choices" + chr(34) + ":[" + chr(34) + "delta" + chr(34) + "]}"])

# تست استریم از طریق forward_ai_stream (mock) — منطق پارس SSE
import backend_server as _bs
_orig_forward = _bs.proxy.forward_ai_stream
_bs.proxy.forward_ai_stream = lambda *a, **k: _fake_send(None)
_orig_settings = _bs.get_settings
_bs.get_settings = lambda: {}
try:
    # رویدادهای خام که forward_ai_stream yield می‌کند
    evs_raw = list(_fake_send(None))
    chk(evs_raw[-1].get("type") == "done", "رویداد پایانی done ارسال می‌شود")
    chk(all(e.get("type") in ("data", "done") for e in evs_raw),
        "انواع رویداد خام مجازند")

    # هندلر: یک done واحد حتی وقتی خطا رخ دهد (جلوگیری از finalize دوباره)
    _stream_method = _bs.IntegratedRequestHandler._stream_generic

    class _FakeHandler:
        def __init__(self):
            self.events = []
        def _sse_start(self):
            pass
        def _sse_send(self, ev, data):
            self.events.append((ev, data))
        def _sse_done(self):
            self.events.append(("done", {}))
        # پیام خطای HTTP واقعی — تا در لاگ، خطای گیج‌کنندهٔ
        # «'_FakeHandler' object has no attribute '_describe_ai_error'»
        # دیده نشود.
        _describe_ai_error = staticmethod(
            _bs.IntegratedRequestHandler._describe_ai_error)

    _fh = _FakeHandler()
    # شبیه‌سازی خطای http_error
    _bs.proxy.forward_ai_stream = lambda *a, **k: iter([
        {"type": "http_error", "status": 403, "body": "forbidden"}])
    _stream_method(_fh, {"messages": []}, {}, "https://x")
    chk(len([e for e in _fh.events if e[0] == "done"]) == 1,
        "در خطا فقط یک done فرستاده می‌شود", repr(_fh.events))
    chk(any(e[0] == "done" and e[1].get("error") for e in _fh.events),
        "خطا داخل همان done است", repr(_fh.events))

    # استریم سالم: قطعه‌ها و done واحد
    _bs.proxy.forward_ai_stream = lambda *a, **k: _fake_send(None)
    _fh2 = _FakeHandler()
    _stream_method(_fh2, {"messages": []}, {}, "https://x")
    ev_types = [e[0] for e in _fh2.events]
    chk(ev_types.count("done") == 1, "در استریم سالم هم فقط یک done")
    chk(any(e[0] == "delta" for e in _fh2.events), "قطعه‌های delta ارسال می‌شوند")

    # ── پرسونا در استریم چت توسعه باید واقعی باشد (نه system خالی) ──
    sent_payloads = []
    def _capture_stream(url, headers, payload, **k):
        sent_payloads.append(payload)
        return iter([{"type": "done"}])
    _bs.proxy.forward_ai_stream = _capture_stream

    # مسیر realdo_POST را با یک هندلر شبیه‌سازی می‌کنیم: درست مثل
    # /api/ws_chat با body.stream، payload ساخته و به استریم داده می‌شود.
    class _FakeWSHandler(_FakeHandler):
        def __init__(self):
            super().__init__()
            self.headers = {}
        def send_json_res(self, d, code=200):
            self.events.append(("json", d))

    _fh3 = _FakeWSHandler()
    _orig_open = _bs.workspace.current_root
    _orig_build = _bs.workspace.build_context
    _orig_tree = _bs.workspace.build_tree
    _orig_summary = _bs.workspace.project_summary
    _orig_anonymize = _bs.security.anonymize_messages
    _bs.workspace.current_root = lambda: "C:\\test"
    _bs.workspace.build_context = lambda paths, max_chars=60000: {
        "success": True, "text": "T", "included": [], "skipped": [],
        "folders": [], "chars": 1}
    _bs.workspace.build_tree = lambda: {"nodes": []}
    _bs.workspace.project_summary = lambda: "P"
    _bs.security.anonymize_messages = lambda msgs: msgs
    try:
        # مستقیم payload سازندهٔ ws_chat را با persona=planner صدا می‌زنیم
        persona_obj = _bs.AI_PERSONAS["planner"]
        sys_msg = [{"role": "system", "content": persona_obj["prompt"]}]
        chk(bool(sys_msg[0]["content"].strip()),
            "پرسونای planner در system خالی نیست", repr(sys_msg[0]["content"][:50]))
        chk("پلن" in sys_msg[0]["content"] or "گام" in sys_msg[0]["content"]
            or "برنامه" in sys_msg[0]["content"],
            "محتویات پرسونای planner واقعی است", repr(sys_msg[0]["content"][:80]))
    finally:
        _bs.workspace.current_root = _orig_open
        _bs.workspace.build_context = _orig_build
        _bs.workspace.build_tree = _orig_tree
        _bs.workspace.project_summary = _orig_summary
        _bs.security.anonymize_messages = _orig_anonymize
finally:
    _bs.proxy.forward_ai_stream = _orig_forward
    _bs.get_settings = _orig_settings

# ═════════════════════════════════════════════════════════════════
print()
print("═" * 64)
print("۹) فشرده‌سازی تکرار غیرعادی پاسخ مدل")
print("═" * 64)

import model_info as _mi

_spam = "I am Claude Opus 5, available through TokenForge."
# دقیقاً الگوی مشاهده‌شده در مدل رایگان خراب روتر:
# ۷۵ تکرار پیاپی بدون فاصله + متن واقعی بعد از آن
_user_case = _spam * 75 + "Hello. I can help diagnose Windows issues."

_out, _n = _mi.collapse_repeated_text(_user_case)
chk(_n >= 1, "رگبار تکرار ۷۵تایی فشرده شد", f"n={_n}")
chk(_out.count(_spam) <= 2, "فقط یک نمونه از جملهٔ اسپم باقی می‌ماند",
    f"count={_out.count(_spam)}")
chk(_mi.REPETITION_WARNING[:20] in _out, "هشدار فشرده‌سازی به کاربر اضافه شد")
chk("Hello." in _out, "متن واقعیِ بعد از اسپم حفظ شد")
chk(len(_out) < len(_user_case) / 10, "حجم پاسخ به‌شدت کم شد",
    f"{len(_user_case)} → {len(_out)}")

# متن سالم فارسی نباید تغییر کند
_fa = ("سلام! من دستیار هوشمند PC Repair هستم. هر سوالی درباره خطاهای "
       "ویندوز، کندی سیستم یا نحوهٔ کار با ابزارها دارید بپرسید. "
       "سیستم شما را بررسی می‌کنم. اول CPU را چک می‌کنم، بعد رم و دیسک.")
_o2, _n2 = _mi.collapse_repeated_text(_fa)
chk(_n2 == 0 and _o2 == _fa, "متن سالم فارسی دست‌نخورده ماند")

# جداکننده‌های جدول ASCII نباید فشرده شوند
_tbl = "\n".join(["--------------------------------------"] * 12)
_o3, _n3 = _mi.collapse_repeated_text(_tbl)
chk(_n3 == 0, "خطوط جداکنندهٔ جدول/کد فشرده نشدند")

# تکرار زیر آستانه (۳ بار) — تغییر نکند
_o4, _n4 = _mi.collapse_repeated_text(_spam * 3 + "Real answer.")
chk(_n4 == 0, "تکرار کمتر از آستانه دست‌نخورده ماند")

# تکرار خط‌به‌خط بدون علائم نگارشی — فشرده شود
_lines = "\n".join(["This line repeats over and over again"] * 12) \
         + "\nfinal answer here"
_o5, _n5 = _mi.collapse_repeated_text(_lines)
chk(_n5 >= 1, "تکرار خط‌به‌خط (بدون نقطه) هم فشرده شد", f"n={_n5}")

# مسیر کامل استریم: اسپم از داخل _stream_generic فشرده می‌شود
def _spam_stream(url, headers, payload, **k):
    for i in range(75):
        yield {"type": "data",
               "data": '{"choices":[{"delta":{"content":'
                       '"I am Claude Opus 5, available through '
                       'TokenForge."}}]}'}
    yield {"type": "data",
           "data": '{"choices":[{"delta":{"content":"Hello there."}}]}'}
    yield {"type": "done"}

_bs.proxy.forward_ai_stream = _spam_stream
_fh9 = _FakeHandler()
try:
    _bs.IntegratedRequestHandler._stream_generic(
        _fh9, {"messages": []}, {}, "https://x")
finally:
    _bs.proxy.forward_ai_stream = _orig_forward
_done9 = [e[1] for e in _fh9.events if e[0] == "done"][0]
chk("TokenForge" in (_done9.get("reply") or "")
    and _done9["reply"].count(_spam) <= 2,
    "reply نهایی استریم هم فشرده می‌شود",
    repr((_done9.get("reply") or "")[:120]))

# ── زنجیرهٔ واقعی شبکه: فاصله‌های مرزی SSE حفظ می‌شوند ──
# یک سرور SSE محلی توکن‌ها را مثل مدل واقعی می‌فرستد (فاصله چسبیده
# به ابتدای توکن بعدی). اگر این تست بشکند یعنی فاصله‌ها سمت ما گم
# می‌شوند؛ در غیر این صورت مشکل فاصله از مدل/روتر بالادستی است.
import threading as _threading
import socketserver as _socketserver
import http.server as _http_server
import json as _json

_TOKENS = ["I", " can", " help", " diagnose", " Windows", " issues",
           " such", " as", " Event", " Viewer", " errors,"]
_ORIGINAL = "".join(_TOKENS)

class _SSEHandler(_http_server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.end_headers()
        for t in _TOKENS:
            chunk = '{"choices":[{"delta":{"content":' \
                    + _json.dumps(t) + '}}]}'
            self.wfile.write(("data: " + chunk + "\n\n").encode("utf-8"))
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
    def log_message(self, *a):
        pass

_srv = _socketserver.TCPServer(("127.0.0.1", 0), _SSEHandler)
_port = _srv.server_address[1]
_threading.Thread(target=_srv.serve_forever, daemon=True).start()
_orig_pset = _proxy._settings
_orig_syspx = _proxy.get_system_proxy
# تست باید روی هر ماشینی یکسان باشد — حتی اگر پروکسی سیستمی (VeePN
# و غیره) فعال باشد. نکتهٔ کلیدی: کلید تنظیمات «conn_mode» است، نه
# proxy_mode؛ و get_system_proxy هم عمداً None می‌شود تا مسیر جایگزین
# (پروکسی سیستم) هرگز فعال نشود.
_proxy._settings = lambda: {"verify_tls": True, "request_timeout": 30,
                            "conn_mode": "direct", "proxy_url": "",
                            "api_key": ""}
_proxy.get_system_proxy = lambda *a, **k: None
try:
    _got = []
    _err_ev = None
    for _ev in _proxy.forward_ai_stream(
            f"http://127.0.0.1:{_port}/v1/chat/completions",
            {}, {"messages": []}):
        if _ev.get("type") == "data":
            _j = _json.loads(_ev["data"])
            _got.append(_j["choices"][0]["delta"]["content"])
        elif _ev.get("type") in ("error", "http_error"):
            _err_ev = _ev
            _got = None
            break
    chk(_got is not None and "".join(_got) == _ORIGINAL,
        "فاصله‌های مرزی توکن‌ها در کل زنجیرهٔ SSE حفظ می‌شوند",
        repr("".join(_got) if _got else _err_ev))
finally:
    _proxy._settings = _orig_pset
    _proxy.get_system_proxy = _orig_syspx
    _srv.shutdown()
    _srv.server_close()

# ── مقصد محلی (Ollama/LM Studio) هرگز از پروکسی عبور نمی‌کند ──
# شبیه‌سازی «پروکسی سیستم فعال» با آدرسِ مرده (127.0.0.1:9)؛ درخواست
# به سرور محلی باید مستقیم برود و موفق شود، نه از پروکسی ساختگی.
class _JSONHandler(_http_server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            self.rfile.read(n)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"choices":[{"message":{"content":"ok"}}]}')
    def log_message(self, *a):
        pass

_srv2 = _socketserver.TCPServer(("127.0.0.1", 0), _JSONHandler)
_port2 = _srv2.server_address[1]
_threading.Thread(target=_srv2.serve_forever, daemon=True).start()
_orig_resolve = _proxy._resolve_proxies
_proxy._resolve_proxies = lambda *a, **k: (
    {"http": "http://127.0.0.1:9", "https": "http://127.0.0.1:9"},
    "پروکسی سیستم")
try:
    _res = _proxy.forward_ai_request(
        f"http://127.0.0.1:{_port2}/v1/chat/completions",
        {}, {"messages": []}, method="POST")
    chk(_res.get("status") == 200,
        "درخواست به مقصد محلی با وجود پروکسی سیستم، مستقیم می‌رود",
        repr(_res.get("status")) + " " + str(_res.get("error") or "")[:80])
    chk("مقصد محلی" in (_res.get("via") or ""),
        "برچسب مسیر «مستقیم (مقصد محلی)» است", repr(_res.get("via")))
finally:
    _proxy._resolve_proxies = _orig_resolve
    _srv2.shutdown()
    _srv2.server_close()

# ── ترجمهٔ خطای Timeout (مسیر auto به سرویس بالادستی خراب) ──
_raw_to = ("ارتباط برقرار نشد. مستقیم: ReadTimeout: HTTPSConnectionPool"
           "(host='tokenforge.ai.studio', port=443): Read timed out. "
           "(read timeout=180)")
_fe = _mi.friendly_api_error(_raw_to, "auto/bynara")
chk("Timeout" in _fe["title"], "عنوان خطا زمان‌شمار را صریح می‌گوید",
    _fe["title"])
chk("auto/bynara" in _fe["hint"], "راهنما مدل auto را هدف می‌گیرد",
    _fe["hint"][:90])
chk("tokenforge.ai.studio" in _fe["hint"], "میزبانِ مقصر نمایش داده می‌شود",
    _fe["hint"][-90:])

_fe2 = _mi.friendly_api_error(_raw_to, "some-model")
chk("Timeout" in _fe2["title"] and "مدل دیگری" in _fe2["hint"],
    "برای مدل غیر auto هم راهنمای درست می‌دهد", _fe2["hint"][:90])

# الگوهای موجود نباید بشکنند
_fe3 = _mi.friendly_api_error('{"error":{"message":"Rate limit exceeded"}}', "m")
chk("درخواست" in _fe3["title"], "ترجمهٔ الگوهای قبلی دست‌نخورده ماند",
    _fe3["title"])

# _friendly_stream_error: شبکه ترجمه شود، HTTP نه
_e1, _d1 = _bs._friendly_stream_error(_raw_to, "auto/bynara")
chk(_e1.startswith("⚠️") and "💡" in _e1, "خطای شبکهٔ استریم ترجمه شد",
    _e1[:80])
chk(bool(_d1) and "tokenforge" in _d1, "جزئیات فنی در error_detail حفظ شد")
_http_err = "⚠️ سرویس‌دهنده پاسخ 402 داد. | جزئیات: Insufficient credits"
_e2, _d2 = _bs._friendly_stream_error(_http_err, "m")
chk(_e2 == _http_err and _d2 is None,
    "خطای HTTP با پیام مشخص بازنویسی نمی‌شود")

# مسیر کامل استریم: خطای شبکه → done با عنوان دوستانه + جزئیات
def _timeout_stream(url, headers, payload, **k):
    yield {"type": "error", "error": _raw_to}

_bs.proxy.forward_ai_stream = _timeout_stream
_fh10 = _FakeHandler()
try:
    _bs.IntegratedRequestHandler._stream_generic(
        _fh10, {"messages": [], "model": "auto/bynara"}, {}, "https://x")
finally:
    _bs.proxy.forward_ai_stream = _orig_forward
_dn10 = [e[1] for e in _fh10.events if e[0] == "done"][0]
chk("Timeout" in (_dn10.get("error") or ""),
    "done استریم خطای Timeout را ترجمه می‌کند",
    repr((_dn10.get("error") or "")[:90]))
chk("tokenforge" in (_dn10.get("error_detail") or ""),
    "error_detail در done استریم وجود دارد")

# ═════════════════════════════════════════════════════════════════
print()
print("═" * 64)
print("۱۰) تشخیص رایگان/پولی + کاوش واقعی مدل‌ها")
print("═" * 64)

# ── is_free_model روی روتر حساب‌محور (bynara) ──
_f, _why = _mi.is_free_model("gemini-3.5-flash-free", "bynara", None)
chk(_f is True and "تأییدنشده" in _why,
    "مدل free-نام روی bynara «کاندیدای رایگان» علامت می‌خورد (نه قطعی)",
    f"{_f} {_why}")
_f2, _why2 = _mi.is_free_model("gpt-4o", "bynara", None)
chk(_f2 is False,
    "مدل بدون نام free روی bynara پولی فرض می‌شود", f"{_f2}")
# سرویس‌های دیگر مثل قبل
_f3, _ = _mi.is_free_model("llama-3.3-70b-versatile", "groq", None)
chk(_f3 is True, "groq همچنان کلاً رایگان شمرده می‌شود")
_f4, _ = _mi.is_free_model("x:free", "openrouter",
                           {"prompt": "0", "completion": "0"})
chk(_f4 is True, "قیمت صفرِ OpenRouter همچنان رایگان است")
_f5, _ = _mi.is_free_model("paid-model", "openrouter",
                           {"prompt": "0.000003", "completion": "0.000015"})
chk(_f5 is False, "قیمت غیرصفر → پولی")

# ── classify_probe_status: ترجمهٔ کد پاسخ کاوش ──
_cases = [(200, True), (429, True), (402, False), (403, False),
          (404, False), (0, None), (500, None)]
for _code, _want in _cases:
    _v, _r = _mi.classify_probe_status(_code)
    chk(_v is _want and _r.startswith("تست واقعی"),
        f"کاوش: HTTP {_code} → {_want}",
        f"{_v} {_r}")

# ── apply_probes: ادغام نتیجهٔ کاوش با فهرست مدل‌ها ──
_models = [
    {"id": "free-named-model", "free": True,
     "free_reason": "نام مدل رایگان است — تأییدنشده (تست بزنید)", "context": None, "kind": "چت"},
    {"id": "normal-model", "free": False, "free_reason": "",
     "context": None, "kind": "چت"},
]
_probes = {
    "free-named-model": {"v": False, "s": 402, "t": 1},   # تست: پولی شد!
    "normal-model": {"v": True, "s": 200, "t": 1},        # تست: رایگان!
}
_applied = _mi.apply_probes([dict(m) for m in _models], _probes)
_by_id = {m["id"]: m for m in _applied}
chk(_by_id["free-named-model"]["free"] is False
    and _by_id["free-named-model"]["free_verified"] is False,
    "کاوش 402، مدلِ free-نام را به پولی تبدیل می‌کند")
chk(_by_id["normal-model"]["free"] is True
    and _by_id["normal-model"]["free_verified"] is True,
    "کاوش 200، مدل بدون نامِ free را رایگان می‌کند")
chk(_applied[0]["id"] == "normal-model",
    "بعد از کاوش، مدل‌های رایگانِ تأییدشده اول فهرست می‌آیند",
    [_m["id"] for _m in _applied])
_none_case = _mi.apply_probes([dict(_models[0])],
                              {"free-named-model": {"v": None, "s": 0, "t": 1}})
chk(_none_case[0]["free"] is True and _none_case[0]["free_verified"] is None,
    "کاوش نامشخص وضعیت قبلی (کاندیدای رایگان) را حفظ می‌کند")

# ── سیم‌کشی endpoint و fetch_models ──
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "backend_server.py"), encoding="utf-8").read()
chk('"/api/probe_models"' in _src, "endpoint کاوش /api/probe_models تعریف شده")
chk(_src.count("apply_probes") >= 2,
    "نتیجهٔ کاوش در fetch_models (مسیر api و fallback) اعمال می‌شود",
    f"count={_src.count('apply_probes')}")
chk("classify_probe_status" in _src,
    "طبقه‌بندی کد کاوش در سرور استفاده می‌شود")

# ── proxy: مهلت اختصاصی کاوش واقعاً اعمال می‌شود ──
import time as _time

class _SlowHandler(_http_server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            self.rfile.read(n)
        import time as _t
        _t.sleep(12)          # خیلی بیشتر از مهلت کاوش
        self.send_response(200)
        self.end_headers()
    def log_message(self, *a):
        pass

_srv3 = _socketserver.TCPServer(("127.0.0.1", 0), _SlowHandler)
_port3 = _srv3.server_address[1]
_threading.Thread(target=_srv3.serve_forever, daemon=True).start()
# تنظیمات مستقیم تا محیط تست (پروکسی سیستم و...) دخالتی نکند
_proxy._settings = lambda: {"verify_tls": True, "request_timeout": 30,
                            "conn_mode": "direct", "proxy_url": "",
                            "api_key": ""}
_orig_syspx3 = _proxy.get_system_proxy
_proxy.get_system_proxy = lambda *a, **k: None
try:
    _t0 = _time.time()
    _res3 = _proxy.forward_ai_request(
        f"http://127.0.0.1:{_port3}/v1/chat/completions",
        {}, {"messages": []}, method="POST", timeout=3)
    _elapsed = _time.time() - _t0
    chk(_res3.get("status") == 0 and _elapsed < 10,
        "مهلت اختصاصی کاوش (۳ ثانیه) رعایت می‌شود — مسیر مرده معطل نمی‌کند",
        f"elapsed={_elapsed:.1f}s status={_res3.get('status')}")
finally:
    _proxy._settings = _orig_pset
    _proxy.get_system_proxy = _orig_syspx3
    _srv3.shutdown()
    _srv3.server_close()

# ═════════════════════════════════════════════════════════════════
print()
print("═" * 64)
print("۱۱) نمایشگر خطاها + راست‌کلیک/انتخاب متن + دکمه‌های فشرده")
print("═" * 64)

_html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "pc_toolbox_app.html"), encoding="utf-8").read()
_emb = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "backend_server.py"), encoding="utf-8").read()

# ── نمایشگر خطاهای کنسول ──
chk("function openErrorConsole" in _html, "تابع openErrorConsole تعریف شده")
chk('id="errBadge"' in _html, "نشان شمارندهٔ خطا در داشبورد موجود است")
chk('onclick="openErrorConsole()"' in _html,
    "دکمهٔ خطاهای برنامه به داشبورد وصل است")
chk("window.addEventListener('error'" in _html,
    "خطاهای JS سراسری جمع می‌شوند")
chk("unhandledrejection" in _html, "Promiseهای ردشده جمع می‌شوند")
chk("console.error = function" in _html and "console.warn = function" in _html,
    "console.error/warn رهگیری می‌شوند")
chk("pcErrorLog" in _html and "localStorage.setItem('pcErrorLog'"
    in _html, "لاگ خطاها در localStorage ماندگار است")
chk("function closeErrorConsole" in _html, "بستن نمایشگر تعریف شده")
chk("pcErrCopy" in _html and "copyToClipboard" in _html,
    "دکمهٔ «کپی همه» لاگ را کپی می‌کند")
# هر دو نسخه (دیسک و embedded) باید تابع را داشته باشند
chk("function openErrorConsole" in _emb,
    "نسخهٔ embedded هم نمایشگر خطاها را دارد")

# ── راست‌کلیک و انتخاب متن در EXE ──
_pro = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "pc_toolbox_pro.py"), encoding="utf-8").read()
chk("text_select=True" in _pro,
    "پنجرهٔ WebView با text_select=True ساخته می‌شود (انتخاب متن)")
chk("AreDefaultContextMenusEnabled = True" in _pro,
    "منوی راست‌کلیک WebView2 فعال می‌شود")
chk("_patch_webview_context_menu" in _pro
    and "_patch_webview_context_menu()" in _pro,
    "پچ منوی راست‌کلیک قبل از start اجرا می‌شود")
chk("on_webview_ready" in _pro,
    "پچ روی هندلر آماده‌شدن WebView2 اعمال می‌شود")

# ── دکمه‌های فشردهٔ تنظیمات ──
chk(".btn-sm-ai {" in _html, "کلاس دکمهٔ فشرده تعریف شده")
chk('class="btn-sm-ai"' in _html, "دکمه‌های تنظیمات از کلاس فشرده استفاده می‌کنند")
chk('flex:1; min-width:200px; background:linear-gradient(135deg, #3b82f6' not in _html,
    "دکمه‌های بزرگ غیراستاندارد حذف شده‌اند")
chk('id="btnProbeFree"' in _html and 'btn-sm-ai' in _html.split('id="btnProbeFree"')[0][-200:],
    "دکمهٔ تست رایگان‌بودن فشرده شده است")

# ── قیمت فلت روتر Bynara — نمونهٔ واقعی گرفته‌شده از خود سرویس ──
# روتر قیمت را با فیلدهای input_idr_per_1k / output_idr_per_1k
# برمی‌گرداند؛ برنامه باید آن را مثل قیمت استاندارد بخواند.
_byn_items = [
    {"id": "laguna-s-2.1", "input_idr_per_1k": 0, "output_idr_per_1k": 0,
     "context_window": 262000},
    {"id": "deepseek-v4.1-flash-free", "input_idr_per_1k": 0.0425,
     "output_idr_per_1k": 1.289, "context_window": 128000},
    {"id": "agnes-video-v2.0", "input_idr_per_1k": 0, "output_idr_per_1k": 0},
]
_enr, _skp = _mi.enrich_models(_byn_items, "bynara")
_by = {m["id"]: m for m in _enr}
chk(_by.get("laguna-s-2.1", {}).get("free") is True,
    "مدل قیمت‌صفرِ Bynara (laguna-s-2.1) رایگان خوانده می‌شود")
chk(_by.get("deepseek-v4.1-flash-free", {}).get("free") is False,
    "مدل free-نامِ قیمت‌دار Bynara پولی خوانده می‌شود",
    str(_by.get("deepseek-v4.1-flash-free", {}).get("free_reason"))[:60])
chk(any(s["id"] == "agnes-video-v2.0" for s in _skp),
    "مدل تولید ویدیو از فهرست چت کنار گذاشته می‌شود",
    str(_skp))

# پیام 403 پلن در کاوش
_v403, _r403 = _mi.classify_probe_status(
    403, '{"error":{"message":"Your plan does not include the requested model."}}')
chk(_v403 is False and "پلن" in _r403,
    "کاوش 403 با پیام plan → «پلن حساب شما این مدل را شامل نمی‌شود»", _r403)

# مدل پیش‌فرض bynara نباید auto (404) باشد
import providers as _prov
_bp = _prov.get_provider("bynara")
chk(_bp and _bp.get("default_model") not in (None, "", "auto/bynara"),
    "مدل پیش‌فرض bynara مدل واقعی فعال است (نه auto/bynara)",
    str(_bp.get("default_model")))
chk(_bp and "laguna-s-2.1" in (_bp.get("models") or []),
    "فهرست پشتیبان bynara شامل مدل رایگان فعال است")

# ═════════════════════════════════════════════════════════════════
print()
print("═" * 64)
print("۱۲) لایهٔ بازیابی خودکار از مدل مرده (عمومی برای هر سرویس)")
print("═" * 64)

# ── تشخیص «مدل مرده» از متن پاسخ — نه از نام مدل ──
chk(_bs._is_dead_model_response(404, "The model `X` does not exist or you do not have access to it"),
    "404 همراه واژهٔ model → مدل مرده")
chk(not _bs._is_dead_model_response(404, "Endpoint not found"),
    "404 بدون model → خطای مسیر، نه مدل (بازیابی نکند)")
chk(_bs._is_dead_model_response(403, "Your plan does not include the requested model."),
    "403 پلن → مدل مرده")
chk(not _bs._is_dead_model_response(403, "unsupported_country_region"),
    "403 منطقه‌ای → مدل نیست")
chk(not _bs._is_dead_model_response(402, "Insufficient credits"),
    "402 اعتبار → مدل نیست")

# ── ai_forward_request: مدل مرده → سوییچ خودکار به زنده ──
_calls = []
def _fake_req(url, headers, payload=None, method='POST',
              use_socks=None, timeout=None):
    _calls.append((method, url, (payload or {}).get("model")))
    if method == "GET" and url.endswith("/models"):
        _mlist = '{"data": [{"id": "alive-free", "input_idr_per_1k": 0, "output_idr_per_1k": 0},'
        _mlist += '{"id": "paid-one", "input_idr_per_1k": 1, "output_idr_per_1k": 2}]}'
        return {"status": 200, "data": _mlist}
    if (payload or {}).get("model") == "dead-model":
        return {"status": 404,
                "data": '{"error":{"message":"The model `dead-model` does not exist"}}'}
    return {"status": 200, "data": '{"choices":[{"message":{"content":"ok"}}]}'}

_orig_req = _bs.proxy.forward_ai_request
_orig_gs2, _orig_ss2 = _bs.get_settings, _bs.save_settings
_saved_sw = {}
_bs.proxy.forward_ai_request = _fake_req
_bs.get_settings = lambda: {"use_socks": False, "api_provider": "custom",
                            "base_url": "https://x.example/v1",
                            "free_probes": {}, "model": "dead-model"}
_bs.save_settings = lambda d: _saved_sw.update(d)
try:
    _r = _bs.ai_forward_request(
        "https://x.example/v1/chat/completions", {},
        {"model": "dead-model", "messages": []})
    chk(_r.get("status") == 200
        and _r.get("switched_model", {}).get("to") == "alive-free",
        "درخواست با مدل مرده → سوییچ خودکار به مدل رایگانِ زنده و موفق",
        repr(_r.get("switched_model")))
    chk(_saved_sw.get("model") == "alive-free",
        "مدل جدید در تنظیمات ذخیره می‌شود", repr(_saved_sw.get("model")))
    # کاندید پولی نباید انتخاب شود
    chk(all(m != "paid-one" for _, _, m in _calls if m),
        "کاندید پولی انتخاب نمی‌شود — فقط رایگانِ قیمت‌صفر",
        str(set(m for _, _, m in _calls if m)))
finally:
    _bs.proxy.forward_ai_request = _orig_req
    _bs.get_settings, _bs.save_settings = _orig_gs2, _orig_ss2

# ── ai_forward_stream: خطای مدل مرده قبل از اولین داده ──
def _fake_stream_dead(url, headers, payload, use_socks=None):
    if (payload or {}).get("model") == "dead-model":
        yield {"type": "http_error", "status": 404,
               "body": '{"error":{"message":"The model `dead-model` does not exist"}}'}
        return
    yield {"type": "data", "data": '{"choices":[{"delta":{"content":"سلام"}}]}'}
    yield {"type": "done"}

_orig_stream3 = _bs.proxy.forward_ai_stream
_bs.proxy.forward_ai_stream = _fake_stream_dead
# فهرست مدل‌ها هم باید شبیه‌سازی بماند (کاندیدهای جایگزین از آن می‌آیند)
_bs.proxy.forward_ai_request = _fake_req
_saved_sw2 = {}
_bs.get_settings = lambda: {"use_socks": False, "api_provider": "custom",
                            "base_url": "https://x.example/v1",
                            "free_probes": {}, "model": "dead-model"}
_bs.save_settings = lambda d: _saved_sw2.update(d)
try:
    _evs = list(_bs.ai_forward_stream(
        "https://x.example/v1/chat/completions", {},
        {"model": "dead-model", "messages": []}))
    _types = [e.get("type") for e in _evs]
    chk("note" in _types and "data" in _types and "done" in _types,
        "استریم با مدل مرده → note (خبر سوییچ) + داده + done با مدل زنده",
        repr(_types))
    chk(any(e.get("type") == "note" and "dead-model" in e.get("text", "")
            and "alive-free" in e.get("text", "") for e in _evs),
        "متن note نام مدل مرده و زنده را می‌گوید",
        str([e.get("text") for e in _evs if e.get("type") == "note"]))
    chk(_saved_sw2.get("model") == "alive-free",
        "سوییچ استریمی هم در تنظیمات ذخیره می‌شود",
        repr(_saved_sw2.get("model")))
finally:
    _bs.proxy.forward_ai_stream = _orig_stream3
    _bs.proxy.forward_ai_request = _orig_req
    _bs.get_settings, _bs.save_settings = _orig_gs2, _orig_ss2

# ── هدایت رویداد note از هندلرهای استریم به UI ──
_src_bs = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "backend_server.py"), encoding="utf-8").read()
chk(_src_bs.count('if t == "note":') >= 2,
    "هر دو هندلر استریم رویداد note را به UI می‌فرستند",
    f"count={_src_bs.count(chr(39) + 'note' + chr(39))}")
chk("model_switched" in _src_bs and "switched_info" in _src_bs,
    "fetch_models مهاجرت پیشگیرانه و گزارش model_switched دارد")
chk("ai_forward_request" in _src_bs and "def ai_forward_stream" in _src_bs,
    "لایهٔ ai_forward_request/ai_forward_stream تعریف شده")
_html12 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "pc_toolbox_app.html"), encoding="utf-8").read()
chk("d.model_switched" in _html12,
    "UI مدل مهاجرت‌شده را در کادر مدل اعمال می‌کند")

# ═════════════════════════════════════════════════════════════════
print()
print("═" * 64)
print("۱۳) Google Gemini — مدل‌های زنده، فیلتر باغ‌مدل‌ها، بلاک منطقه‌ای")
print("═" * 64)

# ── پیش‌فرض gemini باید مدل زندهٔ تست‌شده باشد ──
_gmp = _prov.get_provider("gemini")
chk(_gmp and _gmp.get("default_model") == "gemini-flash-latest",
    "مدل پیش‌فرض gemini = gemini-flash-latest (alias همیشه‌به‌روز)",
    str(_gmp and _gmp.get("default_model")))
chk(_gmp and "gemini-2.0-flash" not in (_gmp.get("models") or []),
    "مدل‌های مردهٔ gemini-2.0/1.5 از فهرست پیش‌فرض حذف شده‌اند")
chk("gemini-2.0-flash" in _prov.DEPRECATED_MODELS
    and "gemini-2.5-flash" in _prov.DEPRECATED_MODELS,
    "gemini های بازنشسته (1.5/2.0/2.5) در فهرست مهاجرت‌اند")

# ── حذف پیشوند models/ + فیلتر مدل‌های غیرچت گوگل ──
_google_zoo = [
    {"id": "models/gemini-flash-latest"},                     # چت — باید بماند
    {"id": "models/gemini-2.5-flash-image"},                  # تصویر
    {"id": "models/nano-banana-pro-preview"},                 # تصویر
    {"id": "models/veo-3.1-generate-preview"},                # ویدیو
    {"id": "models/gemini-3.8-live"},                         # زنده
    {"id": "models/gemini-3.8-flash-tts"},                    # گفتار
    {"id": "models/gemini-2.5-computer-use-preview-10-2025"}, # عامل
    {"id": "models/antigravity-preview-latest"},              # عامل
    {"id": "models/deep-research-max-preview-04-2026"},       # عامل
    {"id": "models/gemini-embedding-001"},                    # بردار
]
_genr, _gskp = _mi.enrich_models(_google_zoo, "gemini")
_ids = {m["id"] for m in _genr}
chk(_ids == {"gemini-flash-latest"},
    "از باغ‌مدل‌های گوگل فقط مدل چت می‌ماند (تصویر/ویدیو/زنده/عامل حذف)",
    str(_ids))
chk(all(not i.startswith("models/") for i in _ids),
    "پیشوند models/ از شناسه‌ها حذف می‌شود")

# ── طبقه‌بندی رایگان: کلید AI Studio پلن رایگان دارد ──
_gfree, _gwhy = _mi.is_free_model("gemini-flash-latest", "gemini", None)
chk(_gfree is True and "پلن رایگان" in _gwhy,
    "مدل‌های Gemini با کلید AI Studio → 🆓 پلن رایگان با سقف نرخ", _gwhy)

# ── بلاک منطقه‌ای گوگل → پیام راهنمای پروکسی ──
_geo = _mi.friendly_api_error(
    '{"error":{"message":"User location is not supported for the API use."}}',
    "gemini-flash-latest")
chk("منطقه" in _geo["title"] and "پروکسی" in _geo["hint"],
    "پیام «User location is not supported» → راهنمای پروکسی",
    _geo["title"] + " | " + _geo["hint"][:60])

# ── 404 «no longer available to new users» گوگل → مدل مرده ──
chk(_bs._is_dead_model_response(
        404, "This model models/gemini-2.5-flash is no longer available "
             "to new users. Please update your code to use gemini-3.8-flash"),
    "404 بازنشستگی گوگل → تشخیص مدل مرده و بازیابی خودکار")

# ═════════════════════════════════════════════════════════════════
print()
print("═" * 64)
print("۱۴) اتصال و پروکسی — رجیستری، تونل‌های VPN (Psiphon و...)، UI")
print("═" * 64)

# ── پارسر ProxyServer رجیستری ──
_pp = _proxy._parse_proxy_server
_r1 = _pp("127.0.0.1:8080")
chk(_r1 == {"http": "http://127.0.0.1:8080", "https": "http://127.0.0.1:8080"},
    "فرمت تک‌مقداری host:port درست پارس می‌شود", repr(_r1))
_r2 = _pp("http=127.0.0.1:8080;https=127.0.0.1:8081;socks=127.0.0.1:1080")
chk(_r2.get("https") == "http://127.0.0.1:8081"
    and "socks" not in str(_r2).lower().split("http=")[0]
    and _r2.get("http") == "http://127.0.0.1:8080",
    "فرمت per-protocol: https→http اولویت دارند، socks فقط به‌عنوان آخرین راه",
    repr(_r2))
_r3 = _pp("socks=127.0.0.1:1080")
chk(_r3 == {"http": "socks5h://127.0.0.1:1080", "https": "socks5h://127.0.0.1:1080"},
    "وقتی فقط socks= ثبت شده، همان با طرح socks5h استفاده می‌شود", repr(_r3))
chk(_pp("") is None and _pp("   ") is None, "مقدار خالی → None")
_r4 = _pp("http=127.0.0.1:9000")
chk(_r4.get("https") == "http://127.0.0.1:9000",
    "فقط http= ثبت شده → https هم از همان عبور می‌کند", repr(_r4))

# ── تشخیص نوع تونل از نام آداپتور ──
_tk = _proxy._tun_kind
chk(_tk("Psiphon3") == "Psiphon", "آداپتور Psiphon شناسایی می‌شود")
chk(_tk("VeePN Tunnel") == "VeePN", "آداپتور VeePN شناسایی می‌شود")
chk(_tk("WireGuard Tunnel") == "WireGuard/Wintun", "آداپتور WireGuard شناسایی می‌شود")
chk(_tk("TAP-Windows Adapter V9") == "OpenVPN/TAP", "آداپتور TAP/OpenVPN شناسایی می‌شود")
chk(_tk("VPN Connection 2") == "VPN سیستمی", "آداپتور VPN خود ویندوز شناسایی می‌شود")
chk(_tk("Ethernet") is None and _tk("Wi-Fi 2") is None,
    "آداپتورهای عادی به‌اشتباه تونل شمرده نمی‌شوند")

# ── system_proxy_info: کلیدهای جدید + سازگاری قدیمی ──
_orig_gsp = _proxy.get_system_proxy
_orig_dtv = _proxy._detect_tun_vpns
_proxy.get_system_proxy = lambda force=False: None
_proxy._detect_tun_vpns = lambda: {
    "detected": True,
    "adapters": [{"name": "Psiphon3", "kind": "Psiphon"}],
    "kinds": ["Psiphon"]}
try:
    _spi = _proxy.system_proxy_info()
    chk(_spi.get("found") is False and _spi.get("tun_kinds") == ["Psiphon"],
        "system_proxy_info تونل‌ها را گزارش می‌کند (بدون پروکسی رجیستری)",
        repr(_spi.get("tun_kinds")))
    chk(isinstance(_spi.get("tun_vpns"), list)
        and _spi["tun_vpns"][0]["kind"] == "Psiphon",
        "جزئیات آداپتور تونل در tun_vpns هست")
    chk("veepn" in _spi, "کلید سازگار veepn حفظ شده است")
finally:
    _proxy.get_system_proxy = _orig_gsp
    _proxy._detect_tun_vpns = _orig_dtv

# ── سیم‌کشی UI ──
_html14 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "pc_toolbox_app.html"), encoding="utf-8").read()
chk("window.__lastTunKinds" in _html14 and "tun_vpns" in _html14,
    "UI تونل‌های شناسایی‌شده را می‌خواند و برای تست اتصال نگه می‌دارد")
chk("تونل VPN فعال است" in _html14,
    "پیام سبزِ «تونل فعال — تنظیمی لازم نیست» در UI هست")
chk("Psiphon حالت VPN" in _html14 and "System Proxy" in _html14,
    "راهنمای UI دو حالت Psiphon را جدا توضیح می‌دهد")
chk("VPN را یک‌بار قطع و دوباره وصل" in _html14,
    "راهنمای عیب‌یابی وقتی تونل هست ولی تست شکست می‌خورد")

# ═════════════════════════════════════════════════════════════════
print()
print("═" * 64)
print("۱۶) تشخیص Hotspot Shield و VPN تنظیمات ویندوز")
print("═" * 64)

# ── الگوی Hotspot Shield ──
chk(_proxy._tun_kind("Hotspot Shield VPN") == "Hotspot Shield",
    "آداپتور Hotspot Shield شناسایی می‌شود")
chk(_proxy._tun_kind("AnchorFree Hss Adapter") == "Hotspot Shield",
    "آداپتور قدیمی AnchorFree/Hss هم شناسایی می‌شود")

# ── آداپتورهای VPN خود ویندوز ──
chk(_proxy._tun_kind("WAN Miniport (IKEv2)") == "VPN ویندوز",
    "آداپتور WAN Miniport (IKEv2) → VPN ویندوز")
chk(_proxy._tun_kind("WAN Miniport (L2TP)") == "VPN ویندوز",
    "آداپتور WAN Miniport (L2TP) → VPN ویندوز")

# ── پارسر rasdial ──
_rd = _proxy._parse_rasdial
chk(_rd("Connected to Work VPN\r\nCommand completed successfully.\r\n") == ["Work VPN"],
    "rasdial: یک VPN وصل‌شده درست پارس می‌شود")
chk(_rd("No connections") == [] and _rd("") == [],
    "rasdial: حالت بدون اتصال → خالی")
chk(_rd("Connected to A\r\nConnected to B\r\nCommand completed successfully.")
    == ["A", "B"],
    "rasdial: چند اتصال همزمان")

# ── پارسر Get-VpnConnection ──
_vj = _proxy._parse_vpn_json
chk(_vj('[{"Name":"آفیس","ConnectionStatus":"Disconnected"},'
        '{"Name":"Home","ConnectionStatus":"Connected"}]')
    == [{"name": "آفیس", "status": "Disconnected"},
        {"name": "Home", "status": "Connected"}],
    "Get-VpnConnection: فهرست پیکربندی‌شده‌ها با وضعیت")
chk(_vj('{"Name":"تنها","ConnectionStatus":"Disconnected"}')
    == [{"name": "تنها", "status": "Disconnected"}],
    "Get-VpnConnection: شیء تکی هم پارس می‌شود")
chk(_vj("not json") == [], "Get-VpnConnection: خروجی نامعتبر → خالی")

# ── ادغام: VPN وصل‌شدهٔ ویندوز در تونل‌های گزارش‌شده ──
_orig_gs16 = _proxy.get_system_proxy
_orig_dt16 = _proxy._detect_tun_vpns
_orig_wv16 = _proxy._detect_windows_vpn
_proxy.get_system_proxy = lambda force=False: None
_proxy._detect_tun_vpns = lambda: {"detected": False, "adapters": [], "kinds": []}
_proxy._detect_windows_vpn = lambda: {
    "connected": ["VPN شرکت"],
    "configured": [{"name": "VPN شرکت", "status": "Connected"}]}
try:
    _spi16 = _proxy.system_proxy_info()
    chk("VPN ویندوز" in _spi16.get("tun_kinds", []),
        "VPN وصل‌شدهٔ تنظیمات ویندوز در تونل‌های فعال گزارش می‌شود",
        repr(_spi16.get("tun_kinds")))
    chk(any(a["kind"] == "VPN ویندوز" and a["name"] == "VPN شرکت"
            for a in _spi16.get("tun_vpns", [])),
        "نام اتصال ویندوز در جزئیات تونل هست")
    chk(_spi16.get("windows_vpn", {}).get("configured") is not None,
        "فهرست کامل VPNهای پیکربندی‌شده در windows_vpn هست")
finally:
    _proxy.get_system_proxy = _orig_gs16
    _proxy._detect_tun_vpns = _orig_dt16
    _proxy._detect_windows_vpn = _orig_wv16

# ── سیم‌کشی UI ──
_html16 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "pc_toolbox_app.html"), encoding="utf-8").read()
chk("Hotspot Shield" in _html16,
    "راهنمای UI حالت Hotspot Shield را پوشش می‌دهد")
chk("VPN ویندوز پیکربندی شده ولی وصل نیست" in _html16,
    "پیام «VPN ویندوز قطع» در UI هست")
chk("d.windows_vpn" in _html16,
    "UI وضعیت VPNهای ویندوز را می‌خواند")

# ═════════════════════════════════════════════════════════════════
print()
print("═" * 64)
print("۱۷) باگ‌های کشف‌شده از تست ۱۲ مدل اعلامی Bynara")
print("═" * 64)

# ── 400 «model is not available» هم مدل مرده است ──
chk(_bs._is_dead_model_response(
        400, '{"error":{"message":"The requested model is not available."}}'),
    "400 «requested model is not available» → مدل مرده (فیلوور می‌گیرد)")
chk(not _bs._is_dead_model_response(
        400, "The model rejected this request. It may not support the input "
             "you sent (e.g. images on a text-only model) or a parameter is invalid."),
    "400 «model rejected this request» → مرگ مدل نیست (خطای گذرا/ورودی)")

# ── پیام روشن برای مدل ناموجود ──
_v404b, _r404b = _mi.classify_probe_status(
    404, '{"error":{"message":"The model `x` does not exist"}}')
chk(_v404b is False and "وجود ندارد" in _r404b,
    "کاوش 404 → «روی سرویس وجود ندارد (حذف/بازنشسته)»", _r404b)
_v400b, _r400b = _mi.classify_probe_status(
    400, '{"error":{"message":"The requested model is not available."}}')
chk(_v400b is False and "وجود ندارد" in _r400b,
    "کاوش 400 not-available → همان پیام روشن", _r400b)
_v400r, _ = _mi.classify_probe_status(
    400, '{"error":{"message":"The model rejected this request"}}')
chk(_v400r is None, "کاوش 400 rejected → نامشخص (قطعی‌سازی نمی‌کند)")

# ── بودجهٔ کاوش ۱۶ توکنی ──
_src17 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "backend_server.py"), encoding="utf-8").read()
chk('"max_tokens": 16, "stream": False' in _src17,
    "کاوش با ۱۶ توکن انجام می‌شود (۱ توکن برای reasoning کم است)")

# ── فیلوور کامل روی مرگِ 400 ──
def _fake400(url, headers, payload=None, method='POST',
             use_socks=None, timeout=None):
    if method == "GET" and url.endswith("/models"):
        return {"status": 200, "data": '{"data": [{"id": "free-alt"}]}'} \
            .__class__("status", 200) if False else {
            "status": 200,
            "data": '{"data": [{"id": "free-alt", "input_idr_per_1k": 0,'
                    ' "output_idr_per_1k": 0}]}'}
    if (payload or {}).get("model") == "gone-model":
        return {"status": 400,
                "data": '{"error":{"message":"The requested model is not available."}}'}
    return {"status": 200, "data": '{"choices":[{"message":{"content":"ok"}}]}'}

_orig_req17 = _bs.proxy.forward_ai_request
_orig_gs17, _orig_ss17 = _bs.get_settings, _bs.save_settings
_sw17 = {}
_bs.proxy.forward_ai_request = _fake400
_bs.get_settings = lambda: {"use_socks": False, "api_provider": "bynara",
                            "free_probes": {}, "model": "gone-model"}
_bs.save_settings = lambda d: _sw17.update(d)
try:
    _r17 = _bs.ai_forward_request(
        "https://router.bynara.id/v1/chat/completions", {},
        {"model": "gone-model", "messages": []})
    # اولویت کاندیدها: پیش‌فرضِ provider (laguna) قبل از فهرست زنده
    # (free-alt) — هر دو اینجا زنده‌اند؛ مهم این است که به مدلِ مرده
    # برنگشته و ذخیره شده باشد.
    _to17 = _r17.get("switched_model", {}).get("to")
    chk(_r17.get("status") == 200 and _to17 in ("laguna-s-2.1", "free-alt"),
        "مرگِ 400 → فیلوور خودکار به مدل زنده (پیش‌فرض provider اولویت دارد)",
        repr(_r17.get("switched_model")))
    chk(_sw17.get("model") == _to17,
        "همان مدل جایگزین در تنظیمات ذخیره شد",
        f"saved={_sw17.get('model')} switched={_to17}")
finally:
    _bs.proxy.forward_ai_request = _orig_req17
    _bs.get_settings, _bs.save_settings = _orig_gs17, _orig_ss17

# ── نشان ❔ برای مدل فهرست‌نشده ──
_html17 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "pc_toolbox_app.html"), encoding="utf-8").read()
chk("m.unknown" in _html17 and "unknown: true" in _html17,
    "مدل ذخیره‌شدهٔ فهرست‌نشده با پرچم unknown علامت می‌خورد")
chk("❔ در فهرست سرویس نیست" in _html17,
    "راهنمای نشان‌ها ❔ را توضیح می‌دهد")

# ═════════════════════════════════════════════════════════════════
print()
print("═" * 64)
print("۱۵) تشخیص خودکار سرویس از آدرس + بازنشستگی + 429 اعتباری")
print("═" * 64)

# ── detect_provider_by_url: میزبان حقیقت است ──
_dp = _prov.detect_provider_by_url
chk(_dp("https://api.openai.com/v1") == "openai",
    "api.openai.com → openai")
chk(_dp("https://api.openai.com/v1/chat/completions") == "openai",
    "مسیر کامل هم همان سرویس را می‌دهد")
chk(_dp("https://api.groq.com/openai/v1") == "groq", "api.groq.com → groq")
chk(_dp("https://router.bynara.id/v1") == "bynara", "router.bynara.id → bynara")
chk(_dp("https://generativelanguage.googleapis.com/v1beta/openai") == "gemini",
    "generativelanguage.googleapis.com → gemini")
chk(_dp("https://openrouter.ai/api/v1") == "openrouter",
    "openrouter.ai → openrouter")
chk(_dp("http://127.0.0.1:11434/v1") is None and _dp("") is None,
    "میزبان ناشناخته/محلی → None (سرویس دستی باقی می‌ماند)")

# ── مشکل اصلی: فهرست OpenAI با provider اشتباه → همه 🆓 غلط ──
_openai_items = [{"id": "gpt-5-nano"}, {"id": "gpt-4o-mini"},
                 {"id": "gpt-dying", "shutdown_date": "2026-04-01"}]
_enr_ok, _skp_ok = _mi.enrich_models(_openai_items, "openai")
chk(sum(1 for m in _enr_ok if m["free"]) == 0,
    "با provider=openai هیچ مدل 🆓 نیست (OpenAI مدل رایگان ندارد)")
chk(any(s["id"] == "gpt-dying" and "بازنشسته" in s["kind"] for s in _skp_ok),
    "مدل دارای shutdown_date به‌عنوان بازنشسته کنار گذاشته می‌شود",
    str(_skp_ok))
_enr_wrong, _ = _mi.enrich_models([{"id": "gpt-5-nano"}], "gemini")
chk(_enr_wrong[0]["free"] is True,
    "provider اشتباه (gemini) مدل OpenAI را 🆓 می‌کند — علت باگ گزارشی")
chk(_dp("https://api.openai.com/v1") == "openai",
    "تشخیص خودکار از آدرس همین را ریشه‌ای رفع می‌کند")

# ── 429 دوچهره: اعتبار تمام‌شده در برابر سقف نرخ ──
_v41, _r41 = _mi.classify_probe_status(
    429, '{"error":{"message":"You have no credits remaining. Add credits '
         'to continue using the API.","code":"credit_balance_exhausted"}}')
chk(_v41 is False and "اعتبار" in _r41,
    "429 «no credits remaining» → پولی/اعتبار تمام‌شده", _r41)
_v42, _r42 = _mi.classify_probe_status(
    429, '{"error":{"message":"Rate limit reached. Please try again later."}}')
chk(_v42 is True, "429 عادی rate-limit → رایگان با سقف نرخ", _r42)
_v43, _ = _mi.classify_probe_status(
    429, '{"error":{"message":"Insufficient credits. Please top up your balance."}}')
chk(_v43 is False, "429 «top up your balance» → اعتبار تمام‌شده")

# ── سیم‌کشی: fetch_models و failover از تشخیص خودکار استفاده می‌کنند ──
_src15 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "backend_server.py"), encoding="utf-8").read()
chk("detected_provider = providers.detect_provider_by_url(base_url)" in _src15,
    "fetch_models سرویس را از روی آدرس تشخیص می‌دهد")
chk('"detected_provider": detected_provider' in _src15,
    "پاسخ fetch_models سرویسِ تشخیص‌داده‌شده را برمی‌گرداند")
chk("providers.detect_provider_by_url(models_url)" in _src15,
    "لایهٔ بازیابی هم از روی میزبان غنی‌سازی می‌کند (نه تنظیمات کهنه)")
chk("max_completion_tokens" in _src15,
    "کاوش برای مدل‌های جدید OpenAI با max_completion_tokens دوباره امتحان می‌کند")
_html15 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "pc_toolbox_app.html"), encoding="utf-8").read()
chk("d.detected_provider" in _html15,
    "UI سرویس تشخیص‌داده‌شده را روی dropdown اعمال می‌کند")

# ── Groq: مدل‌های llama بازنشسته شده‌اند؛ پیش‌فرض باید زنده باشد ──
_gp = _prov.get_provider("groq")
chk(_gp and _gp.get("default_model") == "openai/gpt-oss-120b",
    "مدل پیش‌فرض groq مدل زندهٔ فعلی است (gpt-oss-120b)",
    str(_gp and _gp.get("default_model")))
chk("llama-3.3-70b-versatile" in _prov.DEPRECATED_MODELS
    and "auto/bynara" in _prov.DEPRECATED_MODELS,
    "مدل‌های بازنشسته (llama قدیمی و auto/bynara) در فهرست مهاجرت‌اند")
chk(_bs.DEFAULT_AI_MODEL == _gp.get("default_model"),
    "DEFAULT_AI_MODEL سرور با پیش‌فرض providers یکی است",
    _bs.DEFAULT_AI_MODEL)
chk(_bs._default_settings().get("model") == _bs.DEFAULT_AI_MODEL,
    "default_settings از DEFAULT_AI_MODEL استفاده می‌کند")

# ── مهاجرت خودکار تنظیمات ذخیره‌شدهٔ قدیمی ──
import json as _json5
import tempfile as _tf
_orig_sf = _bs.SETTINGS_FILE
try:
    _tmpd = _tf.mkdtemp()
    _bs.SETTINGS_FILE = os.path.join(_tmpd, "s.json")
    with open(_bs.SETTINGS_FILE, "w", encoding="utf-8") as f:
        _json5.dump({"api_provider": "groq",
                     "model": "llama-3.3-70b-versatile"}, f)
    _mig = _bs.get_settings()
    chk(_mig.get("model") == _gp.get("default_model"),
        "تنظیمات ذخیره‌شده با مدل مرده → خودکار به مدل زنده مهاجرت می‌کند",
        repr(_mig.get("model")))
finally:
    _bs.SETTINGS_FILE = _orig_sf

# پیش‌فرض HTML هم باید زنده باشد
chk('value="openai/gpt-oss-120b"' in _html,
    "مقدار پیش‌فرض کادر مدل در UI زنده است")
chk('value="llama-3.3-70b-versatile"' not in _html,
    "مدل مرده دیگر پیش‌فرض UI نیست")

print()
print("─" * 64)
print(f"نتیجه: {P} موفق، {F} ناموفق")
if F:
    print("\n⚠️ پیش از ساخت exe این موارد را رفع کنید.")
sys.exit(1 if F else 0)
