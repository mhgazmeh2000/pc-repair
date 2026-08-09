# -*- coding: utf-8 -*-
"""
حافظهٔ بین‌جلسه‌ای — «دفعهٔ قبل چه کردیم و نتیجه چه شد؟»

مسئله‌ای که حل می‌کند
─────────────────────
جدول `jobs` تاریخچهٔ اجراها را دارد و `verify_fix` نتیجهٔ سنجش را
ثبت می‌کند — ولی AI هیچ‌کدام را نمی‌بیند. نتیجه:

    کاربر: «هنوز کنده»
    AI:    «SFC را اجرا کنید»          ← همان چیزی که دیروز جواب نداد

با این ماژول:

    AI می‌بیند: SFC دو بار اجرا شده، هر دو بار sfc_corrupt=1 ماند
    AI می‌گوید: «SFC دو بار امتحان شد و فساد برطرف نشد. این یعنی
                منبع سالم در دسترس نیست — باید از ISO استفاده کنیم.»

نکتهٔ طراحی
───────────
فقط چیزهایی به AI داده می‌شود که *تصمیم‌ساز* باشند: چه اجرا شد،
چند بار، و آیا سنجه‌ها بهبود یافتند. خروجی خام دستورها اینجا نمی‌آید
چون هم حجیم است و هم در `analyze_job_output` جداگانه فرستاده می‌شود.
"""

import json
import re
import time

import database

# چند اجرای اخیر در زمینه بیاید. بیشتر از این، توکن هدر می‌رود.
MAX_JOBS_IN_CONTEXT = 8

# اجرای قدیمی‌تر از این، دیگر به مشکل امروز ربط ندارد
MAX_AGE_DAYS = 30

SCHEMA = """
CREATE TABLE IF NOT EXISTS repair_outcomes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      TEXT,
    steps       TEXT,
    verdict     TEXT,
    improved    INTEGER DEFAULT 0,
    worsened    INTEGER DEFAULT 0,
    unchanged   INTEGER DEFAULT 0,
    detail      TEXT,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outcome_time
    ON repair_outcomes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outcome_job
    ON repair_outcomes(job_id);
"""

_VERDICT_FA = {
    "resolved":  "مؤثر بود",
    "partial":   "تا حدی مؤثر",
    "regressed": "وضعیت بدتر شد",
    "no_change": "هیچ تغییری نداد",
    "unknown":   "نتیجه نامشخص",
}


def _ensure_table():
    try:
        with database._WRITE_LOCK, database._conn() as c:
            c.executescript(SCHEMA)
        return True
    except Exception:
        return False


def record_outcome(job_id, steps, comparison):
    """
    ثبت نتیجهٔ سنجش یک تعمیر.
    از `/api/verify_fix` صدا زده می‌شود.
    """
    _ensure_table()
    cmp_ = comparison or {}

    # فقط سنجه‌هایی که واقعاً تغییر کردند ذخیره می‌شوند
    detail = []
    for r in cmp_.get("rows", []):
        if r.get("status") in ("improved", "worsened"):
            detail.append({
                "key": r.get("key"),
                "label": r.get("label_fa"),
                "before": r.get("before"),
                "after": r.get("after"),
                "status": r.get("status"),
            })

    try:
        with database._WRITE_LOCK, database._conn() as c:
            c.execute(
                "INSERT INTO repair_outcomes "
                "(job_id, steps, verdict, improved, worsened, unchanged, "
                " detail, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (job_id,
                 json.dumps(steps or [], ensure_ascii=False),
                 cmp_.get("verdict", "unknown"),
                 int(cmp_.get("improved", 0)),
                 int(cmp_.get("worsened", 0)),
                 int(cmp_.get("unchanged", 0)),
                 json.dumps(detail, ensure_ascii=False),
                 time.time()),
            )
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def recent_outcomes(limit=MAX_JOBS_IN_CONTEXT, max_age_days=MAX_AGE_DAYS):
    """نتایج تعمیرهای اخیر، جدیدترین اول."""
    _ensure_table()
    cutoff = time.time() - max_age_days * 86400
    try:
        with database._conn() as c:
            rows = c.execute(
                "SELECT job_id, steps, verdict, improved, worsened, "
                "unchanged, detail, created_at FROM repair_outcomes "
                "WHERE created_at > ? ORDER BY created_at DESC LIMIT ?",
                (cutoff, limit),
            ).fetchall()
    except Exception:
        return []

    out = []
    for r in rows:
        try:
            steps = json.loads(r[1] or "[]")
        except Exception:
            steps = []
        try:
            detail = json.loads(r[6] or "[]")
        except Exception:
            detail = []
        out.append({
            "job_id": r[0], "steps": steps, "verdict": r[2],
            "improved": r[3], "worsened": r[4], "unchanged": r[5],
            "detail": detail, "created_at": r[7],
            "age_days": round((time.time() - r[7]) / 86400, 1),
        })
    return out


