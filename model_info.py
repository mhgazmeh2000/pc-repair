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
    # کلید AI Studio گوگل پلن رایگانِ محدود به نرخ برای مدل‌های Gemini دارد
    "gemini":   "پلن رایگان با سقف نرخ (کلید Google AI Studio)",
}

# الگوهای نام که نشان‌دهنده رایگان بودن‌اند
FREE_NAME_PATTERNS = [
    re.compile(r':free\b', re.I),          # OpenRouter:  model:free
    re.compile(r'\bfree\b', re.I),
    re.compile(r'-free$', re.I),
]

# مدل‌های رایگان شناخته‌شده (پشتیبان، وقتی API قیمت نمی‌دهد)
# این سرویس‌ها نام‌هایی مثل "...-free" دارند، اما دسترسی واقعی به
# آن مدل به پلن/اعتبار همان حساب وابسته است. پس صرف نام مدل نباید در UI
# به‌عنوان «رایگانِ قطعی» نمایش داده شود (مثلاً HTTP 402 می‌دهد).
ACCOUNT_ENTITLEMENT_PROVIDERS = {"bynara", "nararouter", "nara_router"}

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
                r'\bsora\b|veo-|lyria|\btts-1\b|\bvideo\b', re.I),
     "تولید تصویر/ویدیو"),
    # OCR و بینایی محض
    (re.compile(r'\bocr\b|paddle', re.I), "پردازش تصویر"),

    # ── مدل‌های تخصصی گوگل (تست واقعی روی فهرست ۶۳مدلی Gemini) ──
    (re.compile(r'\bimage\b|nano.?banana', re.I), "تولید تصویر"),
    # «live» باید توکن مستقل باشد (پیش/پسش حرف نباشد) تا اسم‌هایی مثل
    # «alive-free» به‌اشتباه صوتی شمرده نشوند؛ ولی gemini-3.8-live و
    # live-translate گرفته می‌شوند.
    (re.compile(r'audio|realtime|(?<![a-z0-9])live(?![a-z0-9])', re.I),
     "صوت/گفتگوی زنده"),
    (re.compile(r'robotics|computer-use|antigravity|deep-research|\baqa\b', re.I),
     "عامل تخصصی (غیرچت)"),
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

    # NaraRouter/Bynara دسترسی مدل را بر اساس پلن و اعتبار حساب کنترل
    # می‌کند؛ عبارت Free در نام مدل به‌تنهایی تضمین پرداخت‌نکردن نیست.
    # اما برعکسِ قبلی، نام رایگان را هم نادیده نگیر: مدل را «کاندیدای
    # رایگان» علامت بزن (UI آن را 🆓؟ نشان می‌دهد) تا با تست واقعی
    # (کاوش ۱توکنی) تأیید یا رد شود.
    if prov in ACCOUNT_ENTITLEMENT_PROVIDERS:
        for pat in FREE_NAME_PATTERNS:
            if pat.search(mid):
                return True, "نام مدل رایگان است — تأییدنشده (تست بزنید)"
        return False, ""

    # ── روش سوم: الگوی نام ──
    for pat in FREE_NAME_PATTERNS:
        if pat.search(mid):
            return True, "نام مدل نشان‌دهنده نسخه رایگان است"

    # ── روش چهارم: فهرست شناخته‌شده ──
    for p, lst in KNOWN_FREE.items():
        if (not prov or prov == p) and mid in lst:
            return True, "در فهرست مدل‌های رایگان شناخته‌شده"

    return False, ""


