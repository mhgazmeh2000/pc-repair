# -*- coding: utf-8 -*-
"""
attachments.py — مدیریت پیوست تصویر و فایل در چت
====================================================================
مسئله:
    همه مدل‌ها تصویر را نمی‌فهمند. اگر عکس را به مدلی بفرستیم که
    قابلیت بینایی ندارد، یا خطا می‌گیریم یا مدل بی‌سروصدا نادیده‌اش
    می‌گیرد و کاربر فکر می‌کند مدل عکس را دیده.

راهکار:
    پیش از ارسال بررسی می‌کنیم که مدل انتخابی از تصویر پشتیبانی
    می‌کند یا نه، و اگر نه به کاربر هشدار می‌دهیم.

فایل‌های متنی برای همه مدل‌ها کار می‌کنند چون محتوایشان مستقیماً
داخل پیام قرار می‌گیرد.
"""

import os
import re
import base64
import mimetypes

# ---------------------------------------------------------------------------
# فرمت‌های پشتیبانی‌شده
# ---------------------------------------------------------------------------
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

TEXT_EXT = {
    ".txt", ".log", ".md", ".csv", ".json", ".xml", ".yaml", ".yml",
    ".ini", ".cfg", ".conf", ".reg", ".bat", ".cmd", ".ps1", ".sh",
    ".py", ".js", ".ts", ".html", ".css", ".sql", ".env", ".toml",
    ".nfo", ".dmp",          # گزارش خطای ویندوز
}

MAX_IMAGE_MB = 5
MAX_TEXT_KB = 200
MAX_TEXT_CHARS = 60000

# ---------------------------------------------------------------------------
# مدل‌هایی که تصویر را می‌فهمند
# ---------------------------------------------------------------------------
VISION_PATTERNS = [
    re.compile(r'gpt-4o|gpt-4\.1|gpt-4-turbo|gpt-4-vision|o1|o3|o4', re.I),
    re.compile(r'claude-(3|4|opus|sonnet|haiku)', re.I),
    re.compile(r'gemini', re.I),
    re.compile(r'llama.*(vision|scout|maverick)|llama-4', re.I),
    re.compile(r'pixtral|qwen.*vl|internvl|llava|molmo', re.I),
    re.compile(r'grok.*vision|grok-[2-9]', re.I),
    re.compile(r'\bvision\b|multimodal|-vl\b', re.I),
]

# مدل‌هایی که صراحتاً متن‌محورند (برای جلوگیری از تطبیق اشتباه)
TEXT_ONLY_PATTERNS = [
    re.compile(r'whisper|embed|tts|guard|moderation', re.I),
    re.compile(r'deepseek-(chat|coder|reasoner)|deepseek-v3|deepseek-r1', re.I),
    re.compile(r'^gpt-3\.5|davinci|babbage', re.I),
    re.compile(r'mixtral|gemma|codestral|mistral-(small|large|nemo)', re.I),
    re.compile(r'llama-3\.[123]-\d+b|llama3-\d+b', re.I),   # نسخه‌های متنی Llama 3
]


def model_supports_vision(model_id):
    """
    آیا این مدل تصویر را می‌فهمد؟

    خروجی: (bool, دلیل)
    """
    mid = (model_id or "").strip()
    if not mid:
        return False, "مدلی انتخاب نشده"

    for p in TEXT_ONLY_PATTERNS:
        if p.search(mid):
            return False, "این مدل فقط متن را پردازش می‌کند"

    for p in VISION_PATTERNS:
        if p.search(mid):
            return True, "این مدل از تصویر پشتیبانی می‌کند"

    return False, "پشتیبانی از تصویر در این مدل مشخص نیست"


