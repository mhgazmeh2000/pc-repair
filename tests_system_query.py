# -*- coding: utf-8 -*-
"""
تست حلقهٔ خودکار [NEED_INFO: ...] در چت استریمی و درستی پرس‌وجوهای سیستم.

مشکل گزارش‌شده: وقتی کاربر «اطلاعات رم من را بده» می‌پرسید، مدل نشانگر
[NEED_INFO: memory] می‌نوشت و در مسیر استریم همان نشانگرِ خام به کاربر
نمایش داده می‌شد (حلقهٔ جمع‌آوری فقط در مسیر غیر-استریم بود). این تست
مطمئن می‌شود:

  ۱. _split_stream_chunk نشانگر را از متن نمایشی جدا می‌کند (حتی وقتی
     نشانگر وسطِ یک قطعه شکسته شود).
  ۲. _stream_ai_chat دور دوم را با دادهٔ واقعی اجرا می‌کند و هیچ‌وقت
     متن خام [NEED_INFO ...] به فرانت نمی‌رود.
  ۳. _ps دیگر از -Command استفاده نمی‌کند (متن فارسی را cmd.exe خراب
     می‌کرد) بلکه با -EncodedCommand می‌فرستد.

اجرا:  python tests_system_query.py
"""

import io
import json
import os
import sys
import base64

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backend_server as bs
import proxy
import system_query

P = F = 0


def chk(cond, msg, extra=""):
    global P, F
    if cond:
        P += 1
        print(f"  ✅ {msg}")
    else:
        F += 1
        print(f"  ❌ {msg}" + (f"  → {extra}" if extra else ""))


def _make_handler(buf):
    h = bs.IntegratedRequestHandler.__new__(bs.IntegratedRequestHandler)
    h.wfile = buf
    h._set_cors = lambda: None
    h.send_response = lambda *a, **k: None
    h.end_headers = lambda: None
    h.send_header = lambda *a, **k: None
    return h


