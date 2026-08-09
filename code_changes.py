# -*- coding: utf-8 -*-
"""
استخراج، پیش‌نمایش و اعمال تغییرات کد پیشنهادی AI

جریان کار
─────────
    پاسخ AI (متن با بلوک‌های کد)
        ↓  extract_changes()
    فهرست تغییرات پیشنهادی
        ↓  build_preview()
    diff رنگی — کاربر می‌بیند دقیقاً چه چیزی عوض می‌شود
        ↓  apply_change()  ← فقط با تأیید صریح
    فایل روی دیسک + پشتیبان خودکار

چرا مرحلهٔ پیش‌نمایش حذف‌نشدنی است
──────────────────────────────────
مدل زبانی گاهی کل فایل را بازنویسی می‌کند در حالی که فقط باید سه خط
عوض می‌شد؛ گاهی هم بخشی از کد را حذف می‌کند بدون اینکه بگوید. اعمال
مستقیم یعنی کاربر بدون اینکه بفهمد کدش را از دست بدهد.

اینجا هیچ چیزی بدون تأیید صریح نوشته نمی‌شود، و هر نوشتن پشتیبان دارد.

شناسایی فایل مقصد
─────────────────
AI طبق دستور نقش `coder` باید نام فایل را در سطر اول بلوک بنویسد:

    ```python
    # فایل: src/main.py
    ...
    ```

اگر ننوشت، از متن قبل از بلوک حدس زده می‌شود — ولی با پرچم
`confident: False` تا رابط کاربری هشدار بدهد.
"""

import difflib
import os
import re

import workspace

# سقف‌ها
MAX_CHANGES = 20            # بیشتر از این یعنی پاسخ مدل از کنترل خارج شده
MAX_DIFF_LINES = 400        # diff بلندتر در مرورگر کند می‌شود
PREVIEW_MAX_KB = 512        # پیش‌نمایش diff فقط ابتدای فایل را می‌خواند
                            # (فایل‌های بزرگ کامل به حافظه نیایند)

# الگوی بلوک کد ```lang ... ```
_FENCE = re.compile(
    r"```([A-Za-z0-9_+-]*)[ \t]*\n(.*?)```",
    re.DOTALL,
)

# نام فایل در سطر اول بلوک — چند شکل رایج پشتیبانی می‌شود
_FILE_HINTS = [
    re.compile(r"^\s*(?:#|//|--|/\*|<!--)\s*فایل\s*[:：]\s*(.+?)\s*(?:\*/|-->)?\s*$"),
    re.compile(r"^\s*(?:#|//|--|/\*|<!--)\s*[Ff]ile\s*[:：]\s*(.+?)\s*(?:\*/|-->)?\s*$"),
    re.compile(r"^\s*(?:#|//|--)\s*([\w./\\-]+\.[A-Za-z0-9]{1,6})\s*$"),
]

# نام فایل در متن *قبل* از بلوک — پشتیبان وقتی سطر اول نداشت
_INLINE_PATH = re.compile(r"[`«\"']?([\w./-]+/[\w./-]+\.[A-Za-z0-9]{1,6})[`»\"']?")
_BARE_FILE = re.compile(r"[`«\"']([\w.-]+\.[A-Za-z0-9]{1,6})[`»\"']")

# زبان‌هایی که فایل کد نیستند — نباید به‌عنوان تغییر پیشنهاد شوند
_NON_FILE_LANGS = {
    "cmd", "bat", "batch", "powershell", "ps1", "shell", "console",
    "output", "text", "log", "diff",
}


def _strip_file_hint(body):
    """
    حذف سطر «# فایل: ...» از ابتدای بلوک.
    برگشت (نام فایل یا None، بدنهٔ بدون آن سطر).
    """
    lines = body.split("\n")
    if not lines:
        return None, body
    first = lines[0]
    for pat in _FILE_HINTS:
        m = pat.match(first)
        if m:
            name = m.group(1).strip().strip("`\"'«»")
            # سطر راهنما و یک خط خالی احتمالی بعدش حذف می‌شوند
            rest = lines[1:]
            if rest and not rest[0].strip():
                rest = rest[1:]
            return name, "\n".join(rest)
    return None, body


