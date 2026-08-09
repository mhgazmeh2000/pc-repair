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
        "desc": "رایگان و بسیار سریع — Llama 3.3",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                   "llama3-70b-8192", "llama3-8b-8192", "gemma2-9b-it"],
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
        "desc": "سازگار با OpenAI API",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.0-flash",
        "models": ["gemini-2.0-flash", "gemini-2.0-flash-lite",
                   "gemini-1.5-pro", "gemini-1.5-flash"],
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
