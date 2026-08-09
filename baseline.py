# -*- coding: utf-8 -*-
"""
خط پایه و تشخیص انحراف — «قبلاً که خوب بود، چه چیزی عوض شد؟»

مسئله‌ای که حل می‌کند
─────────────────────
تشخیص محلی (local_diagnosis) می‌گوید «۳۱ برنامهٔ استارتاپ داری» — اما
نمی‌داند این عدد همیشه ۳۱ بوده یا هفتهٔ پیش ۸ بوده است. تفاوت این دو
حالت همه‌چیز را عوض می‌کند:

    ۳۱ برنامه، همیشه همین بوده     → احتمالاً علت مشکل جدید نیست
    ۸ → ۳۱ در یک هفته              → این است علت کندی جدید

کاربر معمولاً می‌گوید «تا هفتهٔ پیش خوب بود». بدون خط پایه، AI فقط
وضعیت فعلی را می‌بیند و باید حدس بزند چه چیزی تغییر کرده.

نحوهٔ کار
─────────
۱. کاربر وقتی سیستم سالم است دکمهٔ «ثبت وضعیت سالم» را می‌زند
۲. همهٔ سنجه‌ها + امضای پیکربندی ذخیره می‌شود
۳. بعداً `compare_to_baseline()` تفاوت‌ها را نشان می‌دهد

اسنپ‌شات‌ها در همان دیتابیس SQLite پروژه ذخیره می‌شوند تا فایل
اضافه‌ای به کاربر تحمیل نشود.
"""

import json
import time

import database
import health_metrics

# چند خط پایه نگه داریم؟ قدیمی‌ترها خودکار حذف می‌شوند.
MAX_BASELINES = 10

# حداقل تغییر برای اینکه «انحراف» شمرده شود.
# از آستانهٔ نویز health_metrics استفاده می‌شود ولی برای مقایسهٔ
# بلندمدت کمی سخت‌گیرانه‌تر است — چون در طول هفته‌ها نوسان بیشتر است.
_DRIFT_MULTIPLIER = 1.5


SCHEMA = """
CREATE TABLE IF NOT EXISTS baselines (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    label       TEXT,
    note        TEXT,
    snapshot    TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_baseline_time ON baselines(created_at DESC);
"""


def _ensure_table():
    """جدول را در صورت نبود می‌سازد. هر بار فراخوانی امن است."""
    try:
        with database._WRITE_LOCK, database._conn() as c:
            c.executescript(SCHEMA)
        return True
    except Exception:
        return False


