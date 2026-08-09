# -*- coding: utf-8 -*-
"""
model_info.py — تشخیص مدل‌های رایگان و اعتبارسنجی صادقانه کلید API
====================================================================
دو مسئله‌ای که حل می‌کند:

۱. تشخیص مدل رایگان
   روش اول (دقیق):   قیمت واقعی که خود API برمی‌گرداند.
                     OpenRouter در پاسخ /models فیلد pricing دارد؛
                     اگر prompt و completion صفر باشند، مدل رایگان است.
   روش دوم (پشتیبان): فهرست سرویس‌هایی که کلاً رایگان‌اند + الگوی نام.

۲. اعتبارسنجی صادقانه
   کد وضعیت HTTP را به پیام دقیق فارسی ترجمه می‌کند تا کاربر بداند
   مشکل از کلید است، از دسترسی، یا از شبکه.
"""

import re

# سرویس‌هایی که همه یا بیشتر مدل‌هایشان رایگان است
FREE_PROVIDERS = {
    "groq":     "همه مدل‌های Groq رایگان‌اند (با محدودیت نرخ)",
    "ollama":   "اجرای محلی — کاملاً رایگان",
    "lmstudio": "اجرای محلی — کاملاً رایگان",
}

# الگوهای نام که نشان‌دهنده رایگان بودن‌اند
FREE_NAME_PATTERNS = [
    re.compile(r':free\b', re.I),          # OpenRouter:  model:free
    re.compile(r'\bfree\b', re.I),
    re.compile(r'-free$', re.I),
]

# مدل‌های رایگان شناخته‌شده (پشتیبان، وقتی API قیمت نمی‌دهد)
KNOWN_FREE = {
    "gemini": [
        "gemini-2.0-flash", "gemini-2.0-flash-lite",
        "gemini-1.5-flash", "gemini-1.5-flash-8b",
    ],
    "openrouter": [
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "deepseek/deepseek-r1:free",
        "qwen/qwen-2.5-72b-instruct:free",
        "mistralai/mistral-7b-instruct:free",
    ],
}


# ---------------------------------------------------------------------------
# مدل‌های غیرچتی
# ---------------------------------------------------------------------------
# endpoint /models همه مدل‌های سرویس را برمی‌گرداند — نه فقط مدل‌های چت.
# اگر کاربر مثلاً یک مدل TTS انتخاب کند، درخواست چت با خطای عجیب رد می‌شود:
#   "The model `canopylabs/orpheus-arabic-saudi` requires terms acceptance"
# پس این‌ها را از فهرست کنار می‌گذاریم.
NON_CHAT_PATTERNS = [
    # تبدیل متن به گفتار
    (re.compile(r'\btts\b|text-to-speech|orpheus|playai-tts|\bvoice\b', re.I),
     "تبدیل متن به گفتار"),
    # تشخیص گفتار
    (re.compile(r'whisper|\bstt\b|speech-to-text|transcribe', re.I),
     "تشخیص گفتار"),
    # فیلتر و ایمنی محتوا
    (re.compile(r'guard|moderation|safety|shield', re.I),
     "فیلتر محتوا"),
    # بردارسازی
    (re.compile(r'embed|embedding|\bbge-|\bgte-|rerank', re.I),
     "بردارسازی متن"),
    # تصویر و ویدیو
    (re.compile(r'dall-?e|stable-?diffusion|flux|midjourney|imagen|'
                r'\bsora\b|veo-|lyria|\btts-1\b', re.I),
     "تولید تصویر یا صدا"),
    # OCR و بینایی محض
    (re.compile(r'\bocr\b|paddle', re.I), "پردازش تصویر"),
]


def classify_model(model_id):
    """
    نوع مدل را تشخیص می‌دهد.

    خروجی: (is_chat, نوع)
    """
    mid = (model_id or "").strip()
    for pat, label in NON_CHAT_PATTERNS:
        if pat.search(mid):
            return False, label
    return True, "چت"