def classify(filename):
    """نوع فایل را بر اساس پسوند تشخیص می‌دهد."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in IMAGE_EXT:
        return "image", ext
    if ext in TEXT_EXT:
        return "text", ext
    return "unsupported", ext


def check_file(filename, size_bytes, model_id=None):
    """
    پیش از آپلود بررسی می‌کند که فایل قابل استفاده است یا نه.

    خروجی dict:
        ok            : قابل پیوست است؟
        kind          : image | text | unsupported
        needs_vision  : نیاز به مدل بینایی دارد؟
        vision_ok     : مدل فعلی پشتیبانی می‌کند؟
        message       : پیام فارسی
    """
    kind, ext = classify(filename)

    if kind == "unsupported":
        return {"ok": False, "kind": kind, "ext": ext,
                "message": f"فرمت «{ext or '؟'}» پشتیبانی نمی‌شود. "
                           "فقط تصویر (jpg, png, gif, webp) و فایل متنی "
                           "(txt, log, json, csv و...) قابل ارسال است."}

    if kind == "image":
        mb = size_bytes / (1024 * 1024)
        if mb > MAX_IMAGE_MB:
            return {"ok": False, "kind": kind, "ext": ext,
                    "message": f"حجم تصویر {mb:.1f} مگابایت است — "
                               f"حداکثر مجاز {MAX_IMAGE_MB} مگابایت."}
        vision_ok, why = model_supports_vision(model_id)
        return {"ok": True, "kind": kind, "ext": ext,
                "needs_vision": True, "vision_ok": vision_ok,
                "message": why if vision_ok else
                           f"⚠️ {why} — تصویر ارسال می‌شود ولی ممکن است "
                           "نادیده گرفته شود. مدلی با قابلیت بینایی "
                           "انتخاب کنید (مثل gpt-4o یا gemini)."}

    kb = size_bytes / 1024
    if kb > MAX_TEXT_KB:
        return {"ok": False, "kind": kind, "ext": ext,
                "message": f"حجم فایل {kb:.0f} کیلوبایت است — "
                           f"حداکثر مجاز {MAX_TEXT_KB} کیلوبایت."}
    return {"ok": True, "kind": kind, "ext": ext,
            "needs_vision": False, "vision_ok": True,
            "message": "فایل متنی — با همه مدل‌ها کار می‌کند"}


def build_message_content(text, attachments, model_id=None):
    """
    پیام کاربر را به قالب مناسب API تبدیل می‌کند.

    اگر تصویری هست و مدل بینایی دارد → قالب آرایه‌ای OpenAI
    وگرنه → رشته ساده (محتوای متنی فایل‌ها چسبانده می‌شود)
    """
    atts = attachments or []
    images = [a for a in atts if a.get("kind") == "image"]
    texts = [a for a in atts if a.get("kind") == "text"]

    # محتوای فایل‌های متنی داخل پیام قرار می‌گیرد
    parts = [text or ""]
    for a in texts:
        content = (a.get("content") or "")[:MAX_TEXT_CHARS]
        truncated = len(a.get("content") or "") > MAX_TEXT_CHARS
        parts.append(
            f"\n\n--- محتوای فایل «{a.get('name')}» ---\n"
            f"```\n{content}\n```"
            + ("\n(بخشی از فایل به‌دلیل حجم زیاد حذف شد)" if truncated else "")
        )
    merged = "".join(parts).strip()

    vision_ok, _ = model_supports_vision(model_id)
    if images and vision_ok:
        content = [{"type": "text", "text": merged or "این تصویر را بررسی کن."}]
        for a in images:
            data_url = a.get("data_url")
            if data_url:
                content.append({"type": "image_url",
                                "image_url": {"url": data_url}})
        return content, {"images_sent": len(content) - 1,
                         "texts_merged": len(texts)}

    if images and not vision_ok:
        names = "، ".join(a.get("name", "?") for a in images)
        merged += (f"\n\n[توجه: کاربر {len(images)} تصویر پیوست کرد ({names}) "
                   "ولی مدل فعلی قابلیت پردازش تصویر ندارد. "
                   "از کاربر بخواه محتوای تصویر را توضیح دهد.]")
        return merged, {"images_sent": 0, "images_skipped": len(images),
                        "texts_merged": len(texts)}

    return merged, {"images_sent": 0, "texts_merged": len(texts)}


def sniff_data_url(data_url, filename=""):
    """
    نوع و حجم واقعی یک data URL را استخراج می‌کند.
    نباید به پسوند فایل اعتماد کرد — کاربر می‌تواند exe را png بنامد.
    """
    m = re.match(r'^data:([^;,]+);base64,(.*)$', data_url or "", re.S)
    if not m:
        return {"ok": False, "message": "داده فایل نامعتبر است."}

    mime, b64 = m.group(1).lower(), m.group(2)
    try:
        raw = base64.b64decode(b64[:64] + "=" * (-len(b64[:64]) % 4))
    except Exception:
        return {"ok": False, "message": "داده فایل قابل خواندن نیست."}

    # امضای فایل (magic bytes)
    sigs = {
        b"\xff\xd8\xff": "image/jpeg",
        b"\x89PNG\r\n\x1a\n": "image/png",
        b"GIF87a": "image/gif",
        b"GIF89a": "image/gif",
        b"BM": "image/bmp",
    }
    detected = None
    for sig, t in sigs.items():
        if raw.startswith(sig):
            detected = t
            break
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        detected = "image/webp"

    if mime.startswith("image/") and not detected:
        return {"ok": False,
                "message": f"فایل «{filename}» تصویر معتبری نیست "
                           "(محتوای آن با پسوندش نمی‌خواند)."}

    size = int(len(b64) * 3 / 4)
    return {"ok": True, "mime": detected or mime, "size": size}


if __name__ == "__main__":
    print("── پشتیبانی از تصویر ──\n")
    for m in ["gpt-4o", "gpt-4o-mini", "gemini-2.0-flash",
              "claude-sonnet-4-20250514", "llama-3.3-70b-versatile",
              "deepseek-chat", "meta-llama/llama-4-scout", "gpt-3.5-turbo",
              "qwen/qwen2.5-vl-72b-instruct", "mixtral-8x7b-32768"]:
        ok, why = model_supports_vision(m)
        print(f"  {'🖼️' if ok else '📝'} {m[:34]:36} {why}")

    print("\n── بررسی فایل ──\n")
    for name, size, model in [
        ("screenshot.png", 2 * 1024 * 1024, "gpt-4o"),
        ("screenshot.png", 2 * 1024 * 1024, "llama-3.3-70b-versatile"),
        ("huge.jpg", 9 * 1024 * 1024, "gpt-4o"),
        ("error.log", 50 * 1024, "llama-3.3-70b-versatile"),
        ("virus.exe", 1000, "gpt-4o"),
    ]:
        r = check_file(name, size, model)
        print(f"  {'✅' if r['ok'] else '❌'} {name:16} → {r['message'][:62]}")