def main():
    # نسخهٔ اصلی forward_ai_stream — بخش‌های قبلی ممکن است آن را
    # monkeypatch کرده باشند؛ بخش retry به نسخهٔ واقعی نیاز دارد.
    _real_stream = proxy.forward_ai_stream
    print("تست حلقهٔ NEED_INFO در چت استریمی\n" + "─" * 64)

    # ── ۱) _split_stream_chunk ──
    S = bs.IntegratedRequestHandler._split_stream_chunk
    print("۱) جداسازی نشانگر از متن نمایشی")
    emit, pend, mk, after = S("سلام، این یک پاسخ عادی است")
    chk(emit == "سلام، این یک پاسخ عادی است" and mk is None and pend == "",
        "متن عادی بدون نشانگر کامل ارسال می‌شود", repr((emit, pend, mk)))
    emit, pend, mk, after = S("بررسی می‌کنم [NEED_INFO: memory]")
    chk(mk == "[NEED_INFO: memory]" and emit == "بررسی می‌کنم " and after == "",
        "نشانگر کامل از متن جدا می‌شود", repr((emit, mk, after)))
    emit, pend, mk, after = S("x [NEED_INFO: cpu] tail")
    chk(mk == "[NEED_INFO: cpu]" and after == " tail", "نشانگر وسط متن هم جدا می‌شود",
        repr((emit, mk, after)))
    emit, pend, mk, after = S("بررسی [NEED")
    chk(emit == "بررسی " and pend == "[NEED" and mk is None,
        "شروعِ ناقصِ نشانگر معلق می‌ماند", repr((emit, pend)))
    emit, pend, mk, after = S(pend + "_")
    chk(emit == "" and pend == "[NEED_" and mk is None,
        "ادامهٔ معلق هنوز نمایش داده نمی‌شود", repr((emit, pend)))
    emit, pend, mk, after = S(pend + "INFO: memory]")
    chk(mk == "[NEED_INFO: memory]" and emit == "",
        "تکمیل نشانگر در قطعهٔ بعدی تشخیص داده می‌شود", repr((emit, mk)))
    emit, pend, mk, after = S("متن [1] پایان")
    chk(emit == "متن [1] پایان" and pend == "" and mk is None,
        "کروشهٔ معمولی (غیر نشانگر) آزاد می‌شود", repr((emit, pend)))
    emit, pend, mk, after = S("متن [")
    chk(emit == "متن " and pend == "[" and mk is None,
        "کروشهٔ انتهای قطعه معلق می‌ماند تا مشخص شود", repr((emit, pend)))
    emit, pend, mk, after = S(pend + "1]")
    chk(emit == "[1]" and pend == "" and mk is None,
        "کروشهٔ غیر نشانگر پس از قطعهٔ بعد آزاد می‌شود", repr((emit, pend)))

    # ── ۲) دور کامل استریم: نشانگر → جمع‌آوری → پاسخ نهایی ──
    print("۲) دور کامل _stream_ai_chat (با mock سرویس)")
    responses = iter([
        [{"type": "data", "data": json.dumps(
            {"choices": [{"delta": {"content": "برای پاسخ، این را می‌خواهم ["}}]})},
         {"type": "data", "data": json.dumps(
            {"choices": [{"delta": {"content": "NEED_INFO: memory]"}}]})}],
        [{"type": "data", "data": json.dumps(
            {"choices": [{"delta": {"content": "رم: 16GB — "}}]})},
         {"type": "data", "data": json.dumps(
            {"choices": [{"delta": {"content": "طبق دادهٔ واقعی سیستم."}}]})}],
    ])

    def fake_stream(url, headers, payload, use_socks=True):
        return iter(next(responses))

    orig_qr = system_query.run_queries
    system_query.run_queries = lambda keys: {
        "requested": list(keys),
        "text": "### وضعیت حافظه RAM و ماژول‌ها  (memory)\n```\nکل: 16 GB | آزاد: 8 GB\n```"}
    orig_fwd = proxy.forward_ai_stream
    proxy.forward_ai_stream = fake_stream
    orig_settings = bs.get_settings
    bs.get_settings = lambda: {"use_socks": True}
    buf = io.BytesIO()
    try:
        h = _make_handler(buf)
        h._stream_ai_chat(
            {"model": "m", "messages": []}, {}, "http://x",
            [{"role": "user", "content": "اطلاعات رم من را بده"}],
            {"sent": 1, "total": 2, "tokens": 10, "context": 8000})
    finally:
        system_query.run_queries = orig_qr
        proxy.forward_ai_stream = orig_fwd
        bs.get_settings = orig_settings

    out = buf.getvalue().decode("utf-8")
    chk("NEED_INFO" not in out, "نشانگر خام هرگز به فرانت نمی‌رود")
    chk("برای پاسخ، این را می‌خواهم " in out, "متن قبل از نشانگر نمایش داده می‌شود")
    chk("event: note" in out and "در حال تحلیل" in out,
        "رویداد note (وضعیت میانی) فرستاده می‌شود")
    chk("رم: 16GB — طبق دادهٔ واقعی سیستم." in out,
        "پاسخ دور دوم (با دادهٔ جمع‌آوری‌شده) استریم می‌شود")
    chk("event: done" in out and '"info_collected": ["memory"]' in out,
        "done با info_collected فرستاده می‌شود")
    chk('"memory"' in out, "memory badge در done موجود است")

    # ── ۳) پاسخ عادی بدون نشانگر ──
    print("۳) پاسخ عادی بدون نشانگر")
    responses2 = iter([
        [{"type": "data", "data": json.dumps(
            {"choices": [{"delta": {"content": "سلام! چطور می‌توانم کمک کنم؟"}}]})}],
    ])
    proxy.forward_ai_stream = lambda *a, **k: iter(next(responses2))
    buf2 = io.BytesIO()
    bs.get_settings = lambda: {"use_socks": True}
    h2 = _make_handler(buf2)
    h2._stream_ai_chat({"model": "m", "messages": []}, {}, "http://x",
                       [{"role": "user", "content": "سلام"}], None)
    out2 = buf2.getvalue().decode("utf-8")
    chk("سلام! چطور می‌توانم کمک کنم؟" in out2,
        "پاسخ عادی مستقیم نمایش داده می‌شود")
    chk(out2.count("event: done") == 1, "فقط یک done فرستاده می‌شود")

    # ── ۴) _ps با -EncodedCommand ──
    print("۴) ارسال اسکریپت با -EncodedCommand (ایمن برای فارسی)")
    captured = {}

    def fake_run(cmd, timeout=20):
        captured["cmd"] = cmd
        return ""

    orig_run = system_query._run
    system_query._run = fake_run
    try:
        system_query._ps("$t=1; \"کل: $t GB\"")
    finally:
        system_query._run = orig_run
    cmd = captured.get("cmd", "")
    chk("-EncodedCommand" in cmd, "اسکریپت با -EncodedCommand ارسال می‌شود")
    chk("-Command" not in cmd, "دیگر از -Command استفاده نمی‌شود")
    m = __import__("re").search(r"-EncodedCommand (\S+)", cmd)
    chk(m is not None, "Base64 اسکریپت در دستور هست")
    if m:
        decoded = base64.b64decode(m.group(1)).decode("utf-16-le")
        chk("کل" in decoded and '"' in decoded
            and "OutputEncoding" in decoded,
            "متن فارسی، کوئوت‌ها و تنظیم UTF-8 در اسکریپت سالم‌اند",
            repr(decoded))

    # ── ۵) سقف ۲ دور — وقتی دور دوم هم نشانگر می‌خواهد ──
    print("۵) سقف ۲ دور — وقتی دور دوم هم نشانگر می‌خواهد")
    responses3 = iter([
        [{"type": "data", "data": json.dumps(
            {"choices": [{"delta": {"content": "[NEED_INFO: memory]"}}]})}],
        [{"type": "data", "data": json.dumps(
            {"choices": [{"delta": {"content": "خلاصه: [NEED_INFO: cpu]"}}]})}],
    ])
    proxy.forward_ai_stream = lambda *a, **k: iter(next(responses3))
    buf3 = io.BytesIO()
    bs.get_settings = lambda: {"use_socks": True}
    h3 = _make_handler(buf3)
    h3._stream_ai_chat({"model": "m", "messages": []}, {}, "http://x",
                       [{"role": "user", "content": "رم و سی‌پی‌یو؟"}], None)
    out3 = buf3.getvalue().decode("utf-8")
    done3 = [l for l in out3.split("\n") if l.startswith("data: {")][-1]
    import json as _json
    d3 = _json.loads(done3[6:])
    chk("NEED_INFO" not in out3, "هیچ نشانگری به فرانت نمی‌رود")
    chk(d3.get("reply") == "خلاصه:",
        "پاسخ نهایی متنِ دور دوم را نگه می‌دارد (خالی نمی‌شود)",
        repr(d3.get("reply")))

    # ── ۶) فهرست پرس‌وجوها ──
    print("۶) فهرست پرس‌وجوهای سیستم")
    qs = system_query.list_queries()
    chk(len(qs) >= 25, "حداقل ۲۵ پرس‌وجو تعریف شده", f"{len(qs)}")
    chk(any(q["key"] == "memory" for q in qs), "پرس‌وجوی memory موجود است")
    r = system_query.run_query("not_a_real_key")
    chk(not r.get("success"), "کلید نامعتبر خطای تمیز می‌دهد")

    # ── ۷) retry خطاهای گذرا در استریم (ReadTimeout و مانند آن) ──
    print("۷) retry خطاهای گذرای شبکه در استریم")
    import requests as _requests
    from types import SimpleNamespace as _NS

    class _RespOK:
        status_code = 200
        encoding = "utf-8"
        def __init__(self):
            self.text = ""
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def iter_lines(self, decode_unicode=True):
            yield 'data: {"choices":[{"delta":{"content":"پاسخ پس از retry"}}]}'
            yield "data: [DONE]"

    class _RespPartial:
        """یک تکه تحویل می‌دهد و بعد ReadTimeout می‌دهد."""
        status_code = 200
        encoding = "utf-8"
        def __init__(self):
            self.text = ""
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def iter_lines(self, decode_unicode=True):
            yield 'data: {"choices":[{"delta":{"content":"نیمه‌کاره"}}]}'
            raise _requests.exceptions.ReadTimeout("Read timed out.")

    proxy.forward_ai_stream = _real_stream   # بازگردانی نسخهٔ واقعی

    # ۷-الف) تلاش اول با خطای گذرا می‌میرد، retry موفق می‌شود
    class _SessRetry:
        posts = 0
        def __init__(self):
            self.headers = {}
            self.trust_env = False
        def post(self, url, json=None, proxies=None, timeout=None,
                 verify=None, stream=False):
            _SessRetry.posts += 1
            if _SessRetry.posts == 1:
                raise _requests.exceptions.ReadTimeout("Read timed out.")
            return _RespOK()

    orig_requests = proxy.requests
    orig_sysproxy = proxy.get_system_proxy
    proxy.get_system_proxy = lambda force=False: None
    proxy.requests = _NS(Session=_SessRetry, exceptions=_requests.exceptions)
    try:
        evs = list(proxy.forward_ai_stream("http://x", {}, {"messages": []}))
    finally:
        proxy.requests = orig_requests
        proxy.get_system_proxy = orig_sysproxy
    data_evs = [e for e in evs if e.get("type") == "data"]
    chk(_SessRetry.posts == 2, "خطای گذرا یک بار همان مسیر retry می‌شود",
        f"posts={_SessRetry.posts}")
    chk(any("پاسخ پس از retry" in e.get("data", "") for e in data_evs),
        "retry پاسخ کامل را تحویل می‌دهد")
    chk(any(e.get("type") == "done" for e in evs), "retry با done تمام می‌شود")

    # ۷-ب) تحویل ناقص → retry نمی‌شود (تا متن تکراری به کاربر نرسد)
    class _SessPartial:
        posts = 0
        def __init__(self):
            self.headers = {}
            self.trust_env = False
        def post(self, url, json=None, proxies=None, timeout=None,
                 verify=None, stream=False):
            _SessPartial.posts += 1
            return _RespPartial()

    proxy.get_system_proxy = lambda force=False: None
    proxy.requests = _NS(Session=_SessPartial, exceptions=_requests.exceptions)
    try:
        evs2 = list(proxy.forward_ai_stream("http://x", {}, {"messages": []}))
    finally:
        proxy.requests = orig_requests
        proxy.get_system_proxy = orig_sysproxy
    chk(_SessPartial.posts == 1,
        "بعد از تحویل ناقص، retry اجرا نمی‌شود", f"posts={_SessPartial.posts}")
    chk(any(e.get("type") == "data" for e in evs2)
        and any(e.get("type") == "error" for e in evs2),
        "پاسخ ناقص + خطا گزارش می‌شود")

    # ── ۷ج) run_queries: سقف کلیدها و پیام توصیفی خروجی خالی ──
    print("۷ج) run_queries — سقف و پیام «خروجی خالی»")
    _orig_q = dict(system_query.QUERIES)
    system_query.QUERIES["zz_empty_test"] = ("پرس‌وجوی خالی تست", lambda: "")
    try:
        keys = ["zz_empty_test", "cpu", "memory", "disks", "disk_health",
                "uptime", "top_cpu", "top_memory", "os_info",
                "network_config", "bsod_history", "startup_apps",
                "problem_drivers", "scheduled_tasks"]
        qr = system_query.run_queries(keys)
    finally:
        system_query.QUERIES = _orig_q
    chk(len(qr["requested"]) <= 12,
        "سقف پرس‌وجوهای یک‌جا ۱۲ تاست", f"len={len(qr['requested'])}")
    chk("zz_empty_test" in qr["requested"],
        "پرس‌وجوی خالی در متن می‌آید (نه حذف بی‌صدا)")
    chk("(خروجی خالی)" not in qr["text"],
        "متن خام «خروجی خالی» به AI نمی‌رود")
    chk("گزارش نشد" in qr["text"],
        "به‌جای آن توضیح فارسیِ دلیلِ نبودِ داده می‌رود")

    # ── ۸) fallback آفلاین وقتی استریم قبل از تحویل محتوا خطا بدهد ──
    print("۸) fallback به موتور آفلاین هنگام قطع اتصال")
    proxy.forward_ai_stream = lambda *a, **k: iter([
        {"type": "error", "error": "ReadTimeout: Read timed out."}])
    orig_diag = bs.system_inspector.get_system_diagnostics
    bs.system_inspector.get_system_diagnostics = lambda: {
        "disk_c": {"free_gb": 12, "percent_used": 40},
        "temp_files": {"size_mb": 200},
        "event_viewer_logs": []}
    buf4 = io.BytesIO()
    try:
        h4 = _make_handler(buf4)
        h4._stream_ai_chat({"model": "m", "messages": []}, {}, "http://x",
                           [{"role": "user", "content": "رم؟"}], None)
    finally:
        bs.system_inspector.get_system_diagnostics = orig_diag
    out4 = buf4.getvalue().decode("utf-8")
    chk("موتور آفلاین" in out4,
        "به‌جای خطای خشک، پاسخ موتور آفلاین فرستاده می‌شود")
    chk('"offline": true' in out4, "پرچم offline در done هست")
    chk("ReadTimeout" not in out4,
        "خطای خام به کاربر نمایش داده نمی‌شود")

    print()
    print("─" * 64)
    print(f"نتیجه: {P} موفق، {F} ناموفق")
    sys.exit(1 if F else 0)


if __name__ == "__main__":
    main()
