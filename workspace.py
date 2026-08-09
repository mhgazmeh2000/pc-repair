# -*- coding: utf-8 -*-
"""
مدیریت پوشهٔ پروژه — پایهٔ تب «توسعهٔ نرم‌افزار»

مسئولیت‌ها
──────────
۱. باز کردن یک پوشه روی سیستم به‌عنوان پروژهٔ فعال
۲. ساختن درخت فایل با احترام به .gitignore
۳. خواندن و نوشتن امن فایل‌ها

امنیت — چرا این ماژول محتاط است
────────────────────────────────
برنامه با دسترسی ادمین اجرا می‌شود. اگر مسیر فایل بدون اعتبارسنجی
پذیرفته شود، یک درخواست دستکاری‌شده می‌تواند `C:\\Windows\\System32\\...`
را بخواند یا بازنویسی کند.

سه سد:
  • هر مسیر با realpath حل و بررسی می‌شود که *داخل* ریشهٔ پروژه باشد
    (جلوی ../../ و symlink را می‌گیرد)
  • پوشه‌های سیستمی ویندوز اصلاً به‌عنوان پروژه پذیرفته نمی‌شوند
  • فایل‌های باینری و بزرگ رد می‌شوند

نکتهٔ طراحی: ریشهٔ پروژه در حافظه نگه داشته می‌شود، نه در درخواست.
یعنی کلاینت نمی‌تواند با هر درخواست ریشه را عوض کند.
"""

import fnmatch
import json
import os
import re
import time

# سقف‌ها — از تجربهٔ attachments.py الگو گرفته شده
LARGE_FILE_KB = 10240       # فایل بزرگ‌تر از ۱۰ مگابایت → پرچم «بزرگ» برای هشدار UI
SEARCH_SKIP_KB = 512        # در جست‌وجو، فایل بزرگ‌تر را رد کن (خواندنش کند است)
MAX_TREE_NODES = 4000       # درخت بزرگ‌تر مرورگر را کند می‌کند
MAX_DEPTH = 12
# سقف حجم هر فایل در زمینهٔ AI — یک فایل غول‌پیکر کل بودجه را نمی‌بلعد
CONTEXT_MAX_FILE_KB = 150
# سقف تعداد فایل‌هایی که پوشه‌ها می‌توانند در زمینه باز کنند
CONTEXT_MAX_FILES = 400

# پوشه‌هایی که هرگز نباید پیمایش شوند — حجیم و بی‌فایده‌اند
ALWAYS_SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".env", "dist", "build", "out", "target", ".next", ".nuxt",
    ".output", ".cache", ".parcel-cache", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".tox", ".nox", "coverage", ".idea", ".vscode",
    "vendor", "Pods", ".gradle", ".terraform", "bin", "obj",
}

# پسوندهای متنی که ویرایشگر می‌شناسد
TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".htm", ".css", ".scss",
    ".sass", ".less", ".json", ".jsonc", ".xml", ".yaml", ".yml", ".toml",
    ".ini", ".cfg", ".conf", ".md", ".markdown", ".txt", ".rst", ".log",
    ".sh", ".bash", ".zsh", ".ps1", ".psm1", ".bat", ".cmd",
    ".c", ".h", ".cpp", ".hpp", ".cc", ".cs", ".java", ".kt", ".kts",
    ".go", ".rs", ".rb", ".php", ".pl", ".lua", ".r", ".swift", ".m",
    ".sql", ".graphql", ".proto", ".vue", ".svelte", ".astro",
    ".gitignore", ".dockerignore", ".editorconfig", ".env.example",
    ".csv", ".tsv", ".properties", ".gradle", ".cmake", ".mk",
}

# نگاشت پسوند به زبان — برای هایلایت در ویرایشگر
LANG_MAP = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".html": "html",
    ".htm": "html", ".css": "css", ".scss": "scss", ".json": "json",
    ".xml": "xml", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".md": "markdown", ".sh": "bash", ".bash": "bash", ".ps1": "powershell",
    ".bat": "batch", ".cmd": "batch", ".c": "c", ".h": "c", ".cpp": "cpp",
    ".hpp": "cpp", ".cs": "csharp", ".java": "java", ".go": "go",
    ".rs": "rust", ".rb": "ruby", ".php": "php", ".sql": "sql",
    ".vue": "vue", ".svelte": "svelte", ".lua": "lua", ".kt": "kotlin",
}

