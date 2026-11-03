# -*- coding: utf-8 -*-
"""
providers.py — مدیریت سرویس‌دهنده‌های هوش مصنوعی
====================================================================
مشکلی که حل می‌کند:
    قبلاً فهرست provider در سه جای مختلف hardcode شده بود
    (HTML، بک‌اند، JavaScript). افزودن یک سرویس جدید یعنی
    ویرایش هر سه — و کاربر اصلاً نمی‌توانست سرویس دلخواه اضافه کند.

حالا:
    • فهرست داخلی گسترده‌تر (شامل سرویس‌های ایرانی)
    • کاربر می‌تواند سرویس دلخواه اضافه/ویرایش/حذف کند
    • همه از یک منبع می‌خوانند
"""

import os
import json
import copy

# ---------------------------------------------------------------------------
# سرویس‌دهنده‌های داخلی
#   needs_proxy: آیا معمولاً از ایران نیاز به پروکسی دارد
# ---------------------------------------------------------------------------
BUILTIN = {
    "groq": {
        "name": "Groq",
        "desc": "رایگان و بسیار سریع — GPT-OSS و Qwen",
        "base_url": "https://api.groq.com/openai/v1",
        # llama-3.3-70b-versatile و llama-3.1-8b-instant را Groq بازنشسته
        # کرد (تست واقعی: 404 model does not exist). فهرست فعلی چت:
        # gpt-oss-120b (بهترین کیفیت)، gpt-oss-20b، qwen3.8-27b، allam-2-7b
        "default_model": "openai/gpt-oss-120b",
        "models": ["openai/gpt-oss-120b", "openai/gpt-oss-20b",
                   "qwen/qwen3.8-27b", "allam-2-7b"],
        "key_url": "https://console.groq.com/keys",
        "needs_proxy": False,
    },
    "openai": {
        "name": "OpenAI",
        "desc": "GPT-4o و GPT-5",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini",
                   "o3-mini", "gpt-3.5-turbo"],
        "key_url": "https://platform.openai.com/api-keys",
        "needs_proxy": True,
    },
    "bynara": {
        "name": "NaraRouter / Bynara",
        "desc": "OpenAI-compatible gateway — دسترسی مدل‌ها به پلن و اعتبار حساب وابسته است",
        "base_url": "https://router.bynara.id/v1",
        # auto/bynara روی روتر حذف شده و 404 می‌دهد (تست واقعی).
        # مدل پیش‌فرض باید یک مدل رایگانِ فعالِ قیمت‌صفر باشد؛
        # فهرست کامل و قیمت واقعی هر مدل با «دریافت فهرست واقعی» می‌آید.
        "default_model": "laguna-s-2.1",
        # jev قدیمی حذف شد؛ jev-1.14.0 از ۲۰۲۶-۱۰ پرداختی است (۰.۳ IDR/1k)
        "models": ["laguna-s-2.1", "nemotron-3.5-lightning-free"],
        "key_url": "https://router.bynara.id/keys",
        "needs_proxy": False,
    },
    "openrouter": {
        "name": "OpenRouter",
        "desc": "دسترسی به صدها مدل با یک کلید",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o-mini",
        "models": ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet",
                   "google/gemini-2.0-flash-exp:free",
                   "meta-llama/llama-3.3-70b-instruct",
                   "deepseek/deepseek-chat", "qwen/qwen-2.5-72b-instruct"],
        "key_url": "https://openrouter.ai/keys",
        "needs_proxy": False,
    },
    "deepseek": {
        "name": "DeepSeek",
        "desc": "ارزان و قوی در کدنویسی",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "key_url": "https://platform.deepseek.com/api_keys",
        "needs_proxy": True,
    },
    "gemini": {
        "name": "Google Gemini",
        "desc": "سازگار با OpenAI API — پلن رایگان با سقف نرخ",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        # gemini-2.0/1.5 و حتی 2.5 برای کاربران جدید بازنشسته شده‌اند
        # (تست واقعی: 404 «no longer available to new users»). مدل‌های
        # زندهٔ تست‌شده: gemini-flash-latest ( alias همیشه‌به‌روز )،
        # 3.8-flash، 3.5-flash و lite ها. از ایران نیازمند پروکسی است.
        "default_model": "gemini-flash-latest",
        "models": ["gemini-flash-latest", "gemini-3.8-flash",
                   "gemini-3.5-flash", "gemini-3.1-flash-lite",
                   "gemini-flash-lite-latest"],
        "key_url": "https://aistudio.google.com/apikey",
        "needs_proxy": True,
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "desc": "Claude Sonnet و Opus",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-20250514",
        "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514",
                   "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
        "key_url": "https://console.anthropic.com/settings/keys",
        "needs_proxy": True,
    },
    "xai": {
        "name": "xAI Grok",
        "desc": "مدل‌های Grok",
        "base_url": "https://api.x.ai/v1",
        "default_model": "grok-2-latest",
        "models": ["grok-2-latest", "grok-2-vision-latest", "grok-beta"],
        "key_url": "https://console.x.ai",
        "needs_proxy": True,
    },
    "mistral": {
        "name": "Mistral AI",
        "desc": "مدل‌های اروپایی",
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-small-latest",
        "models": ["mistral-large-latest", "mistral-small-latest",
                   "codestral-latest", "open-mistral-nemo"],
        "key_url": "https://console.mistral.ai/api-keys",
        "needs_proxy": True,
    },
    "together": {
        "name": "Together AI",
        "desc": "مدل‌های متن‌باز",
        "base_url": "https://api.together.xyz/v1",
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "models": ["meta-llama/Llama-3.3-70B-Instruct-Turbo",
                   "Qwen/Qwen2.5-72B-Instruct-Turbo",
                   "deepseek-ai/DeepSeek-V3"],
        "key_url": "https://api.together.xyz/settings/api-keys",
        "needs_proxy": True,
    },
    "avalai": {
        "name": "آوالای (AvalAI)",
        "desc": "🇮🇷 واسط ایرانی — بدون نیاز به پروکسی",
        "base_url": "https://api.avalai.ir/v1",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet-20241022",
                   "gemini-2.0-flash", "deepseek-chat"],
        "key_url": "https://avalai.ir",
        "needs_proxy": False,
    },
    "gapgpt": {
        "name": "گپ‌جی‌پی‌تی (GapGPT)",
        "desc": "🇮🇷 واسط ایرانی — بدون نیاز به پروکسی",
        "base_url": "https://api.gapgpt.app/v1",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet",
                   "gemini-2.0-flash", "deepseek-chat"],
        "key_url": "https://gapgpt.app",
        "needs_proxy": False,
    },
    "liara": {
        "name": "لیارا (Liara AI)",
        "desc": "🇮🇷 سرویس ابری ایرانی",
        "base_url": "https://ai.liara.ir/api/v1",
        "default_model": "openai/gpt-4o-mini",
        "models": ["openai/gpt-4o-mini", "openai/gpt-4o",
                   "google/gemini-2.0-flash"],
        "key_url": "https://console.liara.ir",
        "needs_proxy": False,
    },
    "ollama": {
        "name": "Ollama (محلی)",
        "desc": "اجرای مدل روی کامپیوتر خودتان — بدون کلید",
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.2",
        "models": ["llama3.2", "qwen2.5", "gemma2", "phi4", "mistral"],
        "key_url": "https://ollama.com/download",
        "needs_proxy": False,
    },
    "lmstudio": {
        "name": "LM Studio (محلی)",
        "desc": "سرور محلی LM Studio — بدون کلید",
        "base_url": "http://localhost:1234/v1",
        "default_model": "local-model",
        "models": ["local-model"],
        "key_url": "https://lmstudio.ai",
        "needs_proxy": False,
    },
}