def _guess_path_from_text(text, known_paths):
    """
    یافتن نام فایل در متن توضیحی قبل از بلوک.
    اولویت با مسیرهایی که واقعاً در پروژه وجود دارند.
    """
    if not text:
        return None
    tail = text[-500:]          # فقط نزدیک‌ترین متن به بلوک

    lower_known = {p.lower(): p for p in known_paths}

    # اول مسیرهای کامل (شامل /)
    for m in reversed(list(_INLINE_PATH.finditer(tail))):
        cand = m.group(1).strip().replace("\\", "/")
        if cand.lower() in lower_known:
            return lower_known[cand.lower()]

    # بعد نام تنها — فقط اگر دقیقاً یک فایل با آن نام باشد
    for m in reversed(list(_BARE_FILE.finditer(tail))):
        name = m.group(1).strip().lower()
        hits = [p for p in known_paths if os.path.basename(p).lower() == name]
        if len(hits) == 1:
            return hits[0]
    return None


def extract_changes(reply_text, known_paths=None):
    """
    استخراج تغییرات پیشنهادی از پاسخ AI.

    known_paths: فهرست مسیرهای واقعی پروژه — برای اعتبارسنجی حدس‌ها.
    """
    if not reply_text:
        return {"success": True, "changes": [], "note": ""}

    known_paths = known_paths or []
    changes = []
    skipped_langs = []

    for m in _FENCE.finditer(reply_text):
        lang = (m.group(1) or "").strip().lower()
        body = m.group(2)

        if len(changes) >= MAX_CHANGES:
            break

        # بلوک‌های دستور شل/cmd تغییر فایل نیستند
        if lang in _NON_FILE_LANGS:
            skipped_langs.append(lang)
            continue
        if not body.strip():
            continue

        path, clean = _strip_file_hint(body)
        confident = path is not None

        # بلوکی که فقط سطر «# فایل: ...» دارد و بدنه ندارد، یعنی مدل
        # ناقص پاسخ داده. اعمالش فایل را خالی می‌کرد.
        if not clean.strip():
            continue

        if not path:
            before = reply_text[:m.start()]
            path = _guess_path_from_text(before, known_paths)

        if not path:
            # بدون مقصد نمی‌توان تغییری اعمال کرد
            continue

        path = path.strip().replace("\\", "/").lstrip("/")

        changes.append({
            "id": f"chg{len(changes) + 1}",
            "path": path,
            "lang": lang or workspace.lang_of(path),
            "new_content": clean.rstrip("\n") + "\n",
            "confident": confident,
            "exists_in_project": path in known_paths,
        })

    note = ""
    if skipped_langs:
        note = (f"{len(skipped_langs)} بلوک دستور "
                f"({'، '.join(sorted(set(skipped_langs)))}) "
                "به‌عنوان تغییر فایل در نظر گرفته نشد.")

    return {"success": True, "changes": changes, "note": note}