def _flat_pricing(item):
    """
    کشف خودکار قیمتِ «فلت» با نام‌های دلخواه روترها.

    هر سرویسِ سازگار با OpenAI فیلد استاندارد pricing ندارد؛ روترها
    قیمت را با نام‌های خودشان می‌فرستند:
        input_idr_per_1k / output_idr_per_1k   (Bynara)
        input_price / output_price
        input_cost_per_1k / output_cost_per_1k
        input / output                         (ساده)
    قاعدهٔ عمومی: کلید عددی که در نامش input/prompt یا output/completion
    دارد و بوستان قیمت (price/cost/per/idr/usd) یا خودِ نامِ ساده است،
    قیمتِ همان سمت است. فیلدهای cache/read و سقف‌های توکن (max_completion_tokens)
    به‌طور طبیعی کنار می‌روند.
    """
    inp = out = None
    for k, v in item.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        kl = k.lower()
        is_in = ("input" in kl or "prompt" in kl)
        is_out = ("output" in kl or "completion" in kl)
        if not (is_in ^ is_out):        # هیچ‌کدام یا هر دو؟ ردّ کن
            continue
        has_price_hint = ("price" in kl or "cost" in kl or "per" in kl
                          or "idr" in kl or "usd" in kl
                          or kl in ("input", "output", "prompt", "completion"))
        if not has_price_hint:
            continue
        if is_in and inp is None:
            inp = v
        elif is_out and out is None:
            out = v
    if inp is None and out is None:
        return None
    return {"prompt": inp, "completion": out}


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
            # قیمت فلت با نام‌های دلخواه روترها (input_idr_per_1k،
            # input_price، output_cost_per_1k و…) به‌طور خودکار کشف و به
            # شکل استاندارد درمی‌آید تا رایگان/پولی «از خود سرویس» خوانده
            # شود — دقیق‌تر از نام مدل (نمونهٔ واقعی: مدل‌های «...-free»
            # که قیمت غیرصفر دارند و 403/402 می‌دهند).
            if not isinstance(pricing, dict):
                pricing = _flat_pricing(item)
            ctx = item.get("context_length") or item.get("context_window")
            # Groq فیلد active دارد؛ مدل غیرفعال کار نمی‌کند
            active = item.get("active", True)
            # OpenAI فیلد shutdown_date دارد؛ مدلی که تاریخ خاموشی گرفته
            # در حال حذف از سرویس است — نباید به کاربر پیشنهاد شود.
            shutdown = item.get("shutdown_date")
        else:
            continue
        if not mid:
            continue
        # گوگل شناسه‌ها را با پیشوند «models/» می‌فرستد؛ هر دو شکل سمت
        # سرور کار می‌کند ولی بدون پیشوند برای نمایش، تطبیق تنظیمات
        # ذخیره‌شده و KNOWN_FREE تمیزتر است.
        if mid.startswith("models/"):
            mid = mid[len("models/"):]

        is_chat, kind = classify_model(mid)
        if chat_only and not is_chat:
            skipped.append({"id": mid, "kind": kind})
            continue
        if active is False:
            skipped.append({"id": mid, "kind": "غیرفعال"})
            continue
        if shutdown:
            skipped.append({"id": mid, "kind": f"بازنشسته ({shutdown})"})
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
# کاوش واقعی رایگان‌بودن مدل (برای روترهای حساب‌محور مثل Bynara)
# ---------------------------------------------------------------------------
# در این روترها تنها راهِ قطعیِ تشخیص رایگان/پولی، فرستادن یک درخواست
# واقعیِ کوچک به خود مدل است:
#   200 → مدل برای این حساب رایگان است
#   429 → رایگان است ولی فعلاً به سقف نرخ/روزانه رسیده
#   402 → نیازمند اعتبار/پرداخت
#   403/404 → بدون دسترسی / مدل فعال نیست
def classify_probe_status(status, body=""):
    """
    نتیجهٔ کاوش یک مدل را طبقه‌بندی می‌کند.

    خروجی: (verdict, reason)
        verdict = True   → برای این حساب رایگان است
        verdict = False  → پولی/بدون دسترسی است
        verdict = None   → وضعیت نامشخص (خطای شبکه/سرور)
    """
    if status == 200:
        return True, "تست واقعی: پاسخ داد — برای حساب شما رایگان است"
    if status == 429:
        # ۴۲۹ همیشه یعنی «رایگان ولی rate-limit» نیست! OpenAI برای
        # اعتبار تمام‌شده هم ۴۲۹ می‌دهد:
        #   "You have no credits remaining ... credit_balance_exhausted"
        low = (body or "").lower()
        if any(k in low for k in ("credit", "billing", "top up", "topup",
                                  "balance")):
            return False, "تست واقعی: اعتبار حساب این سرویس تمام شده است"
        return True, "تست واقعی: رایگان است ولی فعلاً به سقف نرخ/روزانه رسیده"
    if status == 402:
        return False, "تست واقعی: نیازمند اعتبار/پرداخت است"
    if status == 403:
        # روتر Bynara برای مدل‌های خارج از پلن، پیام صریح دارد:
        # "Your plan does not include the requested model."
        if body and "plan" in body.lower():
            return False, "تست واقعی: پلن حساب شما این مدل را شامل نمی‌شود"
        return False, "تست واقعی: کلید شما به این مدل دسترسی ندارد"
    if status == 404:
        return False, "تست واقعی: این مدل روی سرویس وجود ندارد (حذف/بازنشسته شده)"
    if status == 400 and re.search(
            r"model (is |was )?not available|requested model is not available",
            (body or "").lower()):
        return False, "تست واقعی: این مدل روی سرویس وجود ندارد (حذف/بازنشسته شده)"
    if status == 0:
        return None, "تست واقعی: خطای شبکه — وضعیت نامشخص"
    return None, f"تست واقعی: پاسخ HTTP {status} — وضعیت نامشخص"