def _store_path():
    """مسیر فایل سرویس‌های سفارشی کاربر."""
    try:
        import backend_server
        return os.path.join(os.path.dirname(backend_server.SETTINGS_FILE),
                            "custom_providers.json")
    except Exception:
        return os.path.join(os.getcwd(), "custom_providers.json")


def _load_custom():
    try:
        with open(_store_path(), encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_custom(data):
    try:
        with open(_store_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _normalize(key, p):
    """فیلدهای جاافتاده را پر و مقادیر را تمیز می‌کند."""
    base = (p.get("base_url") or "").strip().rstrip("/")
    models = p.get("models") or []
    if isinstance(models, str):
        models = [m.strip() for m in models.replace(",", "\n").split("\n") if m.strip()]
    default_model = (p.get("default_model") or "").strip() or (models[0] if models else "")
    if default_model and default_model not in models:
        models = [default_model] + models
    return {
        "key": key,
        "name": (p.get("name") or key).strip(),
        "desc": (p.get("desc") or "").strip(),
        "base_url": base,
        "default_model": default_model,
        "models": models,
        "key_url": (p.get("key_url") or "").strip(),
        "needs_proxy": bool(p.get("needs_proxy", False)),
        "custom": bool(p.get("custom", False)),
    }


def list_providers():
    """همه سرویس‌دهنده‌ها — داخلی + سفارشی کاربر."""
    out = []
    custom = _load_custom()
    for k, v in BUILTIN.items():
        item = copy.deepcopy(v)
        # اگر کاربر یک سرویس داخلی را ویرایش کرده، نسخه او اولویت دارد
        if k in custom:
            item.update(custom[k])
        out.append(_normalize(k, item))
    for k, v in custom.items():
        if k not in BUILTIN:
            item = dict(v)
            item["custom"] = True
            out.append(_normalize(k, item))
    return out


def get_provider(key):
    for p in list_providers():
        if p["key"] == key:
            return p
    return None


# مدل‌هایی که سرویس‌دهنده‌ها بازنشسته/حذف کرده‌اند (تست واقعی: 404
# «model does not exist»). تنظیمات ذخیره‌شدهٔ کاربرانی که هنوز این
# مدل‌ها را دارند، موقع خواندن تنظیمات به مدل پیش‌فرضِ فعلی همان
# سرویس مهاجرت می‌کند تا برنامه به‌جای خطای 404 دوباره کار کند.
DEPRECATED_MODELS = {
    # Groq بازنشسته کرد
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
    "gemma-7b-it",
    "gemma2-9b-it",
    # روتر Bynara حذف کرد
    "auto/bynara",
    "jev",                              # ← jev-1.14.0 پرداختی جایگزین شد
    "muse-spark-1.3-contributor-free",  # پیشنهاد رایگان موقتی تمام شد
    "mimo-v2.5", "mimo-v2.5-pro",       # با mimo-v2.6 جایگزین شدند
    # Google Gemini — برای کاربران جدید بازنشسته (404 no longer available)
    "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite",
    "gemini-2.0-flash", "gemini-2.0-flash-lite",
    "gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.5-flash-8b",
    "gemini-3.8-flash-lite", "aqa",
}


def detect_provider_by_url(url):
    """
    سرویس‌دهندهٔ داخلی را از روی نام میزبان آدرس تشخیص می‌دهد.

    چرا لازم است؟ کاربر که بین سرویس‌ها جابه‌جا می‌شود فقط Base URL و
    کلید را عوض می‌کند و «انتخاب سرویس» قدیمی می‌ماند؛ آن‌وقت منطق
    رایگان/پولی سرویس اشتباه اعمال می‌شود (نمونهٔ واقعی: فهرست
    OpenAI با provider=gemini → همهٔ مدل‌ها 🆓 نمایش داده می‌شد!).

    خروجی: کلید سرویس (مثل "openai") یا None اگر میزبان شناخته نشد.
    """
    try:
        from urllib.parse import urlparse
        host = (urlparse(url or "").hostname or "").lower()
    except Exception:
        return None
    if not host:
        return None
    for key, p in BUILTIN.items():
        try:
            phost = (urlparse(p.get("base_url") or "").hostname or "").lower()
            if phost and phost == host:
                return key
        except Exception:
            continue
    return None


def save_provider(key, data):
    """افزودن یا ویرایش یک سرویس‌دهنده."""
    key = (key or "").strip().lower().replace(" ", "_")
    if not key:
        return {"success": False, "error": "شناسه سرویس نمی‌تواند خالی باشد."}
    if not (data.get("base_url") or "").strip():
        return {"success": False, "error": "آدرس Base URL الزامی است."}

    custom = _load_custom()
    entry = dict(data)
    entry["custom"] = key not in BUILTIN
    custom[key] = _normalize(key, entry)
    if not _save_custom(custom):
        return {"success": False, "error": "ذخیره‌سازی روی دیسک ناموفق بود."}
    return {"success": True, "provider": custom[key]}


def delete_provider(key):
    """
    حذف سرویس سفارشی، یا بازگرداندن سرویس داخلی به حالت اولیه.
    سرویس‌های داخلی هرگز کاملاً حذف نمی‌شوند.
    """
    custom = _load_custom()
    if key not in custom:
        if key in BUILTIN:
            return {"success": False,
                    "error": "این سرویس داخلی است و قابل حذف نیست."}
        return {"success": False, "error": "سرویس یافت نشد."}
    custom.pop(key)
    _save_custom(custom)
    return {"success": True,
            "restored": key in BUILTIN,
            "message": "به تنظیمات پیش‌فرض بازگشت." if key in BUILTIN else "حذف شد."}


def default_models(key):
    p = get_provider(key)
    return p["models"] if p else []


if __name__ == "__main__":
    ps = list_providers()
    print(f"{len(ps)} سرویس‌دهنده:\n")
    for p in ps:
        flag = "🔒" if p["needs_proxy"] else "🟢"
        tag = " [سفارشی]" if p["custom"] else ""
        print(f"  {flag} {p['name']:22} {len(p['models'])} مدل{tag}")
        print(f"     {p['base_url']}")