def build_preview(change):
    """
    ساخت diff بین محتوای فعلی فایل و پیشنهاد AI.

    خروجی شامل سطرهای طبقه‌بندی‌شده است تا UI بتواند رنگ بزند،
    به‌جای اینکه رشتهٔ خام diff را نمایش دهد.
    """
    path = (change or {}).get("path", "")
    new_content = (change or {}).get("new_content", "")

    # max_kb برای جلوگیری از آوردن کل فایل‌های بزرگ به حافظه: حالا که
    # سقف بازکردن برداشته شده، read_file بدون max_kb فایل ۵۰ مگابایتی را
    # کامل می‌خواند و difflib روی آن سنگین می‌شود. اینجا فقط ابتدا خوانده
    # می‌شود و اگر فایل بزرگ بود، diff روی بخشِ خوانده‌شده ساخته می‌شود و
    # پرچم truncated به UI می‌رود تا هشدار بدهد.
    cur = workspace.read_file(path, max_kb=PREVIEW_MAX_KB)
    is_new = not cur.get("success")

    if is_new:
        # فایل جدید — کل محتوا افزوده است
        err = cur.get("error", "")
        if "خارج از پوشه" in err:
            return {"success": False, "error": err}
        old_lines = []
        old_text = ""
        mtime = None
    else:
        old_text = cur["content"]
        old_lines = old_text.splitlines()
        mtime = cur["mtime"]

    new_lines = new_content.splitlines()

    if old_text == new_content:
        return {
            "success": True, "path": path, "is_new": False,
            "identical": True, "rows": [], "added": 0, "removed": 0,
            "mtime": mtime,
            "note": "محتوای پیشنهادی با فایل فعلی یکسان است.",
        }

    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    rows = []
    added = removed = 0
    truncated = False

    def _add(r):
        """یک ردیف اضافه کن؛ اگر سقف پر شد، حلقه را با پرچم truncated قطع کن."""
        nonlocal truncated
        if len(rows) >= MAX_DIFF_LINES:
            truncated = True
            return False
        rows.append(r)
        return True

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if truncated:
            break

        if tag == "equal":
            # فقط چند خط زمینه در ابتدا و انتهای هر بلوک
            block = list(range(i1, i2))
            if len(block) <= 6:
                ctx = block
            else:
                ctx = block[:3] + [None] + block[-3:]
            for k in ctx:
                if k is None:
                    if not _add({"type": "gap", "text": "⋮"}):
                        break
                else:
                    if not _add({
                            "type": "same", "old_no": k + 1,
                            "new_no": j1 + (k - i1) + 1,
                            "text": old_lines[k],
                    }):
                        break
            if truncated:
                break
        elif tag == "delete":
            for k in range(i1, i2):
                removed += 1
                if not _add({"type": "del", "old_no": k + 1,
                             "new_no": None, "text": old_lines[k]}):
                    break
        elif tag == "insert":
            for k in range(j1, j2):
                added += 1
                if not _add({"type": "add", "old_no": None,
                             "new_no": k + 1, "text": new_lines[k]}):
                    break
        elif tag == "replace":
            for k in range(i1, i2):
                removed += 1
                if not _add({"type": "del", "old_no": k + 1,
                             "new_no": None, "text": old_lines[k]}):
                    break
            if not truncated:
                for k in range(j1, j2):
                    added += 1
                    if not _add({"type": "add", "old_no": None,
                                 "new_no": k + 1, "text": new_lines[k]}):
                        break

    # هشدار وقتی مدل بخش بزرگی را حذف کرده
    warning = ""
    if old_lines and removed > len(old_lines) * 0.5 and added < removed * 0.6:
        warning = (f"⚠️ این تغییر {removed} خط از {len(old_lines)} خط فایل را "
                   f"حذف می‌کند و فقط {added} خط اضافه می‌کند. "
                   "پیش از تأیید، با دقت بررسی کنید.")

    return {
        "success": True,
        "path": path,
        "is_new": is_new,
        "identical": False,
        "rows": rows,
        "added": added,
        "removed": removed,
        "old_lines": len(old_lines),
        "new_lines": len(new_lines),
        "truncated": truncated,
        "file_truncated": bool(cur.get("truncated")),
        "file_size": cur.get("size", 0),
        "mtime": mtime,
        "warning": warning,
        "lang": (change or {}).get("lang") or workspace.lang_of(path),
    }


def apply_change(change, expected_mtime=None):
    """
    نوشتن تغییر روی دیسک.

    فقط باید بعد از تأیید صریح کاربر صدا زده شود. پشتیبان‌گیری و
    تشخیص تعارض را workspace.write_file انجام می‌دهد.
    """
    path = (change or {}).get("path", "")
    content = (change or {}).get("new_content", "")
    if not path:
        return {"success": False, "error": "مسیر فایل مشخص نیست."}

    res = workspace.write_file(path, content, expected_mtime=expected_mtime)
    if res.get("success"):
        res["applied"] = True
    return res


def apply_batch(changes, mtimes=None):
    """
    اعمال چند تغییر پشت‌سرهم.

    اگر یکی شکست خورد، بقیه ادامه می‌یابند — ولی گزارش کامل برمی‌گردد
    تا کاربر بداند کدام اعمال شد و کدام نه. توقف در وسط، پروژه را در
    وضعیت نیمه‌کاره‌ای می‌گذاشت که بدتر است.
    """
    mtimes = mtimes or {}
    ok, failed = [], []

    for ch in (changes or []):
        p = ch.get("path", "")
        r = apply_change(ch, expected_mtime=mtimes.get(p))
        if r.get("success"):
            ok.append({"path": p, "backup": r.get("backup"),
                       "created": r.get("created", False)})
        else:
            failed.append({"path": p, "error": r.get("error", ""),
                           "conflict": r.get("conflict", False)})

    return {
        "success": not failed,
        "applied": ok,
        "failed": failed,
        "summary_fa": _batch_summary(ok, failed),
    }


def _batch_summary(ok, failed):
    if not ok and not failed:
        return "تغییری برای اعمال وجود نداشت."
    parts = []
    if ok:
        created = sum(1 for x in ok if x.get("created"))
        edited = len(ok) - created
        if edited:
            parts.append(f"{edited} فایل ویرایش شد")
        if created:
            parts.append(f"{created} فایل ساخته شد")
    if failed:
        parts.append(f"{len(failed)} مورد ناموفق")
    icon = "✅" if not failed else ("⚠️" if ok else "❌")
    return icon + " " + "، ".join(parts) + "."


def revert_change(path, backup_name):
    """بازگرداندن یک فایل از پشتیبان."""
    return workspace.restore_backup(backup_name, path)
