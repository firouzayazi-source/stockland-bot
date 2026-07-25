"""لایهٔ دیتابیس کارشناسی آیفون — جدول‌ها + CRUD خام.

الگوی مهاجرت این پروژه رعایت شده: CREATE TABLE IF NOT EXISTS برای جدول تازه،
به‌علاوه ALTER TABLE در try/except برای ستون‌های بعدی (اگه لازم شد)، پشت یک
فلگ ماژول‌سطح تا هر درخواست دوباره تلاش نکنه.
"""
import json
import time as _time

_SCHEMA_DONE = False


def _conn():
    from db import _get_connection
    return _get_connection()


def ensure_schema():
    global _SCHEMA_DONE
    if _SCHEMA_DONE:
        return
    conn = _conn()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            series TEXT DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );""")
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_capacities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER NOT NULL,
            capacity_label TEXT NOT NULL,
            base_price INTEGER NOT NULL DEFAULT 0,
            buy_price_ref INTEGER NOT NULL DEFAULT 0,
            sell_price_ref INTEGER NOT NULL DEFAULT 0,
            fx_ref_rate INTEGER NOT NULL DEFAULT 0,
            demand_percent REAL NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );""")
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_coefficients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            option_key TEXT NOT NULL,
            option_label TEXT NOT NULL,
            percent REAL NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1
        );""")
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_score_weights (
            category TEXT PRIMARY KEY,
            weight REAL NOT NULL DEFAULT 0
        );""")
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_fx_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            json_path TEXT NOT NULL DEFAULT 'price',
            priority INTEGER NOT NULL DEFAULT 1,
            active INTEGER NOT NULL DEFAULT 1,
            last_value INTEGER,
            last_fetched_at TEXT,
            last_error TEXT
        );""")
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER NOT NULL,
            capacity_id INTEGER NOT NULL,
            condition_note TEXT DEFAULT '',
            buy_price INTEGER NOT NULL DEFAULT 0,
            sell_price INTEGER NOT NULL DEFAULT 0,
            sold_at TEXT,
            days_to_sell INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );""")
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_valuations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            model_id INTEGER,
            capacity_id INTEGER,
            color TEXT DEFAULT '',
            part_number TEXT DEFAULT '',
            sim_type TEXT DEFAULT '',
            input_json TEXT DEFAULT '{}',
            market_price INTEGER NOT NULL DEFAULT 0,
            fair_price INTEGER NOT NULL DEFAULT 0,
            buy_price INTEGER NOT NULL DEFAULT 0,
            sell_price INTEGER NOT NULL DEFAULT 0,
            score INTEGER NOT NULL DEFAULT 0,
            verdict TEXT DEFAULT '',
            report_text TEXT DEFAULT '',
            seller_price INTEGER,
            city TEXT DEFAULT '',
            seller_type TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );""")
        conn.commit()

        # سیدِ پیش‌فرض ضرایب امتیازدهی — فقط اگه جدول خالیه (اولین اجرا)
        row = conn.execute("SELECT COUNT(*) c FROM iv_score_weights;").fetchone()
        if row and row["c"] == 0:
            defaults = [
                ("battery", 20), ("repair", 25), ("registry", 15),
                ("box", 10), ("cosmetic", 20), ("cable", 5), ("features", 5),
            ]
            for cat, w in defaults:
                conn.execute("INSERT INTO iv_score_weights (category, weight) VALUES (?,?);", (cat, w))
            conn.commit()

        # سیدِ پیش‌فرض ضرایب قیمت — فقط اگه جدول خالیه
        row = conn.execute("SELECT COUNT(*) c FROM iv_coefficients;").fetchone()
        if row and row["c"] == 0:
            defaults = [
                ("battery", "batt_95_100", "باتری ۹۵ تا ۱۰۰٪ (بدون افت)", 0, 1),
                ("battery", "batt_90_94", "باتری ۹۰ تا ۹۴٪ (افت جزئی)", -2, 2),
                ("battery", "batt_85_89", "باتری ۸۵ تا ۸۹٪ (افت متوسط)", -6, 3),
                ("battery", "batt_under_85", "باتری زیر ۸۵٪ (افت زیاد)", -12, 4),
                ("battery", "batt_replaced", "باتری تعویض‌شده (غیراصلی)", -8, 5),
                ("repair", "repair_none", "باز نشده", 0, 1),
                ("repair", "repair_opened", "باز شده (بدون تعمیر خاص)", -5, 2),
                ("repair", "repair_screen", "تعویض صفحه", -10, 3),
                ("repair", "repair_battery", "تعویض باتری (توسط تعمیرکار غیرمجاز)", -6, 4),
                ("repair", "repair_board", "تعمیر برد", -25, 5),
                ("repair", "repair_water", "آب‌خوردگی", -35, 6),
                ("registry", "registry_registered", "رجیستر شده", 0, 1),
                ("registry", "registry_owner_transfer_needed", "نیازمند انتقال مالکیت", -3, 2),
                ("registry", "registry_owner_transferred", "مالکیت منتقل‌شده", 0, 3),
                ("registry", "registry_none", "بدون رجیستری", -15, 4),
                ("box", "box_original", "پک اصلی کارخانه", 3, 1),
                ("box", "box_repack", "ریپک", -3, 2),
                ("box", "box_none", "بدون کارتن", -6, 3),
                ("cosmetic", "cosmetic_clean", "کاملاً تمیز", 0, 1),
                ("cosmetic", "cosmetic_minor", "خط و خش جزئی", -3, 2),
                ("cosmetic", "cosmetic_medium", "خط و خش متوسط", -7, 3),
                ("cosmetic", "cosmetic_heavy", "خط و خش زیاد", -12, 4),
                ("cosmetic", "cosmetic_frame_hit", "ضربه فریم", -10, 5),
                ("cosmetic", "cosmetic_front_crack", "شکستگی شیشه جلو", -20, 6),
                ("cosmetic", "cosmetic_back_crack", "شکستگی پشت", -15, 7),
                ("cable", "cable_original", "کابل اصلی دارد", 1, 1),
                ("cable", "cable_none", "کابل ندارد", -1, 2),
                ("cable", "cable_fake", "کابل غیر اصلی", -1, 3),
                ("condition", "cond_new", "نو", 5, 1),
                ("condition", "cond_sealed", "پلمپ", 8, 2),
                ("condition", "cond_like_new", "در حد نو", 0, 3),
                ("condition", "cond_used", "کارکرده", -10, 4),
                ("condition", "cond_needs_repair", "نیازمند تعمیر", -30, 5),
            ]
            for cat, key, label, pct, order in defaults:
                conn.execute(
                    "INSERT INTO iv_coefficients (category, option_key, option_label, percent, sort_order) "
                    "VALUES (?,?,?,?,?);", (cat, key, label, pct, order))
            conn.commit()
    finally:
        conn.close()
    _SCHEMA_DONE = True


# ─── مدل‌ها ──────────────────────────────────────────────────────────────

def list_models(active_only: bool = True) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_models"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY sort_order ASC, id ASC;"
        return [dict(r) for r in conn.execute(q).fetchall()]
    finally:
        conn.close()


def get_model(model_id: int) -> dict | None:
    ensure_schema()
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM iv_models WHERE id=?;", (model_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_model(name: str, series: str = "", sort_order: int = 0) -> int:
    ensure_schema()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO iv_models (name, series, sort_order) VALUES (?,?,?);",
            (name.strip(), (series or "").strip(), sort_order))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_model(model_id: int, **fields) -> None:
    ensure_schema()
    if not fields:
        return
    allowed = {"name", "series", "sort_order", "active"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    conn = _conn()
    try:
        conn.execute(
            f"UPDATE iv_models SET {', '.join(c+'=?' for c in cols)} WHERE id=?;",
            [fields[c] for c in cols] + [model_id])
        conn.commit()
    finally:
        conn.close()


# ─── ظرفیت/قیمت‌ها ───────────────────────────────────────────────────────

def list_capacities(model_id: int | None = None, active_only: bool = True) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_capacities WHERE 1=1"
        params = []
        if model_id is not None:
            q += " AND model_id=?"
            params.append(model_id)
        if active_only:
            q += " AND active=1"
        q += " ORDER BY base_price ASC, id ASC;"
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def get_capacity(cap_id: int) -> dict | None:
    ensure_schema()
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM iv_capacities WHERE id=?;", (cap_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_capacity(model_id: int, capacity_label: str, base_price: int,
                     buy_price_ref: int, sell_price_ref: int,
                     fx_ref_rate: int = 0, demand_percent: float = 0) -> int:
    ensure_schema()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO iv_capacities "
            "(model_id, capacity_label, base_price, buy_price_ref, sell_price_ref, fx_ref_rate, demand_percent) "
            "VALUES (?,?,?,?,?,?,?);",
            (model_id, capacity_label.strip(), base_price, buy_price_ref, sell_price_ref,
             fx_ref_rate, demand_percent))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_capacity(cap_id: int, **fields) -> None:
    ensure_schema()
    if not fields:
        return
    allowed = {"capacity_label", "base_price", "buy_price_ref", "sell_price_ref",
               "fx_ref_rate", "demand_percent", "active"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    conn = _conn()
    try:
        conn.execute(
            f"UPDATE iv_capacities SET {', '.join(c+'=?' for c in cols)}, updated_at=datetime('now') WHERE id=?;",
            [fields[c] for c in cols] + [cap_id])
        conn.commit()
    finally:
        conn.close()


# ─── ضرایب ───────────────────────────────────────────────────────────────

COEFFICIENT_CATEGORIES = ["condition", "battery", "repair", "registry", "box", "cosmetic", "cable"]


def list_coefficients(category: str | None = None, active_only: bool = True) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_coefficients WHERE 1=1"
        params = []
        if category:
            q += " AND category=?"
            params.append(category)
        if active_only:
            q += " AND active=1"
        q += " ORDER BY category ASC, sort_order ASC, id ASC;"
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def create_coefficient(category: str, option_key: str, option_label: str,
                        percent: float, sort_order: int = 0) -> int:
    ensure_schema()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO iv_coefficients (category, option_key, option_label, percent, sort_order) "
            "VALUES (?,?,?,?,?);",
            (category, option_key.strip(), option_label.strip(), percent, sort_order))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_coefficient(coef_id: int, **fields) -> None:
    ensure_schema()
    if not fields:
        return
    allowed = {"option_label", "percent", "sort_order", "active"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    conn = _conn()
    try:
        conn.execute(
            f"UPDATE iv_coefficients SET {', '.join(c+'=?' for c in cols)} WHERE id=?;",
            [fields[c] for c in cols] + [coef_id])
        conn.commit()
    finally:
        conn.close()


def delete_coefficient(coef_id: int) -> None:
    update_coefficient(coef_id, active=0)


# ─── ضرایب امتیازدهی ─────────────────────────────────────────────────────

def list_score_weights() -> dict:
    ensure_schema()
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM iv_score_weights;").fetchall()
        return {r["category"]: r["weight"] for r in rows}
    finally:
        conn.close()


def set_score_weight(category: str, weight: float) -> None:
    ensure_schema()
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO iv_score_weights (category, weight) VALUES (?,?) "
            "ON CONFLICT(category) DO UPDATE SET weight=excluded.weight;",
            (category, weight))
        conn.commit()
    finally:
        conn.close()


# ─── منابع نرخ ارز ───────────────────────────────────────────────────────

def list_fx_sources(active_only: bool = False) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_fx_sources"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY priority ASC, id ASC;"
        return [dict(r) for r in conn.execute(q).fetchall()]
    finally:
        conn.close()


def create_fx_source(name: str, url: str, json_path: str = "price", priority: int = 1) -> int:
    ensure_schema()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO iv_fx_sources (name, url, json_path, priority) VALUES (?,?,?,?);",
            (name.strip(), url.strip(), json_path.strip() or "price", priority))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_fx_source(source_id: int, **fields) -> None:
    ensure_schema()
    if not fields:
        return
    allowed = {"name", "url", "json_path", "priority", "active"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    conn = _conn()
    try:
        conn.execute(
            f"UPDATE iv_fx_sources SET {', '.join(c+'=?' for c in cols)} WHERE id=?;",
            [fields[c] for c in cols] + [source_id])
        conn.commit()
    finally:
        conn.close()


def delete_fx_source(source_id: int) -> None:
    ensure_schema()
    conn = _conn()
    try:
        conn.execute("DELETE FROM iv_fx_sources WHERE id=?;", (source_id,))
        conn.commit()
    finally:
        conn.close()


def record_fx_fetch(source_id: int, value: int | None, error: str | None) -> None:
    ensure_schema()
    conn = _conn()
    try:
        conn.execute(
            "UPDATE iv_fx_sources SET last_value=?, last_fetched_at=datetime('now'), last_error=? WHERE id=?;",
            (value, error, source_id))
        conn.commit()
    finally:
        conn.close()


# ─── تاریخچهٔ معاملات StockLand (برای یادگیری بازار) ─────────────────────

def list_transactions(model_id: int | None = None, limit: int = 50) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_transactions WHERE 1=1"
        params = []
        if model_id is not None:
            q += " AND model_id=?"
            params.append(model_id)
        q += " ORDER BY id DESC LIMIT ?;"
        params.append(limit)
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def create_transaction(model_id: int, capacity_id: int, buy_price: int, sell_price: int,
                        condition_note: str = "", sold_at: str | None = None,
                        days_to_sell: int | None = None) -> int:
    ensure_schema()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO iv_transactions (model_id, capacity_id, condition_note, buy_price, sell_price, "
            "sold_at, days_to_sell) VALUES (?,?,?,?,?,?,?);",
            (model_id, capacity_id, condition_note, buy_price, sell_price, sold_at, days_to_sell))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def market_data_avg_delta_pct(model_id: int, capacity_id: int, base_price: int) -> float:
    """میانگین درصد اختلاف قیمت فروش واقعی نسبت به قیمت پایه، برای همون مدل+ظرفیت."""
    ensure_schema()
    if base_price <= 0:
        return 0.0
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT sell_price FROM iv_transactions WHERE model_id=? AND capacity_id=? "
            "ORDER BY id DESC LIMIT 20;", (model_id, capacity_id)).fetchall()
        if not rows:
            return 0.0
        deltas = [((r["sell_price"] - base_price) / base_price) * 100 for r in rows if r["sell_price"]]
        return sum(deltas) / len(deltas) if deltas else 0.0
    finally:
        conn.close()


# ─── لاگ کارشناسی‌ها ──────────────────────────────────────────────────────

def create_valuation(**fields) -> int:
    ensure_schema()
    cols = ["user_id", "model_id", "capacity_id", "color", "part_number", "sim_type", "input_json",
            "market_price", "fair_price", "buy_price", "sell_price", "score", "verdict", "report_text",
            "seller_price", "city", "seller_type"]
    values = [fields.get(c) for c in cols]
    conn = _conn()
    try:
        cur = conn.execute(
            f"INSERT INTO iv_valuations ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)});",
            values)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_valuations(limit: int = 50, model_id: int | None = None) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = ("SELECT v.*, m.name AS model_name, c.capacity_label FROM iv_valuations v "
             "LEFT JOIN iv_models m ON m.id=v.model_id "
             "LEFT JOIN iv_capacities c ON c.id=v.capacity_id WHERE 1=1")
        params = []
        if model_id is not None:
            q += " AND v.model_id=?"
            params.append(model_id)
        q += " ORDER BY v.id DESC LIMIT ?;"
        params.append(limit)
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def get_stats() -> dict:
    ensure_schema()
    conn = _conn()
    try:
        total = conn.execute("SELECT COUNT(*) c FROM iv_valuations;").fetchone()["c"]
        today = conn.execute(
            "SELECT COUNT(*) c FROM iv_valuations WHERE date(created_at)=date('now');").fetchone()["c"]
        popular = conn.execute(
            "SELECT m.name, COUNT(*) cnt FROM iv_valuations v LEFT JOIN iv_models m ON m.id=v.model_id "
            "GROUP BY v.model_id ORDER BY cnt DESC LIMIT 5;").fetchall()
        avg_fair = conn.execute("SELECT AVG(fair_price) a FROM iv_valuations WHERE fair_price>0;").fetchone()["a"]
        avg_gap = conn.execute(
            "SELECT AVG((seller_price - fair_price) * 100.0 / fair_price) a FROM iv_valuations "
            "WHERE seller_price IS NOT NULL AND seller_price>0 AND fair_price>0;").fetchone()["a"]
        return {
            "total": total,
            "today": today,
            "popular_models": [dict(r) for r in popular],
            "avg_fair_price": round(avg_fair) if avg_fair else 0,
            "avg_price_gap_pct": round(avg_gap, 1) if avg_gap else 0,
        }
    finally:
        conn.close()