def is_free_model(model_id, provider=None, pricing=None):
    """
    آیا این مدل رایگان است؟

    خروجی: (bool, دلیل)
    """
    mid = (model_id or "").strip()
    prov = (provider or "").lower()

    # ── روش اول: قیمت واقعی از API ──
    if isinstance(pricing, dict):
        def num(v):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        p_in  = num(pricing.get("prompt"))
        p_out = num(pricing.get("completion"))
        if p_in is not None and p_out is not None:
            if p_in == 0 and p_out == 0:
                return True, "قیمت اعلامی سرویس: صفر"
            return False, f"هزینه دارد ({p_in}/{p_out} به ازای توکن)"

    # ── روش دوم: سرویس کلاً رایگان ──
    if prov in FREE_PROVIDERS:
        return True, FREE_PROVIDERS[prov]

    # ── روش سوم: الگوی نام ──
    for pat in FREE_NAME_PATTERNS:
        if pat.search(mid):
            return True, "نام مدل نشان‌دهنده نسخه رایگان است"

    # ── روش چهارم: فهرست شناخته‌شده ──
    for p, lst in KNOWN_FREE.items():
        if (not prov or prov == p) and mid in lst:
            return True, "در فهرست مدل‌های رایگان شناخته‌شده"

    return False, ""


def enrich_models(raw_items, provider=None, chat_only=True):
    """
    خروجی خام /models را به فهرست غنی‌شده تبدیل می‌کند.

    chat_only: مدل‌های غیرچتی (TTS، Whisper، embedding و...) حذف شوند.
               پیش‌فرض روشن است چون این برنامه فقط چت می‌کند.
    """
    out, skipped = [], []
    for item in (raw_items or []):
        if isinstance(item, str):
            mid, pricing, ctx, active = item, None, None, True
        elif isinstance(item, dict):
            mid = item.get("id") or item.get("name") or ""
            pricing = item.get("pricing")
            ctx = item.get("context_length") or item.get("context_window")
            # Groq فیلد active دارد؛ مدل غیرفعال کار نمی‌کند
            active = item.get("active", True)
        else:
            continue
        if not mid:
            continue

        is_chat, kind = classify_model(mid)
        if chat_only and not is_chat:
            skipped.append({"id": mid, "kind": kind})
            continue
        if active is False:
            skipped.append({"id": mid, "kind": "غیرفعال"})
            continue

        free, why = is_free_model(mid, provider, pricing)
        out.append({
            "id": mid,
            "free": free,
            "free_reason": why,
            "context": ctx,
            "kind": kind,
        })

    # رایگان‌ها اول
    out.sort(key=lambda m: (not m["free"], m["id"]))
    return out, skipped


# ---------------------------------------------------------------------------
# ترجمه صادقانه کد وضعیت
# ---------------------------------------------------------------------------
STATUS_MEANING = {
    200: ("ok",      "✅ کلید معتبر است و سرویس پاسخ داد"),
    401: ("bad_key", "❌ کلید API نامعتبر است یا منقضی شده"),
    403: ("no_access", "⛔ کلید معتبر است ولی دسترسی به این سرویس ندارید "
                       "(ممکن است به‌خاطر محدودیت منطقه‌ای باشد)"),
    404: ("bad_url", "❓ آدرس Base URL اشتباه است — این مسیر روی سرور وجود ندارد"),
    429: ("rate",    "⏳ تعداد درخواست‌ها بیش از حد مجاز — کمی صبر کنید"),
    500: ("server",  "🔧 خطای داخلی سرور سرویس‌دهنده"),
    502: ("server",  "🔧 سرور سرویس‌دهنده در دسترس نیست"),
    503: ("server",  "🔧 سرویس موقتاً از دسترس خارج است"),
}


def explain_status(code, has_key=True):
    """کد HTTP را به وضعیت و پیام فارسی تبدیل می‌کند."""
    if code in STATUS_MEANING:
        kind, msg = STATUS_MEANING[code]
        if code == 401 and not has_key:
            return "no_key", "🔑 کلید API وارد نشده است"
        return kind, msg
    if code == 0:
        return "network", "🌐 اتصال برقرار نشد — شبکه یا پروکسی را بررسی کنید"
    if 200 <= code < 300:
        return "ok", f"✅ سرویس پاسخ داد (کد {code})"
    return "error", f"⚠️ پاسخ غیرمنتظره از سرور (کد {code})"