# مسیرهایی که به‌عنوان ریشهٔ پروژه پذیرفته نمی‌شوند
_FORBIDDEN_ROOTS_WIN = [
    "c:\\windows", "c:\\program files", "c:\\program files (x86)",
    "c:\\programdata", "c:\\$recycle.bin", "c:\\system volume information",
]

# وضعیت ماژول — ریشهٔ پروژهٔ فعال
_STATE = {"root": None, "opened_at": None, "ignore_patterns": None}


# ═══════════════════════════ کمکی‌ها ═══════════════════════════

def _norm(p):
    """مسیر مطلق و حل‌شده (symlink باز می‌شود)."""
    return os.path.realpath(os.path.abspath(os.path.expanduser(p or "")))


_FORBIDDEN_ROOTS_NIX = (
    "/", "/etc", "/usr", "/bin", "/sbin", "/lib", "/boot",
    "/proc", "/sys", "/dev", "/var", "/root",
)


def _is_forbidden_root(path):
    """
    آیا این مسیر یک پوشهٔ سیستمی است؟

    هر دو سبک مسیر بررسی می‌شوند، نه فقط سبک سیستم‌عامل جاری.
    دلیل: نرمال‌سازی جداکننده‌ها بر اساس os.name باعث می‌شد روی
    لینوکس مسیر '/etc' به '\\etc' تبدیل شود و هیچ‌وقت با فهرست
    ممنوع تطبیق پیدا نکند — یعنی سد امنیتی بی‌صدا غیرفعال بود.
    """
    raw = (path or "").strip().rstrip("/\\").lower()
    if not raw:
        return True

    # ── سبک ویندوز ──
    win = raw.replace("/", "\\")
    # ریشهٔ درایو (C: یا C:\) — ایندکس کردن کل درایو فاجعه است
    if len(win) <= 3 and ":" in win:
        return True
    for f in _FORBIDDEN_ROOTS_WIN:
        if win == f or win.startswith(f + "\\"):
            return True

    # ── سبک یونیکس ──
    nix = "/" + raw.replace("\\", "/").lstrip("/")
    if nix in _FORBIDDEN_ROOTS_NIX:
        return True
    for f in _FORBIDDEN_ROOTS_NIX:
        if f != "/" and nix.startswith(f + "/"):
            return True

    return False


def _load_gitignore(root):
    """
    الگوهای .gitignore را می‌خواند.
    پیاده‌سازی سادهٔ fnmatch — نه کامل مثل git، ولی برای پنهان کردن
    فایل‌های ساخته‌شده کافی است.
    """
    patterns = []
    gi = os.path.join(root, ".gitignore")
    try:
        with open(gi, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("!"):        # الگوی نفی — پشتیبانی نمی‌شود
                    continue
                patterns.append(line.rstrip("/"))
    except Exception:
        pass
    return patterns


def _is_ignored(rel_path, name, patterns):
    """آیا این مسیر با یکی از الگوهای .gitignore می‌خواند؟"""
    if not patterns:
        return False
    rel = rel_path.replace("\\", "/")
    for pat in patterns:
        if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel, pat):
            return True
        if fnmatch.fnmatch(rel, pat + "/*") or rel.startswith(pat + "/"):
            return True
    return False


def is_text_file(name):
    ext = os.path.splitext(name)[1].lower()
    if ext in TEXT_EXTENSIONS:
        return True
    # فایل‌های بی‌پسوند رایج
    return name.lower() in {
        "makefile", "dockerfile", "license", "readme", "changelog",
        "procfile", "gemfile", "rakefile", "cargo.lock", ".gitignore",
    }


def lang_of(name):
    return LANG_MAP.get(os.path.splitext(name)[1].lower(), "text")


# ═══════════════════════ باز/بستن پروژه ═══════════════════════

