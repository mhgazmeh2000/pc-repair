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

print()
print("─" * 64)
print(f"نتیجه: {P} موفق، {F} ناموفق")
if F:
    print("\n⚠️ پیش از ساخت exe این موارد را رفع کنید.")
sys.exit(1 if F else 0)