# ---------------------------------------------------------------------------
# ترجمه خطای خام API به پیام خوانا
# ---------------------------------------------------------------------------
API_ERROR_HINTS = [
    (re.compile(r'requires terms acceptance|model_terms_required', re.I),
     "این مدل نیاز به پذیرش شرایط استفاده دارد",
     "معمولاً یعنی مدل برای چت ساخته نشده (مثلاً تبدیل متن به گفتار). "
     "مدل دیگری انتخاب کنید."),

    (re.compile(r'model_not_found|does not exist|unknown model|invalid model', re.I),
     "این مدل روی سرویس وجود ندارد",
     "نام مدل را بررسی کنید یا دکمه «دریافت فهرست واقعی مدل‌ها» را بزنید."),

    (re.compile(r'insufficient_quota|exceeded your current quota|billing', re.I),
     "اعتبار حساب شما تمام شده",
     "یا اعتبار شارژ کنید یا از سرویس رایگان مثل Groq استفاده کنید."),

    (re.compile(r'rate.?limit|too many requests|429', re.I),
     "تعداد درخواست‌ها بیش از حد مجاز",
     "چند دقیقه صبر کنید یا مدل سبک‌تری انتخاب کنید."),

    (re.compile(r'invalid.?api.?key|incorrect api key|authentication', re.I),
     "کلید API نامعتبر است",
     "کلید را در تنظیمات بررسی کنید."),

    (re.compile(r'context.?length|maximum context|too many tokens', re.I),
     "متن ارسالی بیش از ظرفیت مدل است",
     "گفتگوی جدید شروع کنید یا مدلی با ظرفیت بالاتر انتخاب کنید."),

    (re.compile(r'unsupported.?country|region|not available in your', re.I),
     "این سرویس در منطقه شما در دسترس نیست",
     "از پروکسی استفاده کنید یا سرویس داخلی انتخاب کنید."),

    (re.compile(r'decommissioned|deprecated|no longer supported', re.I),
     "این مدل بازنشسته شده",
     "فهرست مدل‌ها را به‌روز کنید و نسخه جدیدتر را انتخاب کنید."),
]


def friendly_api_error(raw, model=None):
    """
    بدنه خطای خام API را به پیام فارسی قابل فهم تبدیل می‌کند.

    خروجی: dict با title, hint, detail
    """
    text = raw if isinstance(raw, str) else str(raw or "")

    # پیام اصلی را از JSON بیرون بکش
    msg = text
    try:
        import json as _json
        d = _json.loads(text)
        if isinstance(d, dict):
            err = d.get("error", d)
            if isinstance(err, dict):
                msg = err.get("message") or err.get("code") or text
            elif isinstance(err, str):
                msg = err
    except Exception:
        pass

    for pat, title, hint in API_ERROR_HINTS:
        if pat.search(text):
            if model:
                title = f"{title} — «{model}»"
            return {"title": title, "hint": hint, "detail": msg[:300]}

    return {"title": "خطا در ارتباط با سرویس هوش مصنوعی",
            "hint": "جزئیات را ببینید یا مدل/سرویس دیگری امتحان کنید.",
            "detail": msg[:300]}


if __name__ == "__main__":
    print("── تشخیص نوع مدل ──\n")
    for m in ["llama-3.3-70b-versatile", "whisper-large-v3", "playai-tts",
              "canopylabs/orpheus-arabic-saudi", "meta-llama/llama-guard-4-12b",
              "text-embedding-3-small", "gpt-4o"]:
        chat, kind = classify_model(m)
        print(f"  {'✅' if chat else '🚫'} {m[:36]:38} {kind}")

    print("\n── ترجمه خطای API ──\n")
    sample = ('{"error":{"message":"The model `canopylabs/orpheus-arabic-saudi` '
              'requires terms acceptance. Please have the org admin accept the terms",'
              '"type":"invalid_request_error","code":"model_terms_required"}}')
    r = friendly_api_error(sample, "canopylabs/orpheus-arabic-saudi")
    print(f"  عنوان : {r['title']}")
    print(f"  راهنما: {r['hint']}")

    print("\n── تشخیص مدل رایگان ──\n")
    tests = [
        ("llama-3.3-70b-versatile", "groq", None),
        ("gpt-4o", "openai", None),
        ("google/gemini-2.0-flash-exp:free", "openrouter", None),
        ("anthropic/claude-3.5-sonnet", "openrouter",
         {"prompt": "0.000003", "completion": "0.000015"}),
        ("meta-llama/llama-3.3-70b:free", "openrouter",
         {"prompt": "0", "completion": "0"}),
        ("llama3.2", "ollama", None),
    ]
    for mid, prov, pr in tests:
        free, why = is_free_model(mid, prov, pr)
        print(f"  {'🆓' if free else '💰'} {mid[:42]:44} {why}")

    print("\n── ترجمه کد وضعیت ──\n")
    for c in (200, 401, 403, 404, 429, 0):
        k, m = explain_status(c)
        print(f"  {c:3} → {k:10} {m}")