def open_project(path):
    """باز کردن پوشه به‌عنوان پروژهٔ فعال."""
    if not path or not str(path).strip():
        return {"success": False, "error": "مسیری وارد نشده است."}

    root = _norm(path)

    if not os.path.exists(root):
        return {"success": False, "error": f"مسیر وجود ندارد:\n{root}"}
    if not os.path.isdir(root):
        return {"success": False, "error": "مسیر باید یک پوشه باشد، نه فایل."}
    if _is_forbidden_root(root):
        return {"success": False,
                "error": "این پوشه سیستمی است و به‌عنوان پروژه باز نمی‌شود.\n"
                         "یک پوشهٔ پروژهٔ معمولی انتخاب کنید."}
    if not os.access(root, os.R_OK):
        return {"success": False, "error": "اجازهٔ خواندن این پوشه را ندارید."}

    _STATE["root"] = root
    _STATE["opened_at"] = time.time()
    _STATE["ignore_patterns"] = _load_gitignore(root)

    tree = build_tree(root)
    return {
        "success": True,
        "root": root,
        "name": os.path.basename(root) or root,
        "writable": os.access(root, os.W_OK),
        "has_git": os.path.isdir(os.path.join(root, ".git")),
        "gitignore_rules": len(_STATE["ignore_patterns"] or []),
        **tree,
    }


def close_project():
    _STATE["root"] = None
    _STATE["opened_at"] = None
    _STATE["ignore_patterns"] = None
    return {"success": True}


def current_root():
    return _STATE["root"]


def project_info():
    root = _STATE["root"]
    if not root:
        return {"success": False, "error": "پروژه‌ای باز نشده است."}
    return {
        "success": True,
        "root": root,
        "name": os.path.basename(root) or root,
        "opened_at": _STATE["opened_at"],
        "writable": os.access(root, os.W_OK),
        "has_git": os.path.isdir(os.path.join(root, ".git")),
    }


# ═══════════════════════════ درخت ═══════════════════════════