def step_effectiveness():
    """
    آمار تجمعی هر مرحله: چند بار اجرا شد و چند بار مؤثر بود.

    این همان چیزی است که به AI اجازه می‌دهد بگوید «SFC دو بار
    امتحان شد و جواب نداد» به‌جای اینکه سومین بار پیشنهادش کند.
    """
    stats = {}
    for o in recent_outcomes(limit=60, max_age_days=90):
        eff = o["verdict"] in ("resolved", "partial")
        for s in o["steps"]:
            st = stats.setdefault(s, {"runs": 0, "effective": 0,
                                      "last_verdict": "", "last_days": None})
            st["runs"] += 1
            if eff:
                st["effective"] += 1
            if st["last_days"] is None:
                st["last_verdict"] = o["verdict"]
                st["last_days"] = o["age_days"]
    return stats


def ineffective_steps(min_runs=2):
    """
    مراحلی که چند بار اجرا شدند و هیچ‌وقت مؤثر نبودند.
    اینها را نباید دوباره پیشنهاد داد.
    """
    out = []
    for key, st in step_effectiveness().items():
        if st["runs"] >= min_runs and st["effective"] == 0:
            out.append({"step": key, "runs": st["runs"],
                        "last_days": st["last_days"]})
    out.sort(key=lambda x: -x["runs"])
    return out


def build_context(max_items=MAX_JOBS_IN_CONTEXT):
    """
    ساخت متن فارسی از تاریخچه برای زمینهٔ AI.
    رشتهٔ خالی یعنی تاریخچه‌ای نیست که ارزش فرستادن داشته باشد.
    """
    outcomes = recent_outcomes(limit=max_items)
    if not outcomes:
        return ""

    lines = ["### تاریخچهٔ تعمیرهای قبلی این سیستم", ""]

    try:
        import repair_runner
        titles = {k: v.get("title_fa", k)
                  for k, v in repair_runner.REPAIR_STEPS.items()}
    except Exception:
        titles = {}

    for o in outcomes:
        when = (f"{o['age_days']:.0f} روز پیش" if o["age_days"] >= 1
                else f"{o['age_days'] * 24:.0f} ساعت پیش")
        names = "، ".join(titles.get(s, s) for s in o["steps"]) or "(نامشخص)"
        verdict = _VERDICT_FA.get(o["verdict"], o["verdict"])
        lines.append(f"- **{when}**: {names} → {verdict}")

        # فقط دو سنجهٔ شاخص، وگرنه متن طولانی می‌شود
        for d in o["detail"][:2]:
            arrow = "بهبود" if d["status"] == "improved" else "افت"
            lines.append(f"    - {d['label']}: {d['before']} → {d['after']} ({arrow})")

    bad = ineffective_steps()
    if bad:
        lines.append("")
        lines.append("**مراحلی که امتحان شدند و جواب ندادند:**")
        for b in bad:
            name = titles.get(b["step"], b["step"])
            lines.append(f"- {name} — {b['runs']} بار اجرا شد، هیچ‌بار مؤثر نبود")
        lines.append("")
        lines.append(
            "این مراحل را دوباره پیشنهاد نده مگر دلیل تازه‌ای داشته باشی. "
            "اگر چیزی چند بار جواب نداده، یعنی علت جای دیگری است."
        )

    lines.append("")
    lines.append(
        "**راهنما:** از این تاریخچه استفاده کن تا کار تکراری پیشنهاد ندهی. "
        "اگر کاربر می‌گوید مشکل ادامه دارد، به این نگاه کن که چه چیزی "
        "قبلاً امتحان شده و نتیجه‌اش چه بوده."
    )
    return "\n".join(lines)


def summary():
    """خلاصهٔ آماری برای نمایش در رابط کاربری."""
    outcomes = recent_outcomes(limit=60, max_age_days=90)
    if not outcomes:
        # همان کلیدها برمی‌گردند، فقط خالی — وگرنه رابط کاربری که
        # روی وجودشان حساب می‌کند به خطا می‌خورد
        return {"total": 0, "resolved": 0, "no_change": 0, "regressed": 0,
                "ineffective_steps": [], "outcomes": [],
                "summary_fa": "هنوز تعمیری با سنجش نتیجه ثبت نشده است."}

    counts = {}
    for o in outcomes:
        counts[o["verdict"]] = counts.get(o["verdict"], 0) + 1

    total = len(outcomes)
    resolved = counts.get("resolved", 0) + counts.get("partial", 0)
    parts = [f"{total} تعمیر ثبت‌شده"]
    if resolved:
        parts.append(f"{resolved} مؤثر")
    if counts.get("no_change"):
        parts.append(f"{counts['no_change']} بی‌اثر")
    if counts.get("regressed"):
        parts.append(f"{counts['regressed']} با عارضه")

    return {
        "total": total,
        "resolved": resolved,
        "no_change": counts.get("no_change", 0),
        "regressed": counts.get("regressed", 0),
        "ineffective_steps": ineffective_steps(),
        "outcomes": outcomes[:MAX_JOBS_IN_CONTEXT],
        "summary_fa": "📚 " + "، ".join(parts) + ".",
    }


def clear_history():
    _ensure_table()
    try:
        with database._WRITE_LOCK, database._conn() as c:
            c.execute("DELETE FROM repair_outcomes")
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