def apply_probes(models, probes):
    """
    نتیجهٔ کاوش‌های ذخیره‌شده را روی فهرست غنی‌شدهٔ مدل‌ها اعمال می‌کند.

    probes: {model_id: {"v": True/False/None, "s": status, "t": epoch}}

    برای هر مدل:
      free_verified = True/False/None   (نتیجهٔ تست واقعی، اگر موجود)
      free/free_reason فقط وقتی verdict قطعی است بازنویسی می‌شود.
    """
    if not probes:
        return models
    for m in models:
        pr = probes.get(m.get("id", ""))
        if not isinstance(pr, dict):
            continue
        v = pr.get("v")
        m["free_verified"] = v
        m["probe_status"] = pr.get("s")
        if v is True or v is False:
            _, reason = classify_probe_status(pr.get("s", 0))
            m["free"] = v
            m["free_reason"] = reason
    # با نتیجهٔ واقعی، ترتیب (رایگان‌ها اول) را دوباره بچین
    models.sort(key=lambda m: (not m["free"], m["id"]))
    return models


# ---------------------------------------------------------------------------
# ترجمه صادقانه کد وضعیت
# ---------------------------------------------------------------------------
STATUS_MEANING = {
    200: ("ok",      "✅ کلید معتبر است و سرویس پاسخ داد"),
    401: ("bad_key", "❌ کلید API نامعتبر است یا منقضی شده"),
    402: ("payment", "💳 پرداخت یا اعتبار حساب برای این مدل/سرویس لازم است"),
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
# خطای زمان‌شمار شبکه — شامل شکل‌های requests و urllib3
_TIMEOUT_RE = re.compile(
    r'ReadTimeout|Read timed out|read timeout=|ConnectTimeout|Connection timed out',
    re.I)
# میزبانِ مقصد از متن خطای urllib3: host='tokenforge.ai.studio'
_HOST_RE = re.compile(r"host='([^']+)'|host=([^,)\s]+)")

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

    (re.compile(r'unsupported.?country|region|not available in your'
                r'|location is not supported|user location', re.I),
     "این سرویس در منطقه شما در دسترس نیست",
     "از پروکسی استفاده کنید یا سرویس داخلی انتخاب کنید. گوگل (Gemini) "
     "آی‌پی ایران را می‌بندد؛ به پروکسی HTTP/SOCKS فعال نیاز دارد."),

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

    # ── خطای زمان‌شمار (Timeout) ──
    # مدل‌های auto/… مسیر را خودکار انتخاب می‌کنند؛ اگر روتر درخواست را
    # به سرویس بالادستی کُندی بفرستد (نمونهٔ واقعی: auto/bynara که به
    # tokenforge.ai.studio می‌رود) فقط زمان‌شمار می‌ماند. نام میزبانِ
    # نهایی را هم نشان می‌دهیم تا معلوم شود مشکل کجاست.
    if _TIMEOUT_RE.search(text):
        h = _HOST_RE.search(text)
        upstream = (h.group(1) or h.group(2)) if h else ""
        if model and model.lower().startswith("auto"):
            hint = (f"مدل «{model}» مسیر را خودکار انتخاب می‌کند و این بار به "
                    "سرویسی رسیده که پاسخ نمی‌دهد. از تنظیمات یک مدل مشخص "
                    "(نه auto) — ترجیحاً یکی از مدل‌های 🆓 — انتخاب کنید.")
        else:
            hint = ("سرویس‌دهنده در زمان مقرر پاسخ نداد؛ معمولاً یعنی مدل یا "
                    "مسیر انتخابی کُند/ازکارافتاده است. مدل دیگری انتخاب کنید "
                    "و دوباره امتحان کنید.")
        if upstream:
            hint += f" میزبانِ مقصد: {upstream}"
        title = "سرویس در زمان مقرر پاسخ نداد (Timeout)"
        if model:
            title += f" — «{model}»"
        return {"title": title, "hint": hint, "detail": msg[:300]}

    for pat, title, hint in API_ERROR_HINTS:
        if pat.search(text):
            if model:
                title = f"{title} — «{model}»"
            return {"title": title, "hint": hint, "detail": msg[:300]}

    return {"title": "خطا در ارتباط با سرویس هوش مصنوعی",
            "hint": "جزئیات را ببینید یا مدل/سرویس دیگری امتحان کنید.",
            "detail": msg[:300]}


# ═════════════════════════════════════════════════════════════════
# فشرده‌سازی تکرار غیرعادی پاسخ مدل
# ═════════════════════════════════════════════════════════════════
# بعضی مسیرهای رایگانِ روترها (مشاهده‌شده: مسیر «TokenForge» روی یک
# مدل free در NaraRouter/Bynara) پاسخ را با ده‌ها تکرار پیاپیِ یک جملهٔ
# تبلیغاتی شروع می‌کنند و بعد متن واقعی را می‌فرستند:
#
#     «I am Claude Opus 5, available through TokenForge.» × ۷۵
#
# این تابع فقط «تکرار پیاپیِ یک جمله/سطر معنادار» را (۵ بار یا بیشتر)
# به یک نمونه فشرده می‌کند و برچسب شفاف می‌گذارد. متن‌های عادی هرگز
# چنین الگویی ندارند، پس خطر تغییر پاسخ سالم تقریباً صفر است.

# جمله: شروع با غیرفاصله، ۲۰ تا ۳۰۰ نویسه، پایان با نقطه/علامت سؤال
_SENT_RUN = re.compile(r'(\S[^\n]{19,299}?[.!?؟])(?:\s*\1){4,}')
# سطر کامل (بدون نیاز به علائم نگارشی) — برای تکرارِ خط‌به‌خط
_LINE_RUN = re.compile(r'(?:^|\n)([^\s\n][^\n]{19,199})[ \t]*(?:\n[ \t]*\1[ \t]*){4,}(?=\n|$)')

# فقط واحدهایی معنادار فشرده شوند؛ جداکننده‌های جدول/کد مثل
# «────...» یا «----...» که فقط نویسه‌های تکراری‌اند دست نمی‌زنیم.
_HAS_WORD = re.compile(r'[\w\u0600-\u06FF]')

# برچسبی که جای تکرارها می‌نشیند (در Markdown هم بی‌خطر است)
_REP_TAG = " *[(این متن {n} بار پیاپی تکرار شده بود — فشرده شد)]* "

REPETITION_WARNING = (
    "⚠️ پاسخ مدل شامل تکرار غیرعادی بود و خودکار فشرده شد. "
    "مدل/مسیر انتخابی احتمالاً معیوب است — لطفاً از تنظیمات، "
    "مدل دیگری انتخاب کنید."
)


def collapse_repeated_text(text):
    """
    تکرارهای پیاپیِ غیرعادی را فشرده می‌کند.

    خروجی: (متن_جدید, تعداد_فشرده‌سازی)
        متن_جدید     — همان متن یا نسخهٔ فشرده‌شده
        تعداد_فشرده‌سازی — چند «رگبار تکرار» جمع شد (۰ = بدون تغییر)
    """
    if not text or len(text) < 120:
        return text, 0

    collapsed = 0

    def _repl(m):
        nonlocal collapsed
        unit = m.group(1)
        if not _HAS_WORD.search(unit):
            return m.group(0)          # جداکنندهٔ جدول/کد — دست نزن
        n = m.group(0).count(unit)
        if n < 5:
            return m.group(0)
        collapsed += 1
        return unit + _REP_TAG.format(n=n)

    # دور اول: جمله‌های جمله‌بندی‌شده (پوشندهٔ حالت «TokenForge.»)
    text = _SENT_RUN.sub(_repl, text)
    # دور دوم: سطرهای کاملِ تکراری
    text = _LINE_RUN.sub(_repl, text)

    if collapsed:
        text = REPETITION_WARNING + "\n\n" + text
    return text, collapsed


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