def build_tree(root=None, max_nodes=MAX_TREE_NODES):
    """
    ساخت درخت فایل به‌صورت لیست تخت (parent-based).
    لیست تخت از درخت تودرتو سبک‌تر است و رندر آن در JS ساده‌تر.
    """
    root = root or _STATE["root"]
    if not root:
        return {"success": False, "error": "پروژه‌ای باز نشده است.", "nodes": []}

    patterns = _STATE.get("ignore_patterns") or []
    nodes = []
    truncated = False
    files = dirs = 0

    def walk(cur, rel, depth):
        nonlocal truncated, files, dirs
        if truncated or depth > MAX_DEPTH:
            return
        try:
            entries = sorted(
                os.scandir(cur),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except (PermissionError, OSError):
            return

        for e in entries:
            if len(nodes) >= max_nodes:
                truncated = True
                return
            name = e.name
            child_rel = f"{rel}/{name}" if rel else name

            try:
                is_dir = e.is_dir(follow_symlinks=False)
            except OSError:
                continue

            if is_dir:
                if name in ALWAYS_SKIP_DIRS or name.startswith("."):
                    # پوشه‌های نقطه‌دار پنهان‌اند مگر شناخته‌شده باشند
                    if name not in (".github", ".vscode"):
                        continue
                if _is_ignored(child_rel, name, patterns):
                    continue
                dirs += 1
                nodes.append({
                    "path": child_rel, "name": name, "dir": True,
                    "parent": rel, "depth": depth,
                })
                walk(e.path, child_rel, depth + 1)
            else:
                if _is_ignored(child_rel, name, patterns):
                    continue
                try:
                    size = e.stat().st_size
                except OSError:
                    size = 0
                files += 1
                nodes.append({
                    "path": child_rel, "name": name, "dir": False,
                    "parent": rel, "depth": depth, "size": size,
                    "text": is_text_file(name), "lang": lang_of(name),
                })

    walk(root, "", 0)
    return {
        "success": True, "nodes": nodes, "truncated": truncated,
        "file_count": files, "dir_count": dirs,
    }


# ═══════════════════════ خواندن و نوشتن ═══════════════════════

def _resolve(rel_path):
    """
    تبدیل مسیر نسبی به مطلق، با تضمین اینکه داخل ریشه بماند.
    برگشت (abs_path, error).
    """
    root = _STATE["root"]
    if not root:
        return None, "پروژه‌ای باز نشده است."
    if not rel_path or not str(rel_path).strip():
        return None, "مسیر فایل مشخص نشده است."

    raw = str(rel_path).replace("\\", "/")

    # مسیر مطلق را نمی‌پذیریم. lstrip("/") آن را به مسیر نسبیِ داخل
    # پروژه تبدیل می‌کرد — امن بود ولی گمراه‌کننده: کاربر فکر می‌کرد
    # /etc/hosts را می‌نویسد و در واقع <ریشه>/etc/hosts ساخته می‌شد.
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        return None, ("مسیر باید نسبت به پوشهٔ پروژه باشد، نه مطلق.\n"
                      f"دریافت شد: {raw}")

    rel = raw.lstrip("/")
    target = _norm(os.path.join(root, rel))

    # مقایسه با جداکنندهٔ انتهایی تا /project-evil با /project اشتباه نشود
    root_cmp = root if root.endswith(os.sep) else root + os.sep
    if target != root and not target.startswith(root_cmp):
        return None, "دسترسی خارج از پوشهٔ پروژه مجاز نیست."
    return target, None


def read_file(rel_path, max_kb=None):
    """خواندن فایل برای ویرایشگر.

    max_kb: اگر داده شود و فایل بزرگ‌تر باشد، فقط ابتدای فایل خوانده می‌شود
    (پیش‌نمایش امن) و پرچم truncated برمی‌گردد — چون یک فایل ۵۰ مگابایتی
    داخل textarea مرورگر را قفل می‌کند. خودِ بلاکِ «بزرگ‌تر از X باز نشود»
    حذف شده: بدون max_kb هر فایلی کامل خوانده می‌شود.
    """
    target, err = _resolve(rel_path)
    if err:
        return {"success": False, "error": err}
    if not os.path.exists(target):
        return {"success": False, "error": "فایل وجود ندارد."}
    if os.path.isdir(target):
        return {"success": False, "error": "این یک پوشه است، نه فایل."}

    try:
        size = os.path.getsize(target)
    except OSError as e:
        return {"success": False, "error": str(e)}

    is_large = size > LARGE_FILE_KB * 1024
    truncated = False
    read_bytes = size
    if max_kb and size > max_kb * 1024:
        read_bytes = max_kb * 1024
        truncated = True

    name = os.path.basename(target)
    if not is_text_file(name):
        # بررسی محتوا: بایت صفر یعنی باینری
        try:
            with open(target, "rb") as f:
                if b"\x00" in f.read(8192):
                    return {"success": False,
                            "error": "فایل باینری است و در ویرایشگر باز نمی‌شود."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    try:
        with open(target, "rb") as f:
            raw = f.read(read_bytes)
        content = raw.decode("utf-8", errors="replace")
        if truncated:
            # به انتهای آخرین خط کامل برس تا متن نصفه نماند
            cut = content.rfind("\n")
            if cut > 0:
                content = content[:cut]
    except Exception as e:
        return {"success": False, "error": f"خواندن ناموفق: {e}"}

    return {
        "success": True,
        "path": str(rel_path).replace("\\", "/").lstrip("/"),
        "name": name,
        "content": content,
        "size": size,
        "large": is_large,
        "truncated": truncated,
        "lines": content.count("\n") + 1,
        "lang": lang_of(name),
        "mtime": os.path.getmtime(target),
        "writable": os.access(target, os.W_OK),
    }


def write_file(rel_path, content, expected_mtime=None):
    """
    نوشتن فایل با پشتیبان خودکار.

    expected_mtime: اگر داده شود و فایل بیرون از برنامه تغییر کرده
    باشد، نوشتن رد می‌شود — جلوی از دست رفتن تغییرات را می‌گیرد.
    """
    target, err = _resolve(rel_path)
    if err:
        return {"success": False, "error": err}
    if os.path.isdir(target):
        return {"success": False, "error": "این یک پوشه است."}

    existed = os.path.exists(target)

    if existed and expected_mtime is not None:
        try:
            actual = os.path.getmtime(target)
            if abs(actual - float(expected_mtime)) > 1.0:
                return {
                    "success": False, "conflict": True,
                    "error": "فایل بیرون از برنامه تغییر کرده است. "
                             "دوباره بازش کنید تا نسخهٔ جدید را ببینید.",
                }
        except OSError:
            pass

    backup = None
    if existed:
        backup = _make_backup(target)

    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="") as f:
            f.write(content or "")
    except Exception as e:
        return {"success": False, "error": f"نوشتن ناموفق: {e}"}

    return {
        "success": True,
        "path": str(rel_path).replace("\\", "/").lstrip("/"),
        "size": len(content or ""),
        "mtime": os.path.getmtime(target),
        "backup": backup,
        "created": not existed,
    }


def _backup_dir():
    root = _STATE["root"] or ""
    d = os.path.join(root, ".pcrepair_backups")
    try:
        os.makedirs(d, exist_ok=True)
        # این پوشه نباید در گیت برود
        gi = os.path.join(d, ".gitignore")
        if not os.path.exists(gi):
            with open(gi, "w", encoding="utf-8") as f:
                f.write("*\n")
    except Exception:
        return None
    return d


def _make_backup(target):
    """
    کپی فایل قبل از بازنویسی. برگشت نام فایل پشتیبان یا None.

    نام شامل شمارنده است، نه فقط زمان: دو ذخیرهٔ پیاپی در یک ثانیه
    نام یکسان می‌گرفتند و پشتیبان قبلی را بازنویسی می‌کردند —
    یعنی نسخهٔ اصلی بی‌صدا از دست می‌رفت.
    """
    d = _backup_dir()
    if not d:
        return None
    try:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        base = os.path.basename(target)
        name = f"{stamp}_{base}"
        dest = os.path.join(d, name)
        n = 1
        while os.path.exists(dest):
            name = f"{stamp}_{n:02d}_{base}"
            dest = os.path.join(d, name)
            n += 1
            if n > 99:
                break
        with open(target, "rb") as src, open(dest, "wb") as out:
            out.write(src.read())
        _prune_backups(d)
        return name
    except Exception:
        return None


def _prune_backups(d, keep=50):
    """
    نگه‌داشتن N پشتیبان آخر.
    مرتب‌سازی بر اساس (mtime، نام): در یک ثانیه mtime یکسان است و
    تکیه بر آن ترتیب را غیرقطعی می‌کرد.
    """
    try:
        items = []
        for f in os.listdir(d):
            if f == ".gitignore":
                continue
            try:
                items.append((os.path.getmtime(os.path.join(d, f)), f))
            except OSError:
                continue
        items.sort(key=lambda x: (x[0], x[1]), reverse=True)
        for _, f in items[keep:]:
            try:
                os.remove(os.path.join(d, f))
            except OSError:
                pass
    except Exception:
        pass


def list_backups():
    d = _backup_dir()
    if not d or not os.path.isdir(d):
        return {"success": True, "backups": []}
    out = []
    try:
        for f in os.listdir(d):
            if f == ".gitignore":
                continue
            p = os.path.join(d, f)
            out.append({"name": f, "size": os.path.getsize(p),
                        "mtime": os.path.getmtime(p)})
        out.sort(key=lambda x: x["mtime"], reverse=True)
    except Exception:
        pass
    return {"success": True, "backups": out}


def restore_backup(backup_name, rel_path):
    """بازگرداندن یک پشتیبان روی فایل اصلی."""
    d = _backup_dir()
    if not d:
        return {"success": False, "error": "پوشهٔ پشتیبان در دسترس نیست."}
    src = os.path.join(d, os.path.basename(backup_name or ""))
    if not os.path.exists(src):
        return {"success": False, "error": "فایل پشتیبان یافت نشد."}
    target, err = _resolve(rel_path)
    if err:
        return {"success": False, "error": err}
    try:
        if os.path.exists(target):
            _make_backup(target)      # از وضعیت فعلی هم پشتیبان بگیر
        with open(src, "rb") as s, open(target, "wb") as t:
            t.write(s.read())
        return {"success": True, "path": rel_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════ جست‌وجو ═══════════════════════════

def search_in_files(query, max_results=80, case_sensitive=False):
    """جست‌وجوی متنی ساده در فایل‌های پروژه."""
    root = _STATE["root"]
    if not root:
        return {"success": False, "error": "پروژه‌ای باز نشده است.", "hits": []}
    if not query or len(query) < 2:
        return {"success": False, "error": "عبارت جست‌وجو خیلی کوتاه است.", "hits": []}

    needle = query if case_sensitive else query.lower()
    tree = build_tree(root)
    hits = []

    for n in tree.get("nodes", []):
        if n["dir"] or not n.get("text"):
            continue
        if n.get("size", 0) > SEARCH_SKIP_KB * 1024:
            continue
        target, err = _resolve(n["path"])
        if err:
            continue
        try:
            with open(target, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    hay = line if case_sensitive else line.lower()
                    if needle in hay:
                        hits.append({
                            "path": n["path"], "line": i,
                            "text": line.strip()[:200],
                        })
                        if len(hits) >= max_results:
                            return {"success": True, "hits": hits,
                                    "truncated": True, "query": query}
        except Exception:
            continue

    return {"success": True, "hits": hits, "truncated": False, "query": query}


# ═══════════════════ زمینه برای هوش مصنوعی ═══════════════════

def _walk_folder_context(cur, rel, depth, patterns, out, skipped, max_file_bytes):
    """پیمایش یک پوشه و جمع‌آوری فایل‌های متنی — مثل build_tree ولی برای زمینهٔ AI."""
    if depth > MAX_DEPTH:
        return
    try:
        entries = sorted(
            os.scandir(cur),
            key=lambda e: (not e.is_dir(), e.name.lower()),
        )
    except (PermissionError, OSError):
        return

    for e in entries:
        name = e.name
        child_rel = f"{rel}/{name}" if rel else name
        try:
            is_dir = e.is_dir(follow_symlinks=False)
        except OSError:
            continue
        if is_dir:
            if name in ALWAYS_SKIP_DIRS or name.startswith("."):
                if name not in (".github", ".vscode"):
                    continue
            if _is_ignored(child_rel, name, patterns):
                continue
            _walk_folder_context(e.path, child_rel, depth + 1, patterns,
                                 out, skipped, max_file_bytes)
        else:
            if _is_ignored(child_rel, name, patterns):
                continue
            if not is_text_file(name):
                continue
            try:
                size = e.stat().st_size
            except OSError:
                size = 0
            if size > max_file_bytes:
                skipped.append({"path": child_rel,
                                "reason": "فایل بزرگ‌تر از سقف زمینه است"})
                continue
            out.append((child_rel, size))


def build_context(paths, max_chars=60000):
    """
    ساخت بلوک متنی از فایل‌ها/پوشه‌ها برای فرستادن به AI.

    پوشه‌ها باز می‌شوند: فایل‌های متنی داخل‌شان با احترام به .gitignore
    جمع می‌شوند و کوچک‌ترین‌ها اول می‌آیند تا سقف کاراکتر بیشترین پوشش
    را بدهد. فایل‌های بزرگ‌تر از سقف، باینری، یا خارج از بودجه در
    skipped با دلیل می‌آیند تا کاربر بداند چه چیزی نرفته است.

    سقف کاراکتر مهم است: مدل‌های رایگان پنجرهٔ کوچکی دارند و فرستادن
    کل پروژهٔ بزرگ یعنی خطای «context too long».
    """
    root = _STATE["root"]
    if not root:
        return {"success": False, "error": "پروژه‌ای باز نشده است."}

    blocks, included, skipped = [], [], []
    folder_meta = {}      # مسیر پوشه → {name, total}
    targets = []          # (مسیر نسبی فایل, اندازه)
    total = 0
    max_file_bytes = CONTEXT_MAX_FILE_KB * 1024

    for p in (paths or [])[:50]:
        p = str(p)
        target, err = _resolve(p)
        if err:
            skipped.append({"path": p, "reason": err})
            continue
        if os.path.isdir(target):
            # پوشه‌های همیشه‌ردشده (node_modules، .git و…) حتی اگر مستقیماً
            # ضمیمه شوند هم نادیده گرفته می‌شوند — با درخت فایل هماهنگ.
            # (مثل خود پیمایش: .github و .vscode استثنا هستند؛ و «.» یعنی کل
            # پروژه است — حتی اگر نامش dist یا build باشد، همیشه باز می‌شود.)
            base = os.path.basename(target.rstrip(os.sep))
            skip_root = (base in ALWAYS_SKIP_DIRS or base.startswith(".")) \
                and base not in (".github", ".vscode") and p != "."
            if skip_root:
                skipped.append({"path": p,
                                "reason": "پوشهٔ نادیده‌گرفته‌شده (node_modules، مخفی و…)"})
                continue
            out = []
            # مسیر فایل‌ها باید نسبت به ریشهٔ پروژه باشد؛ برای «.» (کل پروژه)
            # با پیشوند خالی تا نام‌ها تمیز بمانند
            walk_rel = "" if p == "." else p
            _walk_folder_context(target, walk_rel, 0,
                                 _STATE.get("ignore_patterns") or [],
                                 out, skipped, max_file_bytes)
            # نام نمایشی: برای «.» کل پروژه، وگرنه نام پوشه
            if p == ".":
                name = os.path.basename(root)
            else:
                name = os.path.basename(target.rstrip(os.sep))
            folder_meta[p] = {"name": name, "total": len(out)}
            targets.extend(out)
        elif os.path.isfile(target):
            try:
                size = os.path.getsize(target)
            except OSError:
                size = 0
            targets.append((p, size))
        else:
            skipped.append({"path": p, "reason": "وجود ندارد."})

    # پوشه‌های هم‌پوشان (مثلاً «.» با «src») نباید فایلی را دوبار بفرستند
    seen = set()
    uniq = []
    for rel_path, size in targets:
        if rel_path in seen:
            continue
        seen.add(rel_path)
        uniq.append((rel_path, size))
    targets = uniq

    # کوچک‌ترین‌ها اول، تا بودجه بیشترین تعداد فایل را پوشش دهد
    targets.sort(key=lambda t: t[1])

    for rel_path, _size in targets:
        if len(included) >= CONTEXT_MAX_FILES:
            skipped.append({"path": rel_path,
                            "reason": "سقف تعداد فایل‌های زمینه"})
            continue
        r = read_file(rel_path)
        if not r.get("success"):
            skipped.append({"path": rel_path, "reason": r.get("error", "")})
            continue
        content = r["content"]
        header = f"### فایل: {r['path']}  ({r['lines']} خط)\n"
        block = f"{header}```{r['lang']}\n{content}\n```"
        if total + len(block) > max_chars:
            skipped.append({"path": rel_path, "reason": "به سقف حجم زمینه رسیدیم"})
            continue
        blocks.append(block)
        included.append(r["path"])
        total += len(block)

    # آمار هر پوشه برای نمایش در UI — «.» کل پروژه است، پس همهٔ فایل‌ها
    # در هر پوشهٔ هم‌پوشان با او شمرده می‌شوند؛ برای زیرپوشه‌ها فقط فایل‌های
    # زیر همان پیشوند.
    folders = []
    for fpath, meta in folder_meta.items():
        if fpath == ".":
            cnt = len(included)
        else:
            prefix = fpath.rstrip("/") + "/"
            cnt = sum(1 for inc in included if inc.startswith(prefix))
        folders.append({"path": fpath, "name": meta["name"],
                        "files": cnt, "total": meta["total"]})

    return {
        "success": True,
        "text": "\n\n".join(blocks),
        "included": included,
        "skipped": skipped,
        "folders": folders,
        "chars": total,
    }


def project_summary():
    """
    خلاصهٔ ساختار پروژه برای AI — بدون محتوای فایل‌ها.
    به مدل کمک می‌کند بفهمد با چه نوع پروژه‌ای طرف است.
    """
    root = _STATE["root"]
    if not root:
        return ""

    tree = build_tree(root)
    nodes = tree.get("nodes", [])
    exts = {}
    for n in nodes:
        if n["dir"]:
            continue
        e = os.path.splitext(n["name"])[1].lower() or "(بدون پسوند)"
        exts[e] = exts.get(e, 0) + 1

    top = sorted(exts.items(), key=lambda x: -x[1])[:8]
    top_dirs = [n["name"] for n in nodes if n["dir"] and n["depth"] == 0][:15]
    root_files = [n["name"] for n in nodes if not n["dir"] and n["depth"] == 0][:20]

    lines = [
        f"نام پروژه: {os.path.basename(root)}",
        f"تعداد فایل: {tree.get('file_count', 0)} · پوشه: {tree.get('dir_count', 0)}",
    ]
    if top:
        lines.append("پسوندهای غالب: "
                     + "، ".join(f"{e} ({c})" for e, c in top))
    if top_dirs:
        lines.append("پوشه‌های سطح اول: " + "، ".join(top_dirs))
    if root_files:
        lines.append("فایل‌های ریشه: " + "، ".join(root_files))
    return "\n".join(lines)