def save_baseline(label=None, note="", snap=None):
    """
    ثبت وضعیت فعلی به‌عنوان مرجع.

    snap=None یعنی همهٔ سنجه‌ها خوانده شوند — این کند است (~۱ دقیقه)
    ولی خط پایه باید کامل باشد وگرنه بعداً قابل مقایسه نیست.
    """
    _ensure_table()
    if snap is None:
        snap = health_metrics.snapshot()

    label = label or time.strftime("%Y/%m/%d %H:%M")
    now = time.time()

    try:
        with database._WRITE_LOCK, database._conn() as c:
            cur = c.execute(
                "INSERT INTO baselines (label, note, snapshot, created_at) "
                "VALUES (?,?,?,?)",
                (label, note, json.dumps(snap, ensure_ascii=False), now),
            )
            new_id = cur.lastrowid
            # نگه‌داشتن فقط N مورد آخر
            c.execute(
                "DELETE FROM baselines WHERE id NOT IN "
                "(SELECT id FROM baselines ORDER BY created_at DESC LIMIT ?)",
                (MAX_BASELINES,),
            )
        measured = sum(1 for m in snap.values() if m.get("value") is not None)
        return {
            "success": True,
            "id": new_id,
            "label": label,
            "created_at": now,
            "metrics_total": len(snap),
            "metrics_measured": measured,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_baselines():
    """فهرست خط پایه‌ها بدون خود اسنپ‌شات (سبک برای نمایش)."""
    _ensure_table()
    try:
        with database._conn() as c:
            rows = c.execute(
                "SELECT id, label, note, created_at, LENGTH(snapshot) "
                "FROM baselines ORDER BY created_at DESC"
            ).fetchall()
        return {
            "success": True,
            "baselines": [
                {
                    "id": r[0],
                    "label": r[1],
                    "note": r[2] or "",
                    "created_at": r[3],
                    "age_days": round((time.time() - r[3]) / 86400, 1),
                    "size": r[4],
                }
                for r in rows
            ],
        }
    except Exception as e:
        return {"success": False, "error": str(e), "baselines": []}


def get_baseline(baseline_id=None):
    """
    یک خط پایه با اسنپ‌شات کامل.
    baseline_id=None یعنی جدیدترین.
    """
    _ensure_table()
    try:
        with database._conn() as c:
            if baseline_id:
                row = c.execute(
                    "SELECT id,label,note,snapshot,created_at FROM baselines WHERE id=?",
                    (baseline_id,),
                ).fetchone()
            else:
                row = c.execute(
                    "SELECT id,label,note,snapshot,created_at FROM baselines "
                    "ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "label": row[1],
            "note": row[2] or "",
            "snapshot": json.loads(row[3]),
            "created_at": row[4],
        }
    except Exception:
        return None


def delete_baseline(baseline_id):
    _ensure_table()
    try:
        with database._WRITE_LOCK, database._conn() as c:
            c.execute("DELETE FROM baselines WHERE id=?", (baseline_id,))
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def compare_to_baseline(baseline_id=None, current=None):
    """
    مقایسهٔ وضعیت فعلی با خط پایه.

    برخلاف health_metrics.compare که برای «قبل و بعد از یک تعمیر»
    است، اینجا بازهٔ زمانی طولانی است. پس:
      • آستانه سخت‌گیرانه‌تر است (نوسان بلندمدت طبیعی است)
      • بازهٔ زمانی گزارش می‌شود
      • نتیجه به زبان «چه چیزی عوض شده» بیان می‌شود، نه «بهتر/بدتر»
    """
    base = get_baseline(baseline_id)
    if not base:
        return {
            "success": False,
            "error": "هیچ خط پایه‌ای ثبت نشده است. وقتی سیستم در وضعیت "
                     "خوبی است، دکمهٔ «ثبت وضعیت سالم» را بزنید.",
        }

    base_snap = base["snapshot"]
    if current is None:
        current = health_metrics.snapshot(list(base_snap.keys()))

    age_days = (time.time() - base["created_at"]) / 86400
    rows = []

    for key, b in base_snap.items():
        a = current.get(key, {})
        bv, av = b.get("value"), a.get("value")

        row = {
            "key": key,
            "label_fa": b.get("label_fa") or key,
            "unit": b.get("unit") or "",
            "baseline": bv,
            "current": av,
            "delta": None,
            "drift": "unknown",
        }

        if bv is None or av is None:
            rows.append(row)
            continue

        delta = av - bv
        row["delta"] = round(delta, 2)

        base_thr = health_metrics.NOISE_THRESHOLD.get(
            key, health_metrics._DEFAULT_NOISE)
        threshold = base_thr * _DRIFT_MULTIPLIER

        if abs(delta) < threshold:
            row["drift"] = "stable"
        else:
            higher_better = b.get("higher_is_better", True)
            better = (delta > 0) if higher_better else (delta < 0)
            row["drift"] = "better" if better else "worse"

        # درصد تغییر — برای فهم بزرگی انحراف
        if bv not in (0, None):
            row["pct"] = round(delta / abs(bv) * 100, 1)

        rows.append(row)

    worse = [r for r in rows if r["drift"] == "worse"]
    better = [r for r in rows if r["drift"] == "better"]
    stable = [r for r in rows if r["drift"] == "stable"]

    # بدترین انحراف‌ها اول
    worse.sort(key=lambda r: abs(r.get("pct") or 0), reverse=True)

    return {
        "success": True,
        "baseline_id": base["id"],
        "baseline_label": base["label"],
        "baseline_note": base["note"],
        "age_days": round(age_days, 1),
        "rows": rows,
        "worse": worse,
        "better": better,
        "stable_count": len(stable),
        "summary_fa": _drift_summary(worse, better, stable, age_days),
    }


def _drift_summary(worse, better, stable, age_days):
    when = (f"{age_days:.0f} روز" if age_days >= 1
            else f"{age_days * 24:.0f} ساعت")
    if not worse and not better:
        return f"➖ نسبت به {when} پیش، هیچ تغییر معناداری دیده نمی‌شود."
    parts = []
    if worse:
        parts.append(f"{len(worse)} سنجه بدتر شده")
    if better:
        parts.append(f"{len(better)} سنجه بهتر شده")
    icon = "⚠️" if worse else "✅"
    return f"{icon} نسبت به {when} پیش: " + "، ".join(parts) + "."


def format_for_ai(cmp_result):
    """
    تبدیل انحراف به متن فارسی برای AI.

    نکتهٔ مهم: به AI گفته می‌شود روی *تغییرات* تمرکز کند، نه روی
    مقادیر مطلق. اگر چیزی از ابتدا همین‌طور بوده، احتمالاً علت
    مشکل جدید نیست.
    """
    if not cmp_result or not cmp_result.get("success"):
        return ""

    lines = ["### مقایسه با وضعیت سالم ثبت‌شده", ""]
    lines.append(
        f"خط پایه: «{cmp_result['baseline_label']}» "
        f"({cmp_result['age_days']} روز پیش)"
    )
    if cmp_result.get("baseline_note"):
        lines.append(f"یادداشت کاربر: {cmp_result['baseline_note']}")
    lines.append("")
    lines.append(cmp_result.get("summary_fa", ""))
    lines.append("")

    worse = cmp_result.get("worse", [])
    if worse:
        lines.append("**سنجه‌هایی که بدتر شده‌اند (به ترتیب شدت):**")
        lines.append("")
        lines.append("| سنجه | آن زمان | اکنون | تغییر |")
        lines.append("|---|---|---|---|")
        for r in worse:
            pct = f" ({r['pct']:+g}٪)" if r.get("pct") is not None else ""
            lines.append(
                f"| {r['label_fa']} | {r['baseline']:g} {r['unit']} | "
                f"{r['current']:g} {r['unit']} | {r['delta']:+g}{pct} |"
            )
        lines.append("")

    better = cmp_result.get("better", [])
    if better:
        names = "، ".join(r["label_fa"] for r in better)
        lines.append(f"سنجه‌های بهبودیافته: {names}")
        lines.append("")

    lines.append(
        "**راهنما:** روی سنجه‌هایی که *تغییر کرده‌اند* تمرکز کن. "
        "مقادیری که از ابتدا همین‌طور بوده‌اند احتمالاً علت مشکل جدید "
        "نیستند. اگر کاربر می‌گوید «قبلاً خوب بود»، جواب در همین "
        "تفاوت‌هاست."
    )
    return "\n".join(lines)


def auto_baseline_if_healthy(diagnosis_result):
    """
    ثبت خودکار خط پایه وقتی تشخیص محلی هیچ مشکلی پیدا نکرده.

    منطق: اگر سیستم الان سالم است و خط پایه‌ای نداریم (یا آخری
    خیلی قدیمی است)، همین حالا بهترین زمان ثبت است. کاربر معمولاً
    یادش نمی‌ماند این کار را بکند.
    """
    if not diagnosis_result or not diagnosis_result.get("healthy"):
        return None

    existing = list_baselines().get("baselines", [])
    if existing and existing[0]["age_days"] < 7:
        return None        # خط پایهٔ تازه داریم

    snap = diagnosis_result.get("snapshot")
    return save_baseline(
        label=time.strftime("%Y/%m/%d") + " (خودکار)",
        note="به‌صورت خودکار ثبت شد چون بررسی محلی هیچ مشکلی پیدا نکرد.",
        snap=snap,
    )
