# -*- coding: utf-8 -*-
"""
chat_memory.py — مدیریت هوشمند حافظه گفتگو
====================================================================
مسئله:
    قبلاً همیشه فقط ۸ پیام آخر به AI فرستاده می‌شد — بدون توجه به
    ظرفیت مدل. برای gpt-4o با ۱۲۸هزار توکن این یعنی استفاده از
    ۱.۵٪ ظرفیت، و برای مدل کوچک ممکن بود همان ۸ تا هم زیاد باشد.

راهکار:
    ۱. ظرفیت واقعی مدل را تشخیص بده
    ۲. بودجه امن حساب کن (سهم پاسخ و پرامپت سیستم کنار گذاشته شود)
    ۳. از جدیدترین پیام به عقب برو تا بودجه پر شود
    ۴. اگر پیام قدیمی جا نماند، خلاصه‌اش کن به‌جای دور انداختن
"""

import re

# ظرفیت پنجره مدل‌های شناخته‌شده (توکن)
MODEL_CONTEXT = {
    # OpenAI
    r'gpt-4o|gpt-4\.1|gpt-4-turbo': 128_000,
    r'o1|o3|o4': 200_000,
    r'gpt-3\.5': 16_385,
    # Anthropic
    r'claude-(sonnet-4|opus-4)': 200_000,
    r'claude-3': 200_000,
    # Google
    r'gemini-2\.0|gemini-2\.5': 1_000_000,
    r'gemini-1\.5-pro': 2_000_000,
    r'gemini-1\.5': 1_000_000,
    # Meta / Groq
    r'llama-3\.3|llama-3\.1': 128_000,
    r'llama-4|scout|maverick': 128_000,
    r'llama3-\d+b': 8_192,
    # سایر
    r'deepseek': 64_000,
    r'mixtral': 32_768,
    r'gemma': 8_192,
    r'qwen': 32_768,
    r'mistral-large': 128_000,
    r'grok': 131_072,
}

DEFAULT_CONTEXT = 8_192      # محافظه‌کارانه برای مدل ناشناس
RESERVE_FOR_REPLY = 4_000    # جای پاسخ مدل
MIN_MESSAGES = 4             # حداقل حافظه، حتی روی مدل کوچک
MAX_MESSAGES = 60            # سقف منطقی — بیشتر از این فایده ندارد


def model_context(model_id, hint=None):
    """
    ظرفیت پنجره مدل را برمی‌گرداند.
    hint: اگر API خودش context_length داده، اولویت با آن است.
    """
    if hint:
        try:
            v = int(hint)
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass

    mid = (model_id or "").lower()
    for pat, ctx in MODEL_CONTEXT.items():
        if re.search(pat, mid):
            return ctx
    return DEFAULT_CONTEXT


def estimate_tokens(text):
    """
    تخمین تعداد توکن.

    نسبت کاراکتر به توکن برای فارسی و انگلیسی فرق دارد:
      انگلیسی ~۴ کاراکتر/توکن
      فارسی   ~۲ کاراکتر/توکن (چون در BPE بیشتر شکسته می‌شود)
    """
    if not text:
        return 0
    if isinstance(text, list):
        # قالب چندبخشی (متن + تصویر)
        total = 0
        for part in text:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    total += estimate_tokens(part.get("text", ""))
                elif part.get("type") == "image_url":
                    total += 800      # تخمین متوسط برای یک تصویر
        return total

    s = str(text)
    fa = sum(1 for c in s if '\u0600' <= c <= '\u06FF')
    other = len(s) - fa
    return int(fa / 2 + other / 4) + 1


def summarize_old(messages, max_chars=600):
    """
    پیام‌های قدیمی که جا نمی‌شوند را به یک خلاصه کوتاه تبدیل می‌کند.

    به‌جای دور انداختن کامل، حداقل موضوع گفتگو حفظ می‌شود تا
    AI بداند قبلاً درباره چه صحبت شده.
    """
    if not messages:
        return None

    topics = []
    for m in messages:
        if m.get("role") != "user":
            continue
        c = m.get("content", "")
        if isinstance(c, list):
            c = " ".join(p.get("text", "") for p in c if isinstance(p, dict))
        c = re.sub(r'\s+', ' ', str(c)).strip()
        if c and c not in topics:
            topics.append(c[:90])

    if not topics:
        return None

    body = "؛ ".join(topics)
    if len(body) > max_chars:
        body = body[:max_chars] + "..."

    return {
        "role": "system",
        "content": (f"[خلاصه {len(messages)} پیام قدیمی‌تر این گفتگو — "
                    f"موضوعاتی که کاربر مطرح کرده: {body}]")
    }


def build_history(messages, model_id, system_tokens=0, context_hint=None,
                  max_messages=None):
    """
    تاریخچه را به اندازه‌ای که در پنجره مدل جا می‌شود برمی‌گرداند.

    خروجی: (فهرست پیام‌ها، اطلاعات تشخیصی)
    """
    msgs = [m for m in (messages or []) if m.get("content")]
    if not msgs:
        return [], {"sent": 0, "total": 0, "context": 0}

    ctx = model_context(model_id, context_hint)
    budget = ctx - RESERVE_FOR_REPLY - system_tokens
    # حتی روی مدل خیلی کوچک، فضایی برای چند پیام بگذار
    budget = max(budget, 1500)

    cap = max_messages or MAX_MESSAGES

    kept, used = [], 0
    for m in reversed(msgs):
        t = estimate_tokens(m.get("content"))
        if kept and (used + t > budget or len(kept) >= cap):
            break
        kept.append(m)
        used += t

    kept.reverse()

    # حداقل تعداد پیام را تضمین کن
    if len(kept) < MIN_MESSAGES and len(msgs) >= MIN_MESSAGES:
        kept = msgs[-MIN_MESSAGES:]
        used = sum(estimate_tokens(m.get("content")) for m in kept)

    dropped = msgs[:len(msgs) - len(kept)]
    summary = None
    if dropped:
        summary = summarize_old(dropped)
        if summary:
            s_tok = estimate_tokens(summary["content"])
            if used + s_tok <= budget:
                kept.insert(0, summary)
                used += s_tok
            else:
                summary = None

    return kept, {
        "sent": len(kept) - (1 if summary else 0),
        "total": len(msgs),
        "dropped": len(dropped),
        "summarized": bool(summary),
        "tokens": used,
        "budget": budget,
        "context": ctx,
        "model": model_id,
    }


if __name__ == "__main__":
    print("── ظرفیت مدل‌ها ──\n")
    for m in ["gpt-4o", "gpt-3.5-turbo", "llama-3.3-70b-versatile",
              "llama3-8b-8192", "gemini-2.0-flash", "claude-sonnet-4-20250514",
              "mixtral-8x7b-32768", "unknown-model-x"]:
        print(f"  {m:30} {model_context(m):>10,} توکن")

    print("\n── چند پیام جا می‌شود؟ (پیام‌های ۳۰۰ کاراکتری فارسی) ──\n")
    fake = [{"role": "user" if i % 2 == 0 else "assistant",
             "content": "این یک پیام آزمایشی فارسی است. " * 10}
            for i in range(80)]

    for m in ["llama3-8b-8192", "mixtral-8x7b-32768",
              "llama-3.3-70b-versatile", "gpt-4o", "gemini-2.0-flash"]:
        kept, info = build_history(fake, m, system_tokens=1200)
        print(f"  {m:26} {info['sent']:>3} پیام از {info['total']}  "
              f"({info['tokens']:,} توکن از {info['budget']:,})"
              + ("  + خلاصه" if info['summarized'] else ""))
