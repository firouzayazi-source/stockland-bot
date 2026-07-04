import os
import sqlite3
from datetime import datetime

from config import DB_PATH, BASE_DIR

# اگر DB_PATH در config نسبی باشد، به BASE_DIR وصل میکنیم
DB_FULL_PATH = DB_PATH
if not os.path.isabs(DB_FULL_PATH):
    DB_FULL_PATH = os.path.join(BASE_DIR, DB_PATH)


def _get_connection():
    """
    همیشه یک کانکشن جدید میسازد تا با Threadهای تلگرام مشکل نداشته باشیم.
    """
    conn = sqlite3.connect(DB_FULL_PATH, timeout=30)
    # Configure SQLite to handle concurrent writers better
    try:
        conn.execute('PRAGMA journal_mode=WAL;')
        conn.execute('PRAGMA busy_timeout=5000;')
    except Exception:
        pass
    return conn


def init_db(db_path=None):
    """
    ساخت / بهروزرسانی جداول دیتابیس.
    اگر قبلاً ساخته شده باشد، فقط مهاجرتهای لازم را انجام میدهد.
    """
    global DB_FULL_PATH
    if db_path:
        if not os.path.isabs(db_path):
            DB_FULL_PATH = os.path.join(BASE_DIR, db_path)
        else:
            DB_FULL_PATH = db_path

    os.makedirs(os.path.dirname(DB_FULL_PATH), exist_ok=True)

    conn = _get_connection()
    try:
        cur = conn.cursor()

        # جدول کیف پول
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS wallets (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """
        )

        # جدول محصولات
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                product_key TEXT NOT NULL,
                title TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            """
        )

        # مهاجرت: ستون قیمت همکار برای محصولات
        try:
            cur.execute("ALTER TABLE products ADD COLUMN partner_price INTEGER;")
        except sqlite3.OperationalError:
            # ستون احتمالاً وجود دارد
            pass

        # مهاجرت: ستونهای حد خرید روزانه برای محصولات
        try:
            cur.execute('ALTER TABLE products ADD COLUMN daily_limit_customer INTEGER DEFAULT 0;')
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute('ALTER TABLE products ADD COLUMN daily_limit_partner INTEGER DEFAULT 0;')
        except sqlite3.OperationalError:
            pass


        # جدول همکاران (نمایندگان)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS partners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_user_id INTEGER UNIQUE,
                phone TEXT UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending',
                username TEXT,
                full_name TEXT,
                note TEXT,
                city TEXT,
                shop_name TEXT,
                created_at TEXT NOT NULL,
                approved_at TEXT
            );
            """
        )


    
    
        # مهاجرت/ایندکسها برای partners
        try:
            cur.execute("PRAGMA table_info(partners);")
            cols = {row[1] for row in cur.fetchall()}
            # ستونهای اصلی
            if "tg_user_id" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN tg_user_id INTEGER;")
            if "phone" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN phone TEXT;")
            if "status" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN status TEXT NOT NULL DEFAULT 'pending';")
            if "username" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN username TEXT;")
            if "full_name" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN full_name TEXT;")
            if "note" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN note TEXT;")
            if "city" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN city TEXT;")
            if "shop_name" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN shop_name TEXT;")
            if "created_at" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN created_at TEXT;")
            if "approved_at" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN approved_at TEXT;")
            # ایندکس یکتا برای جلوگیری از درخواست تکراری
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_partners_phone ON partners(phone);")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_partners_tg_user_id ON partners(tg_user_id);")
        except Exception:
            pass

        # ول سفارشها
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                product_id TEXT NOT NULL,
                title TEXT NOT NULL,
                price INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                buyer_type TEXT
            );
            """
        )
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN buyer_type TEXT;")
        except sqlite3.OperationalError:
            pass
        # وضعیت سفارش: active | returned (برای مورد برگشت محصول)
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'active';")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN feed_id INTEGER;")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN returned_at TEXT;")
        except sqlite3.OperationalError:
            pass

        # جدول تراکنشهای زرینپال
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS zarinpal_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                authority TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        for col, decl in {
            "payment_type": "TEXT DEFAULT 'wallet'",
            "product_id": "INTEGER",
            "wallet_reserved": "INTEGER DEFAULT 0",
            "total_amount": "INTEGER",
            "buyer_type": "TEXT",
            "ref_id": "TEXT",
            "paid_at": "TEXT",
            "error": "TEXT",
        }.items():
            try:
                cur.execute(f"ALTER TABLE zarinpal_transactions ADD COLUMN {col} {decl};")
            except sqlite3.OperationalError:
                pass
        # A1 — Ledger تراکنش: authority باید یکتا باشد (anchor برای ایمنی/ایدِمپوتنسی)
        # اگر DB قدیمی authority تکراری داشته باشد، ابتدا dedupe میکنیم و سپس ایندکس یکتا را میسازیم.
        try:
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_zarinpal_transactions_authority "
                "ON zarinpal_transactions(authority);"
            )
        except (sqlite3.IntegrityError, sqlite3.OperationalError):
            # نگه داشتن قدیمیترین رکورد هر authority و حذف بقیه
            cur.execute(
                """
                DELETE FROM zarinpal_transactions
                WHERE id NOT IN (
                    SELECT MIN(id) FROM zarinpal_transactions GROUP BY authority
                );
                """
            )
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_zarinpal_transactions_authority "
                "ON zarinpal_transactions(authority);"
            )


        # جدول فید محصولات (انبار تحویل خودکار)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS product_feed (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                delivered INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )

    

        # تنظیمات هشدار کمبود موجودی فید (برای هر محصول)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feed_alert_settings (
                product_id INTEGER PRIMARY KEY,
                threshold INTEGER NOT NULL DEFAULT 5,
                last_notified_remaining INTEGER,
                updated_at TEXT NOT NULL
            );
            """
        )

        # جدول سرویسهای «سایر محصولات» (زیرشاخههای پویا مثل Gmail/Yahoo و ...)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS other_services (
                service_key TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                emoji TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            """
        )

        seed_defaults = os.getenv("SEED_DEFAULT_DATA", "0") == "1"



        # اگر هیچ سرویسی تعریف نشده بود، پیشفرض جیمیل را اضافه کن
        cur.execute("SELECT COUNT(*) FROM other_services;")
        svc_count = cur.fetchone()[0] or 0
        if seed_defaults and svc_count == 0:
            now = datetime.utcnow().isoformat()
            cur.execute(
                "INSERT INTO other_services (service_key, title, emoji, is_active, created_at) VALUES (?, ?, ?, ?, ?);",
                ("gmail", "سرویسهای جیمیل", "✉️", 1, now),
            )


        # اگر هیچ محصولی وجود نداشت، چند محصول نمونه اضافه کن
        cur.execute("SELECT COUNT(*) FROM products;")
        count = cur.fetchone()[0] or 0
        if seed_defaults and count == 0:
            sample_products = [
                ("apple", "apple_ready_1", "اپل آیدی آماده ریجن آمریکا", 250000,
                 "تحویل فوری، آمریکا، بدون سوال امنیتی.", 1),
                ("apple", "apple_ready_2", "اپل آیدی آماده ریجن ترکیه", 130000,
                 "تحویل فوری، ترکیه، مناسب خریدهای ارزانتر.", 1),
                ("apple", "apple_ready_3", "ساخت اپل آیدی با ایمیل شما", 170000,
                 "ساخت دستی، تنظیم ریجن مناسب، تحویل ۳۰ دقیقهای.", 1),
                ("gmail", "gmail_ready_1", "جیمیل آماده سنی وریفای شده", 90000,
                 "ایدهآل برای سرویسهای تحریممحور، سنی بالای ۱۸ سال.", 1),
                ("gmail", "gmail_ready_2", "جیمیل اختصاصی با مشخصات شما", 110000,
                 "ساخت اختصاصی، تحویل تا ۱ ساعت.", 1),
            ]
            cur.executemany(
                """
                INSERT INTO products (category, product_key, title, price, description, is_active)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                sample_products,
            )

        # جدول دستهبندیهای داینامیک (نامحدود، درختی)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                parent_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                emoji TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # ستون category_id برای محصولات
        try:
            cur.execute("ALTER TABLE products ADD COLUMN category_id INTEGER REFERENCES categories(id);")
        except sqlite3.OperationalError:
            pass

        # جدول کاربران (برای Broadcast)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # جدول پیامهای تیکت (تاریخچه مکالمه)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                sender TEXT NOT NULL,
                text TEXT,
                media_type TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # جدول متنهای رابط کاربری (UI)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ui_texts (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        conn.commit()
    finally:
        conn.close()


# ========= WALLET HELPERS =========


def get_wallet_balance(user_id: int) -> int:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM wallets WHERE user_id = ?;", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return 0
    return int(row[0])


def add_wallet_balance(user_id: int, amount: int) -> int:
    """
    موجودی را افزایش میدهد و موجودی جدید را برمیگرداند.
    """
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM wallets WHERE user_id = ?;", (user_id,))
    row = cur.fetchone()
    if row:
        new_balance = int(row[0]) + int(amount)
        cur.execute(
            "UPDATE wallets SET balance = ?, updated_at = ? WHERE user_id = ?;",
            (new_balance, now, user_id),
        )
    else:
        new_balance = int(amount)
        cur.execute(
            "INSERT INTO wallets (user_id, balance, updated_at) VALUES (?, ?, ?);",
            (user_id, new_balance, now),
        )
    conn.commit()
    conn.close()
    return new_balance


def subtract_wallet_balance(user_id: int, amount: int) -> bool:
    """
    اگر موجودی کافی باشد، مبلغ را کم میکند و True برمیگرداند؛ در غیر این صورت False.
    """
    amount = int(amount)
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM wallets WHERE user_id = ?;", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False
    balance = int(row[0])
    if balance < amount:
        conn.close()
        return False

    new_balance = balance - amount
    now = datetime.utcnow().isoformat()
    cur.execute(
        "UPDATE wallets SET balance = ?, updated_at = ? WHERE user_id = ?;",
        (new_balance, now, user_id),
    )
    conn.commit()
    conn.close()
    return True


def set_wallet_balance(user_id: int, new_balance: int) -> int:
    """
    مستقیماً موجودی کیف پول را روی مقدار دلخواه تنظیم میکند (برای ادمین).
    """
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM wallets WHERE user_id = ?;", (user_id,))
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE wallets SET balance = ?, updated_at = ? WHERE user_id = ?;",
            (int(new_balance), now, user_id),
        )
    else:
        cur.execute(
            "INSERT INTO wallets (user_id, balance, updated_at) VALUES (?, ?, ?);",
            (user_id, int(new_balance), now),
        )
    conn.commit()
    conn.close()
    return int(new_balance)


# ========= ORDERS =========


def create_order(user_id: int, category: str, title: str, price: int, product_id=None, buyer_type: str | None = None) -> int:
    """
    یک سفارش جدید ثبت میکند و id سفارش را برمیگرداند.
    """
    now = datetime.utcnow().isoformat()
    product_id_str = str(product_id) if product_id is not None else ""
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO orders (user_id, category, product_id, title, price, created_at, buyer_type)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (user_id, category, product_id_str, title, int(price), now, buyer_type),
    )
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id


def get_recent_orders_by_user(user_id: int, limit: int = 10):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, title, price, created_at
            FROM orders
            WHERE CAST(user_id AS INTEGER) = ?
            ORDER BY id DESC
            LIMIT ?;
            """,
            (int(user_id), limit),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows


def get_recent_orders_global(limit: int = 15):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, user_id, title, price, created_at
            FROM orders
            ORDER BY id DESC
            LIMIT ?;
            """,
            (limit,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows


# ========= PRODUCTS =========


def get_products_by_category(category: str):
    """
    محصولات یک دسته را برمیگرداند.
    خروجی همیشه ۷ فیلد است:
    (id, category, title, price, description, is_active, partner_price)
    اگر ستون partner_price وجود نداشت، مقدار آن None خواهد بود.
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        # بررسی وجود ستون partner_price
        try:
            cur.execute("PRAGMA table_info(products);")
            cols = {row[1] for row in cur.fetchall()}
        except Exception:
            cols = set()
        has_partner = 'partner_price' in cols
        if has_partner:
            cur.execute(
                """
                SELECT id, category, title, price, description, is_active, partner_price
                FROM products
                WHERE category = ?
                ORDER BY id ASC;
                """,
                (category,),
            )
        else:
            cur.execute(
                """
                SELECT id, category, title, price, description, is_active, NULL as partner_price
                FROM products
                WHERE category = ?
                ORDER BY id ASC;
                """,
                (category,),
            )
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows

def get_product_by_id(pid: int):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        # بررسی وجود ستونها (برای سازگاری با دیتابیسهای قدیمی)
        try:
            cur.execute('PRAGMA table_info(products);')
            cols = {row[1] for row in cur.fetchall()}
        except Exception:
            cols = set()

        has_partner = 'partner_price' in cols
        has_lim_c = 'daily_limit_customer' in cols
        has_lim_p = 'daily_limit_partner' in cols

        select_cols = [
            'id', 'category', 'title', 'price', 'description', 'is_active',
            ('partner_price' if has_partner else 'NULL AS partner_price'),
            ('daily_limit_customer' if has_lim_c else '0 AS daily_limit_customer'),
            ('daily_limit_partner' if has_lim_p else '0 AS daily_limit_partner'),
        ]
        cur.execute(
            f"SELECT {', '.join(select_cols)} FROM products WHERE id = ?;",
            (pid,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    return row

def update_product_field(pid: int, field: str, value):
    """
    ویرایش فیلدهای مجاز محصول.
    """
    allowed = {"title", "price", "partner_price", "daily_limit_customer", "daily_limit_partner", "description", "is_active"}
    if field not in allowed:
        raise ValueError("Invalid product field")

    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE products SET {field} = ? WHERE id = ?;",
            (value, pid),
        )
        conn.commit()
    finally:
        conn.close()


def toggle_product_active(pid: int):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT is_active FROM products WHERE id = ?;", (pid,))
        row = cur.fetchone()
        if not row:
            return
        current = int(row[0]) or 0
        new_val = 0 if current else 1
        cur.execute(
            "UPDATE products SET is_active = ? WHERE id = ?;",
            (new_val, pid),
        )
        conn.commit()
    finally:
        conn.close()


def add_product(category: str, title: str, price: int, description: str = "", is_active: int = 1, partner_price: int | None = None) -> int:
    """
    یک محصول جدید اضافه میکند و id آن را برمیگرداند.
    product_key یا code بهصورت خودکار از روی عنوان ساخته میشود.
    اگر جدول محصولات ستون product_key یا code داشته باشد، مقدار مناسب در هر ستون درج میشود.
    اگر ستون partner_price وجود داشته باشد و partner_price داده شود، در همان ستون درج میشود.
    """
    # generate slug from title
    slug = "".join(ch if ch.isalnum() else "_" for ch in title)
    slug = slug.lower().strip("_") or "product"
    if len(slug) > 40:
        slug = slug[:40]
    conn = _get_connection()
    cur = conn.cursor()
    # discover columns in products table
    try:
        cur.execute("PRAGMA table_info(products);")
        cols = {row[1] for row in cur.fetchall()}
    except Exception:
        cols = set()

    # base columns
    col_names = []
    values = []
    # category
    col_names.append("category"); values.append(category)

    # product_key / code handling
    if 'product_key' in cols:
        col_names.append("product_key"); values.append(slug)
    if 'code' in cols:
        col_names.append("code"); values.append(slug)

    col_names.append("title"); values.append(title)
    col_names.append("price"); values.append(int(price))
    col_names.append("description"); values.append(description)
    col_names.append("is_active"); values.append(int(is_active))

    if 'partner_price' in cols and partner_price is not None:
        col_names.append("partner_price"); values.append(int(partner_price))

    placeholders = ", ".join(["?"] * len(col_names))
    sql = f"INSERT INTO products ({', '.join(col_names)}) VALUES ({placeholders});"
    cur.execute(sql, tuple(values))
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid

def delete_product(product_id: int) -> None:
    """حذف واقعی (Hard Delete) یک محصول بر اساس id.

    علاوه بر حذف رکورد محصول، آیتمهای فید مرتبط با آن نیز پاک میشوند تا رکورد یتیم باقی نماند.
    """
    conn = _get_connection()
    cur = conn.cursor()
    # پاکسازی فیدهای مرتبط (در صورت وجود)
    try:
        cur.execute("DELETE FROM product_feed WHERE product_id = ?;", (product_id,))
    except Exception:
        # اگر جدول/ستون وجود نداشت، حذف محصول را انجام بده
        pass
    cur.execute("DELETE FROM products WHERE id = ?;", (product_id,))
    conn.commit()
    conn.close()



# ========= STATS =========


def get_stats():
    """برگشت آمار کلی: (تعداد کیفها، جمع موجودیها، تعداد سفارشها، مجموع فروش، تعداد محصولات فعال)"""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        # کیف پولها
        cur.execute("SELECT COUNT(*), COALESCE(SUM(balance), 0) FROM wallets;")
        wallet_row = cur.fetchone()
        total_wallets = wallet_row[0] or 0
        total_balance = wallet_row[1] or 0
        # سفارشها
        cur.execute("SELECT COUNT(*), COALESCE(SUM(price), 0) FROM orders;")
        order_row = cur.fetchone()
        total_orders = order_row[0] or 0
        total_sales = order_row[1] or 0
        # محصولات فعال
        cur.execute("SELECT COUNT(*) FROM products WHERE is_active = 1;")
        active_products = cur.fetchone()[0] or 0
    finally:
        conn.close()
    return total_wallets, total_balance, total_orders, total_sales, active_products
def create_zarinpal_pending_transaction(user_id: int, amount: int, authority: str) -> bool:
    """یک رکورد pending برای authority میسازد. اگر authority قبلا ثبت شده باشد False برمیگرداند."""
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO zarinpal_transactions (user_id, amount, authority, status, created_at)
            VALUES (?, ?, ?, 'pending', ?);
            """,
            (int(user_id), int(amount), str(authority), now),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_zarinpal_transaction(authority: str):
    """برگشت: dict یا None"""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, user_id, amount, authority, status, created_at
            FROM zarinpal_transactions
            WHERE authority = ?
            LIMIT 1;
            """,
            (str(authority),),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "amount": row[2],
        "authority": row[3],
        "status": row[4],
        "created_at": row[5],
    }


def update_zarinpal_status(authority: str, new_status: str, expected_current: str | None = None) -> int:
    """status را تغییر میدهد. اگر expected_current داده شود فقط وقتی status فعلی همان باشد update میکند.
    خروجی: تعداد ردیفهای تغییرکرده (0 یا 1).
    """
    conn = _get_connection()
    cur = conn.cursor()
    if expected_current is None:
        cur.execute(
            "UPDATE zarinpal_transactions SET status = ? WHERE authority = ?;",
            (str(new_status), str(authority)),
        )
    else:
        cur.execute(
            "UPDATE zarinpal_transactions SET status = ? WHERE authority = ? AND status = ?;",
            (str(new_status), str(authority), str(expected_current)),
        )
    conn.commit()
    changed = cur.rowcount or 0
    conn.close()
    return int(changed)


    cur = conn.cursor()

    # کیف پولها
    cur.execute("SELECT COUNT(*), COALESCE(SUM(balance), 0) FROM wallets;")
    wallet_row = cur.fetchone()
    total_wallets = wallet_row[0] or 0
    total_balance = wallet_row[1] or 0

    # سفارشها
    cur.execute("SELECT COUNT(*), COALESCE(SUM(price), 0) FROM orders;")
    order_row = cur.fetchone()
    total_orders = order_row[0] or 0
    total_sales = order_row[1] or 0

    # محصولات فعال
    cur.execute("SELECT COUNT(*) FROM products WHERE is_active = 1;")
    active_products = cur.fetchone()[0] or 0

    conn.close()
    return total_wallets, total_balance, total_orders, total_sales, active_products


# ========= PRODUCT FEED (انبار تحویل خودکار) =========


def add_feed_items(product_id: int, items):
    """
    چند آیتم را برای یک محصول ثبت میکند.
    تکراریها ثبت میشوند اما flagged میشوند.
    Returns: {"added": int, "duplicates": list}
    """
    if not items:
        return {"added": 0, "duplicates": []}

    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    try:
        # پیدا کردن تکراریها
        duplicates = []
        for item in items:
            existing = conn.execute(
                "SELECT id FROM product_feed WHERE product_id=? AND data=? AND delivered=0 LIMIT 1;",
                (product_id, item)
            ).fetchone()
            if existing:
                duplicates.append(item)

        # ثبت همه (اعم از تکراری)
        rows = [(product_id, item, 0, now) for item in items]
        conn.executemany(
            "INSERT INTO product_feed (product_id, data, delivered, created_at) VALUES (?, ?, ?, ?);",
            rows,
        )
        conn.commit()
        return {"added": len(rows), "duplicates": duplicates}
    finally:
        conn.close()


def get_feed_stats(product_id: int):
    """
    تعداد کل، تعداد تحویل نشده، تعداد تحویل شده را برمیگرداند.
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT COUNT(*) FROM product_feed WHERE product_id = ?;",
            (product_id,),
        )
        total = cur.fetchone()[0] or 0

        cur.execute(
            "SELECT COUNT(*) FROM product_feed WHERE product_id = ? AND delivered = 0;",
            (product_id,),
        )
        remaining = cur.fetchone()[0] or 0

        delivered = total - remaining
    finally:
        conn.close()
    return total, remaining, delivered


def claim_next_feed_item(product_id: int, order_id: int = None):
    """
    اتمیک: اولین آیتم تحویلنشده را claim میکند (delivered=1) و برمیگرداند: (feed_id, data) یا None.
    از BEGIN IMMEDIATE برای جلوگیری از race condition در خریدهای همزمان استفاده میشه.
    """
    conn = _get_connection()
    cur = conn.cursor()
    try:
        # migration: اضافه کردن ستونهای tracking اگه نباشن
        try:
            cur.execute("ALTER TABLE product_feed ADD COLUMN order_id INTEGER;")
            cur.execute("ALTER TABLE product_feed ADD COLUMN delivered_at TEXT;")
            conn.commit()
        except Exception:
            pass  # ستونها قبلاً اضافه شدن

        cur.execute("BEGIN IMMEDIATE;")
        cur.execute(
            """SELECT id, data FROM product_feed
               WHERE product_id=? AND delivered=0
               ORDER BY id ASC LIMIT 1;""",
            (product_id,),
        )
        row = cur.fetchone()
        if not row:
            conn.commit()
            return None

        feed_id, feed_data = row[0], row[1]

        # چک مضاعف: مطمئن شو این آیتم قبلاً تحویل داده نشده
        cur.execute("SELECT delivered FROM product_feed WHERE id=?;", (feed_id,))
        chk = cur.fetchone()
        if not chk or chk[0] != 0:
            conn.rollback()
            return None

        cur.execute(
            "UPDATE product_feed SET delivered=1, order_id=?, delivered_at=datetime('now') WHERE id=? AND delivered=0;",
            (order_id, feed_id),
        )
        if cur.rowcount != 1:
            conn.rollback()
            return None

        conn.commit()
        return feed_id, feed_data
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_next_feed_item(product_id: int):
    """
    Deprecated (non-atomic). Use claim_next_feed_item.
    Retained for backward compatibility.
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, data
            FROM product_feed
            WHERE product_id = ? AND delivered = 0
            ORDER BY id ASC
            LIMIT 1;
            """,
            (product_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return row[0], row[1]


def mark_feed_item_delivered(feed_id: int):
    """
    Marks a feed item delivered. Prefer claim_next_feed_item for user delivery path.
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE product_feed SET delivered = 1 WHERE id = ?;",
            (feed_id,),
        )
        conn.commit()
    finally:
        conn.close()



def list_feed_items(product_id: int, delivered: int | None = None, limit: int = 10, offset: int = 0):
    """لیست آیتمهای فید یک محصول را برمیگرداند.

    delivered:
      - None: همه
      - 0: فقط تحویلنشده
      - 1: فقط تحویلشده
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()

        if delivered is None:
            cur.execute(
                """
                SELECT id, data, delivered, created_at
                FROM product_feed
                WHERE product_id = ?
                ORDER BY delivered ASC, id DESC
                LIMIT ? OFFSET ?;
                """,
                (product_id, int(limit), int(offset)),
            )
        else:
            cur.execute(
                """
                SELECT id, data, delivered, created_at
                FROM product_feed
                WHERE product_id = ? AND delivered = ?
                ORDER BY id DESC
                LIMIT ? OFFSET ?;
                """,
                (product_id, int(delivered), int(limit), int(offset)),
            )

        rows = cur.fetchall() or []
    finally:
        conn.close()
    return rows


def count_feed_items(product_id: int, delivered: int | None = None) -> int:
    conn = _get_connection()
    cur = conn.cursor()
    if delivered is None:
        cur.execute("SELECT COUNT(*) FROM product_feed WHERE product_id = ?;", (product_id,))
    else:
        cur.execute(
            "SELECT COUNT(*) FROM product_feed WHERE product_id = ? AND delivered = ?;",
            (product_id, int(delivered)),
        )
    n = cur.fetchone()[0] or 0
    conn.close()
    return int(n)


def set_feed_item_delivered(feed_id: int, delivered: int):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE product_feed SET delivered = ? WHERE id = ?;",
            (int(1 if delivered else 0), int(feed_id)),
        )
        conn.commit()
    finally:
        conn.close()


def delete_feed_item(feed_id: int):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM product_feed WHERE id = ?;", (int(feed_id),))
        conn.commit()
    finally:
        conn.close()



def list_other_services(active_only: bool = True):
    """لیست سرویسهای «سایر محصولات» را برمیگرداند."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        if active_only:
            cur.execute(
                "SELECT service_key, title, COALESCE(emoji,''), is_active FROM other_services WHERE is_active=1 ORDER BY title;"
            )
        else:
            cur.execute(
                "SELECT service_key, title, COALESCE(emoji,''), is_active FROM other_services ORDER BY title;"
            )
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows


def add_other_service(service_key: str, title: str, emoji: str = "🧩") -> bool:
    """یک سرویس جدید اضافه میکند. اگر کلید تکراری باشد False برمیگرداند."""
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO other_services (service_key, title, emoji, is_active, created_at) VALUES (?, ?, ?, 1, ?);",
            (service_key, title, emoji, now),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def delete_other_service(service_key: str, delete_products: bool = True) -> None:
    """یک سرویس را حذف میکند. در صورت delete_products محصولات و فیدهای آن سرویس هم پاک میشود."""
    conn = _get_connection()
    cur = conn.cursor()
    if delete_products:
        # حذف فیدهای مربوط به محصولات این دسته
        cur.execute(
            "DELETE FROM product_feed WHERE product_id IN (SELECT id FROM products WHERE category=?);",
            (service_key,),
        )
        # حذف محصولات این دسته
        cur.execute("DELETE FROM products WHERE category=?;", (service_key,))
    # حذف خود سرویس
    cur.execute("DELETE FROM other_services WHERE service_key=?;", (service_key,))
    conn.commit()
    conn.close()

# ========= FEED ALERT SETTINGS =========

def get_feed_alert_setting(product_id: int):
    """برمیگرداند: (threshold, last_notified_remaining). اگر تنظیمی نبود threshold=5."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT threshold, last_notified_remaining FROM feed_alert_settings WHERE product_id=?;",
            (product_id,),
        )
        row = cur.fetchone()
        if not row:
            threshold = 5
            last = None
            now = datetime.utcnow().isoformat()
            cur.execute(
                "INSERT OR IGNORE INTO feed_alert_settings (product_id, threshold, last_notified_remaining, updated_at) VALUES (?, ?, NULL, ?);",
                (product_id, threshold, now),
            )
            conn.commit()
            return threshold, last
        return int(row[0]), row[1]
    finally:
        conn.close()


def set_feed_alert_threshold(product_id: int, threshold: int):
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO feed_alert_settings (product_id, threshold, last_notified_remaining, updated_at) VALUES (?, ?, NULL, ?) "
            "ON CONFLICT(product_id) DO UPDATE SET threshold=excluded.threshold, updated_at=excluded.updated_at;",
            (product_id, int(threshold), now),
        )
        conn.commit()
    finally:
        conn.close()


def reset_feed_alert_notification(product_id: int):
    """پس از شارژ مجدد موجودی، هشدار قبلی ریست میشود تا دوباره ارسال شود."""
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO feed_alert_settings (product_id, threshold, last_notified_remaining, updated_at) VALUES (?, 5, NULL, ?) "
            "ON CONFLICT(product_id) DO UPDATE SET last_notified_remaining=NULL, updated_at=excluded.updated_at;",
            (product_id, now),
        )
        conn.commit()
    finally:
        conn.close()


def set_feed_alert_last_notified(product_id: int, remaining: int):
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO feed_alert_settings (product_id, threshold, last_notified_remaining, updated_at) VALUES (?, 5, ?, ?) "
            "ON CONFLICT(product_id) DO UPDATE SET last_notified_remaining=excluded.last_notified_remaining, updated_at=excluded.updated_at;",
            (product_id, int(remaining), now),
        )
        conn.commit()
    finally:
        conn.close()

# =====================
# Partner / Reseller API
# =====================

def upsert_partner_request(tg_user_id: int, phone: str, username: str = "", full_name: str = "", note: str = "", city: str = "", shop_name: str = ""):
    """ثبت درخواست نمایندگی.

    سیاست فعلی: هر کاربر/شماره فقط یکبار میتواند درخواست ثبت کند.
    بنابراین اگر رکوردی وجود داشته باشد، وضعیت آن را به pending برنمیگردانیم.
    - pending: فقط اطلاعات پروفایل را بهروزرسانی میکنیم (بدون تغییر created_at)
    - approved: فقط اطلاعات پروفایل را بهروزرسانی میکنیم (بدون تغییر approved_at)
    - rejected: فقط اطلاعات پروفایل را بهروزرسانی میکنیم
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat(timespec='seconds')

        cur.execute("SELECT id, status, created_at, approved_at FROM partners WHERE tg_user_id = ? OR phone = ? ORDER BY id DESC LIMIT 1;", (tg_user_id, phone))
        row = cur.fetchone()

        if row:
            pid, st, created_at, approved_at = row[0], (row[1] or "").strip().lower(), row[2], row[3]
            if st == "pending":
                cur.execute(
                    """
                    UPDATE partners
                    SET tg_user_id = ?, phone = ?, username = ?, full_name = ?, note = ?,
                        city = COALESCE(?, city), shop_name = COALESCE(?, shop_name)
                    WHERE id = ?;
                    """,
                    (tg_user_id, phone, username, full_name, note, city or None, shop_name or None, pid),
                )
            elif st == "approved":
                cur.execute(
                    """
                    UPDATE partners
                    SET tg_user_id = ?, phone = ?, username = ?, full_name = ?, note = ?,
                        city = COALESCE(?, city), shop_name = COALESCE(?, shop_name)
                    WHERE id = ?;
                    """,
                    (tg_user_id, phone, username, full_name, note, city or None, shop_name or None, pid),
                )
            elif st == "rejected":
                cur.execute(
                    """
                    UPDATE partners
                    SET tg_user_id = ?, phone = ?, username = ?, full_name = ?, note = ?,
                        city = COALESCE(?, city), shop_name = COALESCE(?, shop_name)
                    WHERE id = ?;
                    """,
                    (tg_user_id, phone, username, full_name, note, city or None, shop_name or None, pid),
                )
            else:
                # وضعیتهای ناشناخته: مثل pending رفتار کن
                cur.execute(
                    """
                    UPDATE partners
                    SET tg_user_id = ?, phone = ?, username = ?, full_name = ?, note = ?,
                        city = COALESCE(?, city), shop_name = COALESCE(?, shop_name)
                    WHERE id = ?;
                    """,
                    (tg_user_id, phone, username, full_name, note, city or None, shop_name or None, pid),
                )
        else:
            cur.execute(
                """
                INSERT OR IGNORE INTO partners (tg_user_id, phone, status, username, full_name, note, city, shop_name, created_at)
                VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?);
                """,
                (tg_user_id, phone, username, full_name, note, city, shop_name, now),
            )

        conn.commit()
    finally:
        conn.close()



def update_partner_city_shop(tg_user_id: int, city: str = "", shop_name: str = ""):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE partners SET city = COALESCE(?, city), shop_name = COALESCE(?, shop_name) WHERE tg_user_id = ?;",
            (city or None, shop_name or None, tg_user_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_partner_by_user_id(tg_user_id: int):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, tg_user_id, phone, status, username, full_name, note, created_at, approved_at
            FROM partners WHERE tg_user_id = ? ORDER BY id DESC LIMIT 1;
            """,
            (tg_user_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    return row


def get_partner_by_phone(phone: str):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, tg_user_id, phone, status, username, full_name, note, created_at, approved_at
            FROM partners WHERE phone = ? ORDER BY id DESC LIMIT 1;
            """,
            (phone,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    return row

def list_partner_requests(status: str | None = None, query: str | None = None, limit: int = 50, offset: int = 0):
    """لیست درخواستهای همکار با امکان فیلتر وضعیت و جستجو.

    خروجی: (id, tg_user_id, phone, username, full_name, city, shop_name, status, created_at, approved_at)
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT id, tg_user_id, phone, username, full_name, city, shop_name, status, created_at, approved_at
            FROM partners
            WHERE 1=1
        """
        params: list = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if query:
            q = f"%{query.strip()}%"
            sql += " AND (phone LIKE ? OR username LIKE ? OR full_name LIKE ? OR city LIKE ? OR shop_name LIKE ?)"
            params.extend([q, q, q, q, q])
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?;"
        params.extend([int(limit), int(offset)])
        cur.execute(sql, params)
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows


def list_pending_partners():
    # برای سازگاری با کدهای قبلی
    return list_partner_requests(status='pending', query=None, limit=200, offset=0)

def approve_partner(tg_user_id: int):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat(timespec='seconds')
        cur.execute(
            """UPDATE partners SET status='approved', approved_at=? WHERE tg_user_id=?;""",
            (now, tg_user_id),
        )
        conn.commit()
        changed = cur.rowcount
    finally:
        conn.close()
    return changed > 0

def reject_partner(tg_user_id: int):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE partners SET status='rejected' WHERE tg_user_id=?;", (tg_user_id,))
        conn.commit()
        changed = cur.rowcount
    finally:
        conn.close()
    return changed > 0

def is_partner_approved(tg_user_id: int) -> bool:
    conn = _get_connection()
    try:
        ok = conn.execute(
            "SELECT 1 FROM partners WHERE tg_user_id=? AND status='approved' LIMIT 1;",
            (tg_user_id,)
        ).fetchone() is not None
        return ok
    finally:
        conn.close()


def count_user_product_orders_today(user_id: int, product_id: int | None = None, buyer_type: str | None = None) -> int:
    """
    Counts user's product orders created 'today' (server local date).
    Safe fallback: returns 0 if table/columns aren't present.
    NOTE: Replace with real query once order schema is confirmed.
    """
    import datetime
    import sqlite3
    try:
        # DB_PATH should exist in this module; fallback to default path if not.
        db_path = globals().get("DB_FULL_PATH") or globals().get("DB_PATH") or os.path.join(BASE_DIR, "db.sqlite")
        con = sqlite3.connect(db_path, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA journal_mode=WAL;")
            con.execute("PRAGMA busy_timeout=10000;")
        except Exception:
            pass

        # Heuristic table detection
        tables = {r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        # common candidates
        candidates = ["product_orders", "orders", "user_orders", "order_items"]
        table = next((t for t in candidates if t in tables), None)
        if not table:
            return 0

        cols = {r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
        # heuristics for columns
        user_col = "user_id" if "user_id" in cols else ("uid" if "uid" in cols else None)
        ts_col = "created_at" if "created_at" in cols else ("created" if "created" in cols else ("ts" if "ts" in cols else None))
        prod_col = "product_id" if "product_id" in cols else ("pid" if "pid" in cols else None)

        if not user_col or not ts_col:
            return 0

        today = datetime.date.today().isoformat()  # 'YYYY-MM-DD'
        # If timestamps stored as ISO text, this works with LIKE; otherwise returns 0.
        q = f"SELECT COUNT(1) AS c FROM {table} WHERE {user_col}=? AND {ts_col} LIKE ?"
        params = [user_id, today + "%"]
        if product_id is not None and prod_col:
            q += f" AND {prod_col}=?"
            params.append(product_id)

        row = con.execute(q, params).fetchone()
        return int(row["c"] if row and "c" in row.keys() else 0)
    except Exception:
        return 0
    finally:
        try:
            con.close()
        except Exception:
            pass


def count_user_product_orders_today(user_id: int, product_id: int | None = None, buyer_type: str | None = None) -> int:
    """
    Count how many orders this user placed today (optionally per product).
    If orders table has buyer_type column, it will be respected.
    buyer_type example values typically: 'customer' / 'partner'
    """
    import datetime, sqlite3

    db_path = globals().get("DB_FULL_PATH") or globals().get("DB_PATH") or os.path.join(BASE_DIR, "db.sqlite")
    con = sqlite3.connect(db_path, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        try:
            con.execute("PRAGMA journal_mode=WAL;")
            con.execute("PRAGMA busy_timeout=10000;")
        except Exception:
            pass

        # Ensure orders table exists
        row = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'").fetchone()
        if not row:
            return 0

        cols = {r["name"] for r in con.execute("PRAGMA table_info(orders)").fetchall()}

        # Minimal required columns
        if "user_id" not in cols or "created_at" not in cols:
            return 0

        today = datetime.date.today().isoformat()  # YYYY-MM-DD

        q = "SELECT COUNT(1) AS c FROM orders WHERE user_id=? AND created_at LIKE ?"
        params = [user_id, today + "%"]

        if product_id is not None and "product_id" in cols:
            q += " AND product_id=?"
            params.append(product_id)

        # Apply buyer_type filter only if schema supports it
        if buyer_type and "buyer_type" in cols:
            q += " AND buyer_type=?"
            params.append(buyer_type)

        r = con.execute(q, params).fetchone()
        return int(r["c"] if r else 0)
    finally:
        con.close()

# ========= UI TEXTS =========

def get_ui_text(key: str) -> str | None:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM ui_texts WHERE key=? LIMIT 1;", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def set_ui_text(key: str, value: str) -> None:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO ui_texts(key, value, updated_at) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;",
        (key, value, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def delete_ui_text(key: str) -> None:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM ui_texts WHERE key=?;", (key,))
    conn.commit()
    conn.close()


def list_ui_texts(prefix: str | None = None) -> list[tuple[str, str, str]]:
    conn = _get_connection()
    cur = conn.cursor()
    if prefix:
        cur.execute(
            "SELECT key, value, updated_at FROM ui_texts WHERE key LIKE ? ORDER BY key ASC;",
            (f"{prefix}%",),
        )
    else:
        cur.execute("SELECT key, value, updated_at FROM ui_texts ORDER BY key ASC;")
    rows = cur.fetchall() or []
    conn.close()
    return rows


# ========= CATEGORIES =========

def get_root_categories(active_only: bool = True) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = "AND is_active=1" if active_only else ""
        return conn.execute(
            f"SELECT * FROM categories WHERE parent_id IS NULL {where} ORDER BY sort_order, name;"
        ).fetchall()
    finally:
        conn.close()


def get_subcategories(parent_id: int, active_only: bool = True) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = "AND is_active=1" if active_only else ""
        return conn.execute(
            f"SELECT * FROM categories WHERE parent_id=? {where} ORDER BY sort_order, name;",
            (parent_id,)
        ).fetchall()
    finally:
        conn.close()


def get_category(cat_id: int):
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM categories WHERE id=? LIMIT 1;", (cat_id,)).fetchone()
    finally:
        conn.close()


def get_category_by_slug(slug: str):
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM categories WHERE slug=? LIMIT 1;", (slug,)).fetchone()
    finally:
        conn.close()


def get_category_products(cat_id: int, active_only: bool = True) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = "AND is_active=1" if active_only else ""
        return conn.execute(
            f"SELECT * FROM products WHERE category_id=? {where} ORDER BY id;",
            (cat_id,)
        ).fetchall()
    finally:
        conn.close()


_CAT_BTN_CACHE = {"t": 0.0, "map": {}}

def _cat_btn_map() -> dict:
    """نقشه متن دکمه ← دسته ریشه — کش ۲۰ ثانیه (این تابع در فیلتر هر پیام صدا می‌خورد)."""
    import time as _t
    now = _t.time()
    if now - _CAT_BTN_CACHE["t"] < 20:
        return _CAT_BTN_CACHE["map"]
    m = {}
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        for cat in conn.execute(
            "SELECT * FROM categories WHERE parent_id IS NULL AND is_active=1;"
        ).fetchall():
            emoji = (cat["emoji"] or "").strip()
            btn = f"{emoji} {cat['name']}".strip() if emoji else cat["name"]
            m[btn] = dict(cat)
    except Exception:
        pass
    finally:
        conn.close()
    _CAT_BTN_CACHE["t"] = now
    _CAT_BTN_CACHE["map"] = m
    return m


def cat_btn_cache_clear():
    _CAT_BTN_CACHE["t"] = 0.0


def get_category_by_button_text(text: str):
    """یافتن دسته ریشه بر اساس متن دکمه Reply Keyboard — از کش."""
    return _cat_btn_map().get((text or "").strip())


def _legacy_get_category_by_button_text(text: str):
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        cats = conn.execute(
            "SELECT * FROM categories WHERE parent_id IS NULL AND is_active=1;"
        ).fetchall()
        text = (text or "").strip()
        for cat in cats:
            emoji = (cat["emoji"] or "").strip()
            btn = f"{emoji} {cat['name']}".strip() if emoji else cat["name"]
            if btn == text:
                return cat
        return None
    finally:
        conn.close()


def create_category(name: str, parent_id: int | None, emoji: str = "", sort_order: int = 0) -> int:
    slug = "".join(c if c.isalnum() else "_" for c in name).lower()[:40]
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        cur = conn.execute(
            "INSERT INTO categories (name, slug, parent_id, emoji, sort_order, is_active, created_at) VALUES (?,?,?,?,?,1,?);",
            (name.strip(), slug, parent_id, emoji.strip(), sort_order, now)
        )
        cat_id = cur.lastrowid
        conn.commit()
        return cat_id
    finally:
        conn.close()


def update_category(cat_id: int, name: str, emoji: str, sort_order: int, is_active: int) -> None:
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE categories SET name=?, emoji=?, sort_order=?, is_active=? WHERE id=?;",
            (name.strip(), emoji.strip(), sort_order, is_active, cat_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_category(cat_id: int) -> None:
    """حذف دسته و همه زیردستهها و محصولات مرتبط"""
    conn = _get_connection()
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        # پیدا کردن همه IDs به صورت recursive
        all_ids = _collect_category_ids(conn, cat_id)
        for cid in all_ids:
            conn.execute("DELETE FROM product_feed WHERE product_id IN (SELECT id FROM products WHERE category_id=?);", (cid,))
            conn.execute("DELETE FROM products WHERE category_id=?;", (cid,))
        conn.execute("DELETE FROM categories WHERE id IN ({});".format(",".join("?" * len(all_ids))), all_ids)
        conn.commit()
    finally:
        conn.close()


def _collect_category_ids(conn, cat_id: int) -> list:
    ids = [cat_id]
    children = conn.execute("SELECT id FROM categories WHERE parent_id=?;", (cat_id,)).fetchall()
    for child in children:
        ids.extend(_collect_category_ids(conn, child[0]))
    return ids


def get_category_path(cat_id: int) -> list:
    """مسیر کامل از ریشه تا دسته (breadcrumb)"""
    path = []
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        cid = cat_id
        while cid:
            cat = conn.execute("SELECT * FROM categories WHERE id=? LIMIT 1;", (cid,)).fetchone()
            if not cat:
                break
            path.insert(0, cat)
            cid = cat["parent_id"]
    finally:
        conn.close()
    return path


def toggle_category(cat_id: int) -> None:
    conn = _get_connection()
    try:
        conn.execute("UPDATE categories SET is_active=CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?;", (cat_id,))
        conn.commit()
    finally:
        conn.close()


def get_all_categories_flat() -> list:
    """همه دستهها برای نمایش در select box پنل"""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM categories ORDER BY parent_id NULLS FIRST, sort_order, name;").fetchall()
    finally:
        conn.close()


def add_product_with_category(category_id: int, title: str, price: int, partner_price: int | None,
                               limit_c: int, limit_p: int, description: str) -> int:
    slug = "".join(c if c.isalnum() else "_" for c in title).lower()[:40] or "product"
    conn = _get_connection()
    try:
        cat = conn.execute("SELECT slug FROM categories WHERE id=? LIMIT 1;", (category_id,)).fetchone()
        cat_slug = cat[0] if cat else str(category_id)
        cur = conn.execute(
            """INSERT INTO products (category, category_id, product_key, title, price, partner_price,
               daily_limit_customer, daily_limit_partner, description, is_active)
               VALUES (?,?,?,?,?,?,?,?,?,1);""",
            (cat_slug, category_id, slug, title.strip(), price,
             partner_price if partner_price and partner_price > 0 else None,
             limit_c, limit_p, description.strip())
        )
        pid = cur.lastrowid
        conn.commit()
        return pid
    finally:
        conn.close()


# ========= USERS (Broadcast) =========

def upsert_user(user_id: int, username: str | None = None, full_name: str | None = None) -> None:
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO users (user_id, username, full_name, first_seen, last_seen)
               VALUES (?,?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                 username=excluded.username,
                 full_name=excluded.full_name,
                 last_seen=excluded.last_seen;""",
            (user_id, username, full_name, now, now)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def get_broadcast_users(target: str = "all", product_id: int | None = None,
                        category_id: int | None = None) -> list[int]:
    """بازگرداندن لیست user_id برای broadcast بر اساس target"""
    conn = _get_connection()
    try:
        if target == "all":
            rows = conn.execute("SELECT user_id FROM users ORDER BY user_id;").fetchall()
        elif target == "buyers":
            rows = conn.execute("SELECT DISTINCT user_id FROM orders ORDER BY user_id;").fetchall()
        elif target == "non_buyers":
            rows = conn.execute("""
                SELECT u.user_id FROM users u
                LEFT JOIN orders o ON u.user_id = o.user_id
                WHERE o.user_id IS NULL ORDER BY u.user_id;
            """).fetchall()
        elif target == "product" and product_id:
            rows = conn.execute(
                "SELECT DISTINCT user_id FROM orders WHERE product_id=? ORDER BY user_id;",
                (str(product_id),)
            ).fetchall()
        elif target == "category" and category_id:
            rows = conn.execute("""
                SELECT DISTINCT o.user_id FROM orders o
                JOIN products p ON CAST(o.product_id AS INTEGER) = p.id
                WHERE p.category_id=? ORDER BY o.user_id;
            """, (category_id,)).fetchall()
        else:
            rows = []
        return [int(r[0]) for r in rows]
    finally:
        conn.close()


def get_users_stats() -> dict:
    conn = _get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
        buyers = conn.execute("SELECT COUNT(DISTINCT user_id) FROM orders;").fetchone()[0]
        return {"total": total, "buyers": buyers, "non_buyers": total - buyers}
    finally:
        conn.close()


# ========= TICKET MESSAGES =========

def save_ticket_message(ticket_id: int, sender: str, text: str | None,
                         media_type: str | None = None) -> None:
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO ticket_messages (ticket_id, sender, text, media_type, created_at) VALUES (?,?,?,?,?);",
            (ticket_id, sender, text, media_type, now)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def get_ticket_messages(ticket_id: int) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY id ASC;",
            (ticket_id,)
        ).fetchall()
    finally:
        conn.close()


def get_all_tickets(status: str | None = None, limit: int = 100) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = "WHERE t.status=?" if status else ""
        params = (status, limit) if status else (limit,)
        return conn.execute(f"""
            SELECT t.*, p.title as product_title,
                   (SELECT COUNT(*) FROM ticket_messages tm WHERE tm.ticket_id=t.id) as msg_count
            FROM tickets t
            LEFT JOIN products p ON t.product_id=p.id
            {where} ORDER BY t.id DESC LIMIT ?;
        """, params).fetchall()
    finally:
        conn.close()


def get_ticket_by_id(ticket_id: int):
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT t.*, p.title as product_title
            FROM tickets t LEFT JOIN products p ON t.product_id=p.id
            WHERE t.id=? LIMIT 1;
        """, (ticket_id,)).fetchone()
    finally:
        conn.close()


def update_ticket_status(ticket_id: int, status: str) -> None:
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        if status == "closed":
            conn.execute(
                "UPDATE tickets SET status=?, closed_at=?, closed_by='admin' WHERE id=?;",
                (status, now, ticket_id)
            )
        else:
            conn.execute("UPDATE tickets SET status=? WHERE id=?;", (status, ticket_id))
        conn.commit()
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# TICKET SYSTEM v2
# ═══════════════════════════════════════════════════════════════════════════

TICKET_MAX_USER_MSGS = 3  # max consecutive user messages before admin must reply


def ticket_ensure_schema() -> None:
    """Create v2 ticket tables (migration-safe)."""
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL DEFAULT 'support',
                user_id INTEGER NOT NULL,
                product_id INTEGER DEFAULT 0,
                order_id INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'waiting_admin',
                user_msg_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT
            );
        """)
        # migration: add columns to old schema
        for col, typedef in [
            ("type",           "TEXT NOT NULL DEFAULT 'support'"),
            ("order_id",       "INTEGER DEFAULT 0"),
            ("user_msg_count", "INTEGER DEFAULT 0"),
            ("updated_at",     "TEXT"),
            ("feed_id",        "INTEGER DEFAULT NULL"),
            ("feed_data",      "TEXT DEFAULT NULL"),
            ("setup_status",   "TEXT DEFAULT NULL"),
        ]:
            try:
                conn.execute(f"ALTER TABLE tickets ADD COLUMN {col} {typedef};")
            except Exception:
                pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                sender TEXT NOT NULL,
                text TEXT,
                media_type TEXT,
                media_file_id TEXT,
                source TEXT NOT NULL DEFAULT 'telegram',
                created_at TEXT NOT NULL
            );
        """)
        # migration: add missing columns
        for col, typedef in [
            ("source",        "TEXT NOT NULL DEFAULT 'telegram'"),
            ("media_file_id", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE ticket_messages ADD COLUMN {col} {typedef};")
            except Exception:
                pass

        conn.commit()
    finally:
        conn.close()


def ticket_create(user_id: int, type_: str = "support",
                  product_id: int = 0, order_id: int = 0,
                  feed_id: int = None, feed_data: str = None,
                  setup_status: str = None) -> int:
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        initial_status = "waiting_info" if type_ == "product_setup" else "waiting_admin"
        if setup_status:
            initial_status = setup_status
        cur = conn.execute(
            """INSERT INTO tickets (type, user_id, product_id, order_id,
               status, setup_status, feed_id, feed_data, user_msg_count, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,0,?,?);""",
            (type_, user_id, product_id, order_id,
             initial_status, setup_status or initial_status,
             feed_id, feed_data, now, now)
        )
        ticket_id = cur.lastrowid
        conn.commit()
        return int(ticket_id)
    finally:
        conn.close()


def ticket_get(ticket_id: int):
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM tickets WHERE id=? LIMIT 1;", (ticket_id,)).fetchone()
    finally:
        conn.close()


def ticket_get_open_support(user_id: int):
    """آخرین تیکت پشتیبانی باز کاربر."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM tickets WHERE user_id=? AND type='support' AND status!='closed' "
            "ORDER BY id DESC LIMIT 1;",
            (user_id,)
        ).fetchone()
    finally:
        conn.close()


def ticket_get_open_product(user_id: int, order_id: int):
    """تیکت محصول باز برای یک سفارش خاص."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM tickets WHERE user_id=? AND order_id=? AND type='product' "
            "AND status!='closed' LIMIT 1;",
            (user_id, order_id)
        ).fetchone()
    finally:
        conn.close()


def ticket_add_message(ticket_id: int, sender: str, text: str | None,
                        media_type: str | None = None, source: str = "telegram",
                        media_file_id: str | None = None) -> int:
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        cur = conn.execute(
            "INSERT INTO ticket_messages (ticket_id, sender, text, media_type, media_file_id, source, created_at) "
            "VALUES (?,?,?,?,?,?,?);",
            (ticket_id, sender, text, media_type, media_file_id, source, now)
        )
        msg_id = cur.lastrowid
        conn.execute("UPDATE tickets SET updated_at=? WHERE id=?;", (now, ticket_id))
        conn.commit()
        return int(msg_id)
    finally:
        conn.close()


def ticket_user_sent(ticket_id: int) -> int:
    """کاربر پیام فرستاد — وضعیت و counter رو آپدیت کن. returns new count."""
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE tickets SET status='waiting_admin', "
            "user_msg_count = user_msg_count + 1, updated_at=? WHERE id=?;",
            (now, ticket_id)
        )
        conn.commit()
        row = conn.execute("SELECT user_msg_count FROM tickets WHERE id=?;", (ticket_id,)).fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def ticket_admin_replied(ticket_id: int) -> None:
    """ادمین پاسخ داد — counter ریست، وضعیت → waiting_user."""
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE tickets SET status='waiting_user', user_msg_count=0, updated_at=? WHERE id=?;",
            (now, ticket_id)
        )
        conn.commit()
    finally:
        conn.close()


def ticket_close(ticket_id: int) -> None:
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE tickets SET status='closed', closed_at=?, updated_at=? WHERE id=?;",
            (now, now, ticket_id)
        )
        conn.commit()
    finally:
        conn.close()


def ticket_get_messages(ticket_id: int) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY id ASC;", (ticket_id,)
        ).fetchall()
    finally:
        conn.close()


def ticket_count_waiting() -> int:
    """تعداد تیکتهایی که ادمین باید پاسخ بده (badge count)."""
    conn = _get_connection()
    try:
        return int(conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE status='waiting_admin';"
        ).fetchone()[0])
    finally:
        conn.close()


def ticket_get_all(status: str | None = None, type_: str | None = None,
                   limit: int = 100) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        wheres, params = [], []
        if status:
            wheres.append("t.status=?"); params.append(status)
        if type_:
            wheres.append("t.type=?"); params.append(type_)
        w = "WHERE " + " AND ".join(wheres) if wheres else ""
        params.append(limit)
        return conn.execute(f"""
            SELECT t.*,
                   (SELECT COUNT(*) FROM ticket_messages m WHERE m.ticket_id=t.id) AS msg_count,
                   (SELECT text FROM ticket_messages m WHERE m.ticket_id=t.id ORDER BY m.id DESC LIMIT 1) AS last_msg
            FROM tickets t {w}
            ORDER BY CASE t.status WHEN 'waiting_admin' THEN 0 WHEN 'waiting_user' THEN 1 ELSE 2 END,
                     t.updated_at DESC LIMIT ?;
        """, params).fetchall()
    finally:
        conn.close()


def ticket_toggle_product_chat(product_id: int) -> bool:
    """Toggle chat_enabled for a product. Returns new state."""
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE products SET chat_enabled=CASE WHEN chat_enabled=1 THEN 0 ELSE 1 END WHERE id=?;",
            (product_id,)
        )
        conn.commit()
        row = conn.execute("SELECT chat_enabled FROM products WHERE id=?;", (product_id,)).fetchone()
        return bool(row[0] if row else 0)
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# ORDER MANAGEMENT — برگشت محصول (مورد ۴)
# ═══════════════════════════════════════════════════════════════════════════

def order_get(order_id: int):
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM orders WHERE id=? LIMIT 1;", (order_id,)).fetchone()
    finally:
        conn.close()


def order_set_feed_id(order_id: int, feed_id: int) -> None:
    """ذخیره feed_id مربوط به سفارش (برای برگشت)."""
    conn = _get_connection()
    try:
        conn.execute("UPDATE orders SET feed_id=? WHERE id=?;", (int(feed_id), int(order_id)))
        conn.commit()
    finally:
        conn.close()


def order_mark_returned_advanced(
    order_id: int,
    product_action: str = "restore",   # 'restore' | 'delete'
    wallet_action: str = "none",        # 'none' | 'full' | 'custom_add' | 'custom_deduct'
    custom_amount: int = 0,
) -> dict:
    """
    برگشت پیشرفته:
    - product_action: restore (به موجودی برگرد) یا delete (حذف دائم)
    - wallet_action: none | full | custom_add | custom_deduct
    """
    from datetime import datetime as _dt
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        order = conn.execute("SELECT * FROM orders WHERE id=? LIMIT 1;", (order_id,)).fetchone()
        if not order:
            return {"ok": False, "error": "سفارش یافت نشد"}
        if (order["status"] or "active") == "returned":
            return {"ok": False, "error": "این سفارش قبلاً برگشت خورده"}

        price = int(order["price"] or 0)

        # feed_id
        try:
            feed_id = order["feed_id"]
        except Exception:
            feed_id = None

        conn.execute("""
            CREATE TABLE IF NOT EXISTS delivery_messages (
                feed_id INTEGER PRIMARY KEY, order_id INTEGER,
                chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, created_at TEXT NOT NULL
            );
        """)
        if not feed_id:
            dm = conn.execute("SELECT feed_id FROM delivery_messages WHERE order_id=? LIMIT 1;", (order_id,)).fetchone()
            if dm:
                feed_id = dm["feed_id"]

        # پیام تحویل
        chat_id = message_id = None
        if feed_id:
            dmsg = conn.execute("SELECT chat_id,message_id FROM delivery_messages WHERE feed_id=? LIMIT 1;", (feed_id,)).fetchone()
            if dmsg:
                chat_id, message_id = dmsg["chat_id"], dmsg["message_id"]

        # تکلیف محصول فید
        if feed_id:
            if product_action == "restore":
                conn.execute("UPDATE product_feed SET delivered=0, order_id=NULL, delivered_at=NULL WHERE id=?;", (int(feed_id),))
            else:  # delete
                conn.execute("DELETE FROM product_feed WHERE id=?;", (int(feed_id),))

        # تکلیف کیفپول
        wallet_delta = 0
        if wallet_action == "full":
            wallet_delta = price
        elif wallet_action == "custom_add":
            wallet_delta = abs(custom_amount)
        elif wallet_action == "custom_deduct":
            wallet_delta = -abs(custom_amount)

        if wallet_delta != 0:
            user_id = order["user_id"]
            existing = conn.execute("SELECT balance FROM wallets WHERE user_id=?;", (user_id,)).fetchone()
            if existing:
                new_bal = max(0, int(existing["balance"]) + wallet_delta)
                conn.execute("UPDATE wallets SET balance=?, updated_at=datetime('now') WHERE user_id=?;", (new_bal, user_id))
            else:
                new_bal = max(0, wallet_delta)
                conn.execute("INSERT INTO wallets (user_id, balance, updated_at) VALUES (?,?,datetime('now'));", (user_id, new_bal))

        now = _dt.utcnow().isoformat()
        conn.execute("UPDATE orders SET status='returned', returned_at=? WHERE id=?;", (now, order_id))
        conn.commit()

        return {
            "ok": True, "feed_id": feed_id, "product_id": order["product_id"],
            "chat_id": chat_id, "message_id": message_id,
            "user_id": order["user_id"], "title": order["title"], "price": price,
            "wallet_delta": wallet_delta,
        }
    except Exception as ex:
        conn.rollback()
        return {"ok": False, "error": str(ex)[:100]}
    finally:
        conn.close()


def order_mark_returned(order_id: int) -> dict:
    """Backward compat — restore to inventory, no wallet change."""
    return order_mark_returned_advanced(order_id, product_action="restore", wallet_action="none")
    """
    برگشت محصول:
      - وضعیت سفارش → 'returned'
      - اگر feed_id موجود باشد، آیتم فید به delivered=0 برمیگردد (موجودی +1)
    return: {ok, feed_id, product_id, chat_id, message_id, user_id, title}
    """
    from datetime import datetime as _dt
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        order = conn.execute("SELECT * FROM orders WHERE id=? LIMIT 1;", (order_id,)).fetchone()
        if not order:
            return {"ok": False, "error": "سفارش یافت نشد"}
        if (order["status"] or "active") == "returned":
            return {"ok": False, "error": "این سفارش قبلاً برگشت خورده"}

        feed_id = order["feed_id"] if "feed_id" in order.keys() else None

        # اطمینان از وجود جدول delivery_messages
        conn.execute("""
            CREATE TABLE IF NOT EXISTS delivery_messages (
                feed_id INTEGER PRIMARY KEY,
                order_id INTEGER,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
        """)

        # اگر feed_id در orders نبود، از delivery_messages بگیر
        if not feed_id:
            dm = conn.execute(
                "SELECT feed_id FROM delivery_messages WHERE order_id=? LIMIT 1;", (order_id,)
            ).fetchone()
            if dm:
                feed_id = dm["feed_id"]

        # پیام تحویل در چت کاربر
        chat_id = message_id = None
        if feed_id:
            dmsg = conn.execute(
                "SELECT chat_id, message_id FROM delivery_messages WHERE feed_id=? LIMIT 1;", (feed_id,)
            ).fetchone()
            if dmsg:
                chat_id = dmsg["chat_id"]
                message_id = dmsg["message_id"]

        # بازگرداندن موجودی: feed item → delivered=0
        if feed_id:
            conn.execute("UPDATE product_feed SET delivered=0 WHERE id=?;", (int(feed_id),))

        # علامتگذاری سفارش بهعنوان برگشتی
        now = _dt.utcnow().isoformat()
        conn.execute("UPDATE orders SET status='returned', returned_at=? WHERE id=?;", (now, order_id))
        conn.commit()

        return {
            "ok": True,
            "feed_id": feed_id,
            "product_id": order["product_id"],
            "chat_id": chat_id,
            "message_id": message_id,
            "user_id": order["user_id"],
            "title": order["title"],
        }
    finally:
        conn.close()


def order_update(order_id: int, title: str = None, price: int = None) -> bool:
    """ویرایش عنوان/قیمت سفارش."""
    conn = _get_connection()
    try:
        sets, params = [], []
        if title is not None:
            sets.append("title=?"); params.append(title)
        if price is not None:
            sets.append("price=?"); params.append(int(price))
        if not sets:
            return False
        params.append(int(order_id))
        conn.execute(f"UPDATE orders SET {', '.join(sets)} WHERE id=?;", params)
        conn.commit()
        return True
    finally:
        conn.close()


def order_stats_returned() -> dict:
    """آمار سفارشهای برگشتی."""
    conn = _get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM orders;").fetchone()[0]
        returned = conn.execute("SELECT COUNT(*) FROM orders WHERE status='returned';").fetchone()[0]
        returned_sum = conn.execute(
            "SELECT COALESCE(SUM(price),0) FROM orders WHERE status='returned';"
        ).fetchone()[0]
        return {"total": int(total), "returned": int(returned), "returned_sum": int(returned_sum)}
    finally:
        conn.close()


def feed_returned_count(product_id: int) -> int:
    """تعداد آیتمهای برگشتی یک محصول (سفارشهای returned با این product_id)."""
    conn = _get_connection()
    try:
        return int(conn.execute(
            "SELECT COUNT(*) FROM orders WHERE product_id=? AND status='returned';",
            (str(product_id),)
        ).fetchone()[0])
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── کد تخفیف ───────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_discount_table():
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                code            TEXT    UNIQUE NOT NULL COLLATE NOCASE,
                type            TEXT    NOT NULL DEFAULT 'percent',  -- 'percent' | 'fixed' | 'wallet'
                value           INTEGER NOT NULL DEFAULT 0,
                max_value       INTEGER DEFAULT 0,    -- سقف تخفیف (برای درصدی) — 0=نامحدود
                min_amount      INTEGER DEFAULT 0,    -- حداقل مبلغ سفارش
                max_uses        INTEGER DEFAULT 0,    -- 0=نامحدود
                max_uses_per_user INTEGER DEFAULT 0,  -- 0=نامحدود
                used_count      INTEGER DEFAULT 0,
                product_id      INTEGER DEFAULT NULL, -- NULL=همه محصولات
                category_id     INTEGER DEFAULT NULL, -- NULL=همه دستهها
                first_buy_only  INTEGER DEFAULT 0,    -- فقط اولین خرید
                vip_only        INTEGER DEFAULT 0,    -- فقط کاربران VIP
                starts_at       TEXT    DEFAULT NULL,
                expires_at      TEXT    DEFAULT NULL,
                is_active       INTEGER DEFAULT 1,
                created_at      TEXT    DEFAULT (datetime('now','localtime')),
                description     TEXT    DEFAULT ''
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS discount_usage (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                code_id     INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                order_id    INTEGER,
                used_at     TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY(code_id) REFERENCES discount_codes(id)
            );
        """)
        # ─── مهاجرت: افزودن ستون‌های جدید به جدول‌های قدیمی ───────────────
        try:
            existing = {r[1] for r in conn.execute("PRAGMA table_info(discount_codes);").fetchall()}
            for col, decl in [
                ("max_value",         "INTEGER DEFAULT 0"),
                ("min_amount",        "INTEGER DEFAULT 0"),
                ("max_uses",          "INTEGER DEFAULT 0"),
                ("max_uses_per_user", "INTEGER DEFAULT 0"),
                ("used_count",        "INTEGER DEFAULT 0"),
                ("product_id",        "INTEGER DEFAULT NULL"),
                ("category_id",       "INTEGER DEFAULT NULL"),
                ("first_buy_only",    "INTEGER DEFAULT 0"),
                ("vip_only",          "INTEGER DEFAULT 0"),
                ("starts_at",         "TEXT DEFAULT NULL"),
                ("expires_at",        "TEXT DEFAULT NULL"),
                ("is_active",         "INTEGER DEFAULT 1"),
                ("description",       "TEXT DEFAULT ''"),
            ]:
                if col not in existing:
                    conn.execute(f"ALTER TABLE discount_codes ADD COLUMN {col} {decl};")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


def validate_discount(code: str, product_id: int = None, category_id: int = None,
                      amount: int = 0, user_id: int = None) -> dict:
    """اعتبارسنجی جامع کد تخفیف."""
    ensure_discount_table()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    now = datetime.utcnow().isoformat()
    try:
        row = conn.execute(
            "SELECT * FROM discount_codes WHERE code=? COLLATE NOCASE AND is_active=1 LIMIT 1;",
            (code.strip(),)
        ).fetchone()
        if not row:
            return {"valid": False, "error": "کد تخفیف یافت نشد یا غیرفعال است"}
        if row["max_uses"] > 0 and row["used_count"] >= row["max_uses"]:
            return {"valid": False, "error": "ظرفیت این کد تمام شده است"}
        if row["starts_at"] and row["starts_at"] > now:
            return {"valid": False, "error": "این کد هنوز فعال نشده است"}
        if row["expires_at"] and row["expires_at"] < now:
            return {"valid": False, "error": "کد تخفیف منقضی شده است"}
        if row["min_amount"] > 0 and amount < row["min_amount"]:
            return {"valid": False, "error": f"حداقل مبلغ سفارش {row['min_amount']:,} تومان است"}
        if row["product_id"] and product_id and int(row["product_id"]) != int(product_id):
            return {"valid": False, "error": "این کد برای محصول دیگری است"}
        if row["category_id"] and category_id and int(row["category_id"]) != int(category_id):
            return {"valid": False, "error": "این کد برای دستهبندی دیگری است"}
        if user_id:
            if row["max_uses_per_user"] > 0:
                uses = conn.execute(
                    "SELECT COUNT(*) FROM discount_usage WHERE code_id=? AND user_id=?;",
                    (row["id"], user_id)
                ).fetchone()[0]
                if uses >= row["max_uses_per_user"]:
                    return {"valid": False, "error": "سقف استفاده شما از این کد تمام شده است"}
            if row["first_buy_only"]:
                has_order = conn.execute(
                    "SELECT COUNT(*) FROM orders WHERE CAST(user_id AS INTEGER)=? "
                    "AND COALESCE(status,'active') != 'returned';",
                    (int(user_id),)
                ).fetchone()[0]
                if has_order > 0:
                    return {"valid": False, "error": "این کد فقط برای اولین خرید است"}
            if row["vip_only"]:
                # VIP = کاربر دارای برچسب VIP یا همکار تأییدشده
                is_vip = False
                try:
                    tag_row = conn.execute(
                        "SELECT tags FROM users WHERE CAST(user_id AS INTEGER)=?;", (int(user_id),)
                    ).fetchone()
                    if tag_row and tag_row["tags"] and "vip" in str(tag_row["tags"]).lower():
                        is_vip = True
                except Exception:
                    pass
                if not is_vip:
                    try:
                        pr = conn.execute(
                            "SELECT 1 FROM partners WHERE CAST(tg_user_id AS INTEGER)=? AND status='approved' LIMIT 1;",
                            (int(user_id),)
                        ).fetchone()
                        is_vip = bool(pr)
                    except Exception:
                        pass
                if not is_vip:
                    return {"valid": False, "error": "این کد مخصوص کاربران VIP است"}

        # محاسبه تخفیف
        if row["type"] == "percent":
            discount = int(amount * row["value"] / 100)
            if row["max_value"] > 0:
                discount = min(discount, row["max_value"])
        elif row["type"] == "fixed":
            discount = row["value"]
        elif row["type"] == "wallet":
            discount = row["value"]  # اعتبار کیفپول
        else:
            discount = 0
        discount = min(discount, amount)

        return {
            "valid": True, "discount_amount": discount, "type": row["type"],
            "value": row["value"], "code_id": row["id"], "error": None,
            "description": row["description"] or ""
        }
    finally:
        conn.close()


def use_discount(code_id: int, user_id: int = None, order_id: int = None):
    """ثبت استفاده از کد."""
    conn = _get_connection()
    try:
        conn.execute("UPDATE discount_codes SET used_count=used_count+1 WHERE id=?;", (code_id,))
        if user_id:
            conn.execute(
                "INSERT INTO discount_usage (code_id,user_id,order_id) VALUES (?,?,?);",
                (code_id, user_id, order_id)
            )
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── اشتراک موجودی ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_subscription_table():
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_subscriptions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                created_at TEXT    DEFAULT (datetime('now','localtime')),
                notified   INTEGER DEFAULT 0,
                UNIQUE(user_id, product_id)
            );
        """)
        conn.commit()
    finally:
        conn.close()


def subscribe_stock(user_id: int, product_id: int) -> bool:
    """ثبت اشتراک موجودی. True=جدید، False=قبلاً ثبت شده."""
    ensure_subscription_table()
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO stock_subscriptions (user_id, product_id) VALUES (?,?);",
            (user_id, product_id)
        )
        changed = conn.execute("SELECT changes();").fetchone()[0]
        conn.commit()
        return bool(changed)
    finally:
        conn.close()


def get_stock_subscribers(product_id: int) -> list:
    """لیست کاربرانی که اشتراک این محصول دارند و هنوز نوتیف نگرفتن."""
    ensure_subscription_table()
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT user_id FROM stock_subscriptions WHERE product_id=? AND notified=0;",
            (product_id,)
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def mark_subscriptions_notified(product_id: int):
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE stock_subscriptions SET notified=1 WHERE product_id=?;",
            (product_id,)
        )
        conn.commit()
    finally:
        conn.close()


def reset_subscriptions_on_restock(product_id: int):
    """وقتی موجودی اومد، اشتراکها رو reset کن برای دور بعد."""
    conn = _get_connection()
    try:
        conn.execute(
            "DELETE FROM stock_subscriptions WHERE product_id=? AND notified=1;",
            (product_id,)
        )
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── پشتیبانی اختصاصی محصول ─────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_product_support_schema():
    """اضافه کردن ستونهای setup به products."""
    conn = _get_connection()
    try:
        for col, default in [
            ("support_after_purchase", "INTEGER DEFAULT 0"),
            ("setup_message", "TEXT DEFAULT ''"),
        ]:
            try:
                conn.execute(f"ALTER TABLE products ADD COLUMN {col} {default};")
                conn.commit()
            except Exception:
                pass
    finally:
        conn.close()


def get_product_support_flag(product_id: int) -> bool:
    conn = _get_connection()
    try:
        row = conn.execute("SELECT support_after_purchase FROM products WHERE id=? LIMIT 1;", (product_id,)).fetchone()
        return bool(row and row[0])
    except Exception:
        return False
    finally:
        conn.close()


def get_product_setup_message(product_id: int) -> str:
    """متن راهنما برای کاربر هنگام راهاندازی محصول."""
    conn = _get_connection()
    try:
        row = conn.execute("SELECT setup_message FROM products WHERE id=? LIMIT 1;", (product_id,)).fetchone()
        return (row[0] or "").strip() if row else ""
    except Exception:
        return ""
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── سیستم معرفی کاربران ─────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_referral_schema():
    conn = _get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS referral_settings (
                id              INTEGER PRIMARY KEY DEFAULT 1,
                reward_amount   INTEGER DEFAULT 5000,
                is_active       INTEGER DEFAULT 1,
                updated_at      TEXT    DEFAULT (datetime('now','localtime'))
            );
            INSERT OR IGNORE INTO referral_settings (id) VALUES (1);

            CREATE TABLE IF NOT EXISTS referrals (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id     INTEGER NOT NULL,
                referred_id     INTEGER NOT NULL UNIQUE,
                rewarded        INTEGER DEFAULT 0,
                reward_amount   INTEGER DEFAULT 0,
                first_order_id  INTEGER DEFAULT NULL,
                created_at      TEXT    DEFAULT (datetime('now','localtime')),
                rewarded_at     TEXT    DEFAULT NULL
            );
        """)
        conn.commit()
    finally:
        conn.close()


def get_referral_settings() -> dict:
    ensure_referral_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM referral_settings WHERE id=1;").fetchone()
        return dict(row) if row else {"reward_amount": 5000, "is_active": 1}
    finally:
        conn.close()


def register_referral(referrer_id: int, referred_id: int) -> bool:
    """ثبت معرفی — False اگه قبلاً ثبت شده."""
    ensure_referral_schema()
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?,?);",
            (referrer_id, referred_id)
        )
        changed = conn.execute("SELECT changes();").fetchone()[0]
        conn.commit()
        return bool(changed)
    finally:
        conn.close()


def process_referral_reward(referred_id: int, order_id: int) -> dict:
    """
    اگه کاربر اولین خریدش رو کرده و معرف داره → پاداش بده.
    Returns: {rewarded, referrer_id, amount}
    """
    ensure_referral_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        ref = conn.execute(
            "SELECT * FROM referrals WHERE referred_id=? AND rewarded=0 LIMIT 1;",
            (referred_id,)
        ).fetchone()
        if not ref:
            return {"rewarded": False}

        settings = conn.execute("SELECT * FROM referral_settings WHERE id=1;").fetchone()
        amount   = int(settings["reward_amount"] if settings else 5000)

        # اضافه کردن به کیفپول همکاری (نه کیفپول اصلی)
        credit_partner_wallet(ref["referrer_id"], amount,
                              note=f"پاداش معرفی — سفارش #{order_id}")

        conn.execute("""UPDATE referrals SET rewarded=1, reward_amount=?, first_order_id=?,
            rewarded_at=datetime('now') WHERE id=?;""", (amount, order_id, ref["id"]))
        conn.commit()
        return {"rewarded": True, "referrer_id": ref["referrer_id"], "amount": amount}
    finally:
        conn.close()


def process_referral_commission(referred_id: int, order_id: int, order_price: int) -> dict:
    """
    پورسانت روی «هر» خرید زیرمجموعه — بر اساس سطح معرف:
      1. اگر سطح معرف مبلغ ثابت (commission_fixed) دارد → همان مبلغ
      2. وگرنه اگر سطح درصد (commission_percent) دارد → درصدی از مبلغ سفارش
      3. وگرنه → درصد عمومی از partner_commission
    Returns: {paid, referrer_id, amount, tier_name}
    """
    ensure_referral_schema()
    ensure_partner_tiers_extended()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        ref = conn.execute(
            "SELECT referrer_id FROM referrals WHERE referred_id=? LIMIT 1;",
            (referred_id,)
        ).fetchone()
        if not ref:
            return {"paid": False}
        referrer_id = int(ref["referrer_id"])

        # تنظیمات عمومی پورسانت
        gset = conn.execute("SELECT * FROM partner_commission WHERE id=1;").fetchone()
        if gset and not int(gset["is_active"] or 0):
            return {"paid": False}
        global_pct = float(gset["percent"] if gset else 5.0)
        min_order  = int(gset["min_order"] if gset else 0)
        max_payout = int(gset["max_payout"] if gset else 0)

        if min_order > 0 and order_price < min_order:
            return {"paid": False}

        # سطح معرف
        try:
            order_count = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE CAST(user_id AS INTEGER)=? AND buyer_type='partner';",
                (referrer_id,)
            ).fetchone()[0]
        except Exception:
            order_count = 0
        tier = conn.execute("""
            SELECT * FROM partner_tiers WHERE min_orders <= ?
            ORDER BY min_orders DESC LIMIT 1;
        """, (order_count,)).fetchone()

        tier_name  = tier["name"] if tier else "—"
        tier_fixed = int(tier["commission_fixed"] or 0) if tier and "commission_fixed" in tier.keys() else 0
        tier_pct   = float(tier["commission_percent"] or 0) if tier and "commission_percent" in tier.keys() else 0.0

        if tier_fixed > 0:
            amount = tier_fixed
        elif tier_pct > 0:
            amount = int(order_price * tier_pct / 100)
        else:
            amount = int(order_price * global_pct / 100)

        if max_payout > 0:
            amount = min(amount, max_payout)
        if amount <= 0:
            return {"paid": False}
    finally:
        conn.close()

    wallet = credit_referrer(referrer_id, amount,
                             note=f"پاداش فروش — سفارش #{order_id} (سطح {tier_name})")
    return {"paid": True, "referrer_id": referrer_id, "amount": amount,
            "tier_name": tier_name, "wallet": wallet}


def get_referral_stats(referrer_id: int) -> dict:
    ensure_referral_schema()
    conn = _get_connection()
    try:
        total    = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?;", (referrer_id,)).fetchone()[0]
        rewarded = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND rewarded=1;", (referrer_id,)).fetchone()[0]
        earned   = conn.execute("SELECT COALESCE(SUM(reward_amount),0) FROM referrals WHERE referrer_id=? AND rewarded=1;", (referrer_id,)).fetchone()[0]
        return {"total": total, "rewarded": rewarded, "earned": int(earned)}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── سیستم فروشندگان ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

SELLER_LEVELS = [
    {"id":1,"name":"برنز",  "emoji":"🥉","min_sales":0,  "commission":50000},
    {"id":2,"name":"نقره",  "emoji":"🥈","min_sales":5,  "commission":70000},
    {"id":3,"name":"طلایی", "emoji":"🥇","min_sales":20, "commission":100000},
    {"id":4,"name":"الماس", "emoji":"💎","min_sales":50, "commission":300000},
]

def ensure_seller_schema():
    conn = _get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS seller_levels (
                id              INTEGER PRIMARY KEY,
                name            TEXT    NOT NULL,
                emoji           TEXT    DEFAULT '',
                min_sales       INTEGER DEFAULT 0,
                commission      INTEGER DEFAULT 50000,
                updated_at      TEXT    DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS sellers (
                user_id         INTEGER PRIMARY KEY,
                code            TEXT    UNIQUE NOT NULL,
                level_id        INTEGER DEFAULT 1,
                status          TEXT    DEFAULT 'active',
                total_sales     INTEGER DEFAULT 0,
                total_earned    INTEGER DEFAULT 0,
                wallet_balance  INTEGER DEFAULT 0,
                custom_commission INTEGER DEFAULT NULL,
                invited_users   INTEGER DEFAULT 0,
                created_at      TEXT    DEFAULT (datetime('now','localtime')),
                updated_at      TEXT    DEFAULT (datetime('now','localtime')),
                FOREIGN KEY(level_id) REFERENCES seller_levels(id)
            );

            CREATE TABLE IF NOT EXISTS seller_commissions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id       INTEGER NOT NULL,
                order_id        INTEGER NOT NULL,
                buyer_id        INTEGER NOT NULL,
                product_id      INTEGER,
                product_title   TEXT    DEFAULT '',
                order_amount    INTEGER DEFAULT 0,
                commission      INTEGER DEFAULT 0,
                level_id        INTEGER DEFAULT 1,
                status          TEXT    DEFAULT 'earned',
                created_at      TEXT    DEFAULT (datetime('now','localtime')),
                paid_at         TEXT    DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS seller_payouts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id       INTEGER NOT NULL,
                amount          INTEGER NOT NULL,
                status          TEXT    DEFAULT 'pending',
                card_number     TEXT    DEFAULT '',
                card_name       TEXT    DEFAULT '',
                requested_at    TEXT    DEFAULT (datetime('now','localtime')),
                processed_at    TEXT    DEFAULT NULL,
                admin_note      TEXT    DEFAULT ''
            );
        """)
        # seed default levels
        for lv in SELLER_LEVELS:
            conn.execute("""INSERT OR IGNORE INTO seller_levels (id,name,emoji,min_sales,commission)
                VALUES (?,?,?,?,?);""", (lv["id"],lv["name"],lv["emoji"],lv["min_sales"],lv["commission"]))
        conn.commit()
    finally:
        conn.close()


def _gen_seller_code() -> str:
    import random, string
    while True:
        code = "STLAND-" + "".join(random.choices(string.digits, k=4))
        conn = _get_connection()
        exists = conn.execute("SELECT 1 FROM sellers WHERE code=?;", (code,)).fetchone()
        conn.close()
        if not exists:
            return code


def seller_activate(user_id: int) -> str:
    """فعالسازی فروشنده — کد میسازه."""
    ensure_seller_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        existing = conn.execute("SELECT code FROM sellers WHERE user_id=?;", (user_id,)).fetchone()
        if existing:
            return existing["code"]
        code = _gen_seller_code()
        conn.execute("INSERT INTO sellers (user_id,code) VALUES (?,?);", (user_id, code))
        conn.commit()
        return code
    finally:
        conn.close()


def seller_get(user_id: int) -> dict | None:
    ensure_seller_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("""
            SELECT s.*, sl.name as level_name, sl.emoji as level_emoji,
                   sl.commission as level_commission, sl.min_sales as level_min,
                   (SELECT sl2.min_sales FROM seller_levels sl2 WHERE sl2.id=s.level_id+1 LIMIT 1) as next_min
            FROM sellers s JOIN seller_levels sl ON sl.id=s.level_id
            WHERE s.user_id=?;
        """, (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def seller_is_active(user_id: int) -> bool:
    ensure_seller_schema()
    conn = _get_connection()
    try:
        row = conn.execute("SELECT status FROM sellers WHERE user_id=? AND status='active';", (user_id,)).fetchone()
        return bool(row)
    finally:
        conn.close()


def seller_get_commission(seller_id: int, product_id: int = None) -> int:
    """محاسبه پورسانت — اختصاصی اگه داشت، وگرنه سطح."""
    ensure_seller_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        s = conn.execute("""
            SELECT s.custom_commission, sl.commission
            FROM sellers s JOIN seller_levels sl ON sl.id=s.level_id
            WHERE s.user_id=? AND s.status='active';
        """, (seller_id,)).fetchone()
        if not s:
            return 0
        return int(s["custom_commission"] if s["custom_commission"] else s["commission"])
    finally:
        conn.close()


def seller_record_sale(seller_id: int, order_id: int, buyer_id: int,
                        product_id: int, product_title: str, order_amount: int) -> int:
    """ثبت فروش و پورسانت — returns commission amount."""
    ensure_seller_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        s = conn.execute("SELECT * FROM sellers WHERE user_id=? AND status='active';", (seller_id,)).fetchone()
        if not s:
            return 0
        commission = seller_get_commission(seller_id, product_id)
        now = datetime.utcnow().isoformat()
        conn.execute("""
            INSERT INTO seller_commissions
                (seller_id,order_id,buyer_id,product_id,product_title,order_amount,commission,level_id,created_at)
            VALUES (?,?,?,?,?,?,?,?,?);
        """, (seller_id, order_id, buyer_id, product_id, product_title, order_amount, commission, s["level_id"], now))

        new_sales = int(s["total_sales"]) + 1
        new_earned = int(s["total_earned"]) + commission
        new_wallet = int(s["wallet_balance"]) + commission

        # بررسی ارتقای سطح
        new_level = s["level_id"]
        levels = conn.execute("SELECT * FROM seller_levels ORDER BY min_sales DESC;").fetchall()
        for lv in levels:
            if new_sales >= lv["min_sales"]:
                new_level = lv["id"]
                break

        conn.execute("""
            UPDATE sellers SET total_sales=?, total_earned=?, wallet_balance=?,
            level_id=?, invited_users=invited_users+1, updated_at=? WHERE user_id=?;
        """, (new_sales, new_earned, new_wallet, new_level, now, seller_id))
        conn.commit()
        return commission
    finally:
        conn.close()


def seller_request_payout(seller_id: int, amount: int, card_number: str, card_name: str) -> dict:
    ensure_seller_schema()
    conn = _get_connection()
    try:
        s = conn.execute("SELECT wallet_balance FROM sellers WHERE user_id=?;", (seller_id,)).fetchone()
        if not s or int(s[0]) < amount:
            return {"ok": False, "error": "موجودی کافی نیست"}
        conn.execute("""INSERT INTO seller_payouts (seller_id,amount,card_number,card_name)
            VALUES (?,?,?,?);""", (seller_id, amount, card_number, card_name))
        conn.execute("UPDATE sellers SET wallet_balance=wallet_balance-? WHERE user_id=?;", (amount, seller_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def seller_list_all() -> list:
    ensure_seller_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT s.*, sl.name as level_name, sl.emoji as level_emoji,
                   u.full_name, u.username
            FROM sellers s
            JOIN seller_levels sl ON sl.id=s.level_id
            LEFT JOIN users u ON u.user_id=s.user_id
            ORDER BY s.total_sales DESC;
        """).fetchall()
    finally:
        conn.close()


def seller_list_payouts(status: str = None) -> list:
    ensure_seller_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = f"WHERE p.status='{status}'" if status else ""
        return conn.execute(f"""
            SELECT p.*, s.code, u.full_name, u.username
            FROM seller_payouts p
            JOIN sellers s ON s.user_id=p.seller_id
            LEFT JOIN users u ON u.user_id=p.seller_id
            {where} ORDER BY p.id DESC LIMIT 200;
        """).fetchall()
    finally:
        conn.close()


def seller_update(seller_id: int, **kwargs):
    ensure_seller_schema()
    conn = _get_connection()
    try:
        allowed = {"status","level_id","custom_commission","wallet_balance"}
        sets = ", ".join(f"{k}=?" for k in kwargs if k in allowed)
        vals = [v for k,v in kwargs.items() if k in allowed]
        if sets:
            conn.execute(f"UPDATE sellers SET {sets}, updated_at=datetime('now') WHERE user_id=?;",
                         vals + [seller_id])
            conn.commit()
    finally:
        conn.close()


def seller_payout_update(payout_id: int, status: str, note: str = ""):
    ensure_seller_schema()
    conn = _get_connection()
    try:
        p = conn.execute("SELECT seller_id, amount, status FROM seller_payouts WHERE id=?;", (payout_id,)).fetchone()
        if not p:
            return
        if p[2] != "pending":
            return
        conn.execute("UPDATE seller_payouts SET status=?,admin_note=?,processed_at=datetime('now') WHERE id=?;",
                     (status, note, payout_id))
        # اگه رد شد پول برگرده
        if status == "rejected":
            conn.execute("UPDATE sellers SET wallet_balance=wallet_balance+? WHERE user_id=?;", (p[1], p[0]))
        conn.commit()
    finally:
        conn.close()


def seller_get_levels() -> list:
    ensure_seller_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM seller_levels ORDER BY id;").fetchall()
    finally:
        conn.close()


# ── درخواست فروشندگی (جایگزین درخواست نمایندگی) ──────────────────────────────

def seller_apply(user_id: int, full_name: str, phone: str, city: str, shop_name: str, note: str = "") -> bool:
    """ثبت درخواست فروشندگی — ذخیره در partner_requests برای بررسی ادمین."""
    try:
        upsert_partner_request(
            tg_user_id=user_id, phone=phone, username="",
            full_name=full_name, note=note, city=city, shop_name=shop_name
        )
        return True
    except Exception:
        return False


def seller_pending_applications() -> list:
    """درخواستهای در انتظار فروشندگی."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT p.*, u.username
            FROM partners p
            LEFT JOIN users u ON u.user_id=p.tg_user_id
            WHERE p.status='pending'
            ORDER BY p.created_at DESC LIMIT 100;
        """).fetchall()
    except Exception:
        return []
    finally:
        conn.close()


def seller_approve_application(user_id: int) -> str:
    """تأیید درخواست: approve در partners + activate در sellers."""
    approve_partner(user_id)
    code = seller_activate(user_id)
    return code


# ─── ستونهای اضافی کاربران (یادداشت، برچسب، مسدودسازی) ──────────────────────

def ensure_user_extra_schema():
    conn = _get_connection()
    try:
        for col, default in [
            ("admin_note", "TEXT DEFAULT ''"),
            ("tags",       "TEXT DEFAULT ''"),
            ("is_blocked", "INTEGER DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {default};")
                conn.commit()
            except Exception:
                pass
    finally:
        conn.close()


def get_user_full(user_id: int) -> dict | None:
    ensure_user_extra_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("""
            SELECT u.*,
                   COALESCE(w.balance,0) AS balance,
                   (SELECT COUNT(*) FROM orders o WHERE CAST(o.user_id AS INTEGER)=u.user_id AND o.status='active') AS order_count,
                   (SELECT 1 FROM partners p WHERE p.tg_user_id=u.user_id AND p.status='approved' LIMIT 1) AS is_partner
            FROM users u
            LEFT JOIN wallets w ON w.user_id=u.user_id
            WHERE u.user_id=?;
        """, (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_user_note(user_id: int, note: str, tags: str = None):
    ensure_user_extra_schema()
    conn = _get_connection()
    try:
        if tags is not None:
            conn.execute("UPDATE users SET admin_note=?, tags=? WHERE user_id=?;", (note, tags, user_id))
        else:
            conn.execute("UPDATE users SET admin_note=? WHERE user_id=?;", (note, user_id))
        conn.commit()
    finally:
        conn.close()


def toggle_user_block(user_id: int) -> bool:
    ensure_user_extra_schema()
    conn = _get_connection()
    try:
        cur = conn.execute("SELECT is_blocked FROM users WHERE user_id=?;", (user_id,)).fetchone()
        new_val = 0 if (cur and cur[0]) else 1
        conn.execute("UPDATE users SET is_blocked=? WHERE user_id=?;", (new_val, user_id))
        conn.commit()
        return bool(new_val)
    finally:
        conn.close()


def get_user_orders(user_id: int, limit: int = 20) -> list:
    """سفارش‌های کاربر — سفارش‌های برگشت‌خورده نمایش داده نمی‌شوند."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT * FROM orders
            WHERE CAST(user_id AS INTEGER)=?
              AND COALESCE(status,'active') != 'returned'
            ORDER BY id DESC LIMIT ?;
        """, (user_id, limit)).fetchall()
    finally:
        conn.close()


def get_user_tickets(user_id: int, limit: int = 20) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT * FROM tickets WHERE user_id=?
            ORDER BY id DESC LIMIT ?;
        """, (user_id, limit)).fetchall()
    except Exception:
        return []
    finally:
        conn.close()


# ─── سیستم سطوح و تنظیمات همکاری ────────────────────────────────────────────

def ensure_partner_system_schema():
    """جداول سطوح همکاری + تنظیمات پورسانت."""
    conn = _get_connection()
    try:
        # سطوح همکاری
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partner_tiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                icon TEXT DEFAULT '🥉',
                min_orders INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0
            );
        """)
        # تنظیمات پورسانت همکاری
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partner_commission (
                id INTEGER PRIMARY KEY CHECK (id=1),
                percent REAL DEFAULT 5.0,
                min_order INTEGER DEFAULT 0,
                max_payout INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()

        # سطوح پیشفرض اگه خالی بود
        cnt = conn.execute("SELECT COUNT(*) FROM partner_tiers;").fetchone()[0]
        if cnt == 0:
            defaults = [
                ("برنز", "🥉", 0, 1),
                ("نقرهای", "🥈", 10, 2),
                ("طلایی", "🥇", 30, 3),
                ("الماس", "💎", 70, 4),
            ]
            conn.executemany(
                "INSERT INTO partner_tiers (name,icon,min_orders,sort_order) VALUES (?,?,?,?);",
                defaults
            )
            conn.commit()

        # تنظیمات پیشفرض
        c2 = conn.execute("SELECT COUNT(*) FROM partner_commission;").fetchone()[0]
        if c2 == 0:
            conn.execute("INSERT INTO partner_commission (id,percent,min_order,max_payout,is_active) VALUES (1,5.0,0,0,1);")
            conn.commit()
    finally:
        conn.close()


def get_partner_tiers() -> list:
    ensure_partner_system_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM partner_tiers ORDER BY sort_order, min_orders;").fetchall()
    finally:
        conn.close()


def save_partner_tier(tier_id, name, icon, min_orders):
    ensure_partner_system_schema()
    conn = _get_connection()
    try:
        if tier_id:
            conn.execute("UPDATE partner_tiers SET name=?,icon=?,min_orders=? WHERE id=?;",
                         (name, icon, min_orders, tier_id))
        else:
            mx = conn.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM partner_tiers;").fetchone()[0]
            conn.execute("INSERT INTO partner_tiers (name,icon,min_orders,sort_order) VALUES (?,?,?,?);",
                         (name, icon, min_orders, mx))
        conn.commit()
    finally:
        conn.close()


def delete_partner_tier(tier_id):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM partner_tiers WHERE id=?;", (tier_id,))
        conn.commit()
    finally:
        conn.close()


def get_partner_commission() -> dict:
    ensure_partner_system_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM partner_commission WHERE id=1;").fetchone()
        return dict(row) if row else {"percent": 5.0, "min_order": 0, "max_payout": 0, "is_active": 1}
    finally:
        conn.close()


def save_partner_commission(percent, min_order, max_payout, is_active):
    ensure_partner_system_schema()
    conn = _get_connection()
    try:
        conn.execute("""UPDATE partner_commission
            SET percent=?,min_order=?,max_payout=?,is_active=?,updated_at=datetime('now') WHERE id=1;""",
            (percent, min_order, max_payout, is_active))
        conn.commit()
    finally:
        conn.close()


def get_partner_order_count(tg_user_id: int) -> int:
    """تعداد خریدهای همکاری (با قیمت همکار)."""
    conn = _get_connection()
    try:
        n = conn.execute("""
            SELECT COUNT(*) FROM orders
            WHERE CAST(user_id AS INTEGER)=? AND buyer_type='partner';
        """, (tg_user_id,)).fetchone()[0]
        return int(n or 0)
    except Exception:
        return 0
    finally:
        conn.close()


def get_partner_tier_for(order_count: int) -> dict:
    """سطح فعلی بر اساس تعداد خرید — شامل photo_file_id."""
    ensure_partner_tiers_extended()
    tiers = get_partner_tiers()
    current = None
    for t in tiers:
        if order_count >= t["min_orders"]:
            current = t
    if current is None and tiers:
        current = tiers[0]
    return dict(current) if current else {"name": "برنز", "icon": "🥉", "min_orders": 0, "photo_file_id": ""}


def get_referral_stats_for(referrer_id: int) -> dict:
    """آمار کلی زیرمجموعههای یک معرف."""
    conn = _get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?;", (referrer_id,)).fetchone()[0]
        rewarded = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND rewarded=1;", (referrer_id,)).fetchone()[0]
        total_reward = conn.execute("SELECT COALESCE(SUM(reward_amount),0) FROM referrals WHERE referrer_id=? AND rewarded=1;", (referrer_id,)).fetchone()[0]
        return {"total": int(total or 0), "rewarded": int(rewarded or 0), "total_reward": int(total_reward or 0)}
    except Exception:
        return {"total": 0, "rewarded": 0, "total_reward": 0}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── کیفپول همکاری ────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_partner_wallet_schema():
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partner_wallets (
                user_id   INTEGER PRIMARY KEY,
                balance   INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partner_transactions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                type       TEXT NOT NULL,
                amount     INTEGER NOT NULL,
                note       TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partner_payouts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                amount       INTEGER NOT NULL,
                status       TEXT DEFAULT 'pending',
                admin_note   TEXT DEFAULT '',
                created_at   TEXT DEFAULT (datetime('now')),
                processed_at TEXT
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partner_payout_settings (
                id            INTEGER PRIMARY KEY CHECK (id=1),
                min_amount    INTEGER DEFAULT 50000,
                max_amount    INTEGER DEFAULT 0,
                max_per_month INTEGER DEFAULT 2,
                is_active     INTEGER DEFAULT 1,
                updated_at    TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
        # پیشفرض تنظیمات تسویه
        cnt = conn.execute("SELECT COUNT(*) FROM partner_payout_settings;").fetchone()[0]
        if cnt == 0:
            conn.execute("INSERT INTO partner_payout_settings (id) VALUES (1);")
            conn.commit()
    finally:
        conn.close()


def get_partner_wallet_balance(user_id: int) -> int:
    ensure_partner_wallet_schema()
    conn = _get_connection()
    try:
        row = conn.execute("SELECT balance FROM partner_wallets WHERE user_id=?;", (user_id,)).fetchone()
        return int(row[0] or 0) if row else 0
    finally:
        conn.close()


def credit_partner_wallet(user_id: int, amount: int, note: str = "") -> int:
    """واریز پورسانت به کیفپول همکاری. Returns new balance."""
    ensure_partner_wallet_schema()
    conn = _get_connection()
    try:
        existing = conn.execute("SELECT balance FROM partner_wallets WHERE user_id=?;", (user_id,)).fetchone()
        if existing:
            conn.execute("UPDATE partner_wallets SET balance=balance+?, updated_at=datetime('now') WHERE user_id=?;",
                         (amount, user_id))
        else:
            conn.execute("INSERT INTO partner_wallets (user_id, balance) VALUES (?,?);", (user_id, amount))
        conn.execute("INSERT INTO partner_transactions (user_id, type, amount, note) VALUES (?,?,?,?);",
                     (user_id, "credit", amount, note))
        conn.commit()
        row = conn.execute("SELECT balance FROM partner_wallets WHERE user_id=?;", (user_id,)).fetchone()
        return int(row[0] or 0)
    finally:
        conn.close()


def transfer_partner_to_main(user_id: int, amount: int) -> dict:
    """انتقال از کیفپول همکاری به کیفپول اصلی."""
    ensure_partner_wallet_schema()
    conn = _get_connection()
    try:
        bal = conn.execute("SELECT balance FROM partner_wallets WHERE user_id=?;", (user_id,)).fetchone()
        current = int(bal[0] or 0) if bal else 0
        if current < amount:
            return {"ok": False, "error": "موجودی کافی نیست"}
        if amount <= 0:
            return {"ok": False, "error": "مبلغ نامعتبر"}
        # کسر از partner wallet
        conn.execute("UPDATE partner_wallets SET balance=balance-?, updated_at=datetime('now') WHERE user_id=?;",
                     (amount, user_id))
        conn.execute("INSERT INTO partner_transactions (user_id,type,amount,note) VALUES (?,?,?,?);",
                     (user_id, "transfer_out", amount, "انتقال به کیفپول اصلی"))
        # واریز به کیفپول اصلی
        existing = conn.execute("SELECT balance FROM wallets WHERE user_id=?;", (user_id,)).fetchone()
        if existing:
            conn.execute("UPDATE wallets SET balance=balance+?, updated_at=datetime('now') WHERE user_id=?;",
                         (amount, user_id))
        else:
            conn.execute("INSERT INTO wallets (user_id, balance, updated_at) VALUES (?,?,datetime('now'));",
                         (user_id, amount))
        conn.commit()
        return {"ok": True, "transferred": amount}
    finally:
        conn.close()


def get_partner_payout_settings() -> dict:
    ensure_partner_wallet_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM partner_payout_settings WHERE id=1;").fetchone()
        if row:
            return dict(row)
        return {"min_amount": 50000, "max_amount": 0, "max_per_month": 2, "is_active": 1}
    finally:
        conn.close()


def save_partner_payout_settings(min_amount, max_amount, max_per_month, is_active):
    ensure_partner_wallet_schema()
    conn = _get_connection()
    try:
        conn.execute("""UPDATE partner_payout_settings
            SET min_amount=?, max_amount=?, max_per_month=?, is_active=?, updated_at=datetime('now')
            WHERE id=1;""", (min_amount, max_amount, max_per_month, is_active))
        conn.commit()
    finally:
        conn.close()


def request_partner_payout(user_id: int, amount: int) -> dict:
    """ثبت درخواست تسویه."""
    ensure_partner_wallet_schema()
    settings = get_partner_payout_settings()
    if not settings.get("is_active"):
        return {"ok": False, "error": "تسویه در حال حاضر غیرفعال است"}
    bal = get_partner_wallet_balance(user_id)
    if amount > bal:
        return {"ok": False, "error": "موجودی کافی نیست"}
    min_a = int(settings.get("min_amount") or 0)
    max_a = int(settings.get("max_amount") or 0)
    if min_a and amount < min_a:
        return {"ok": False, "error": f"حداقل مبلغ تسویه {min_a:,} تومان است"}
    if max_a and amount > max_a:
        return {"ok": False, "error": f"حداکثر مبلغ تسویه {max_a:,} تومان است"}
    # بررسی تعداد ماهانه
    max_pm = int(settings.get("max_per_month") or 0)
    if max_pm:
        conn = _get_connection()
        try:
            cnt = conn.execute("""
                SELECT COUNT(*) FROM partner_payouts
                WHERE user_id=? AND status IN ('pending','approved')
                AND strftime('%Y-%m', created_at)=strftime('%Y-%m','now');
            """, (user_id,)).fetchone()[0]
        finally:
            conn.close()
        if cnt >= max_pm:
            return {"ok": False, "error": f"سقف {max_pm} درخواست در ماه تکمیل شده"}
    conn = _get_connection()
    try:
        # کسر موقت از کیفپول
        conn.execute("UPDATE partner_wallets SET balance=balance-?, updated_at=datetime('now') WHERE user_id=?;",
                     (amount, user_id))
        conn.execute("INSERT INTO partner_transactions (user_id,type,amount,note) VALUES (?,?,?,?);",
                     (user_id, "payout_request", amount, "درخواست تسویه"))
        conn.execute("INSERT INTO partner_payouts (user_id,amount,status) VALUES (?,?,'pending');",
                     (user_id, amount))
        conn.commit()
        row = conn.execute("SELECT last_insert_rowid();").fetchone()
        return {"ok": True, "payout_id": row[0]}
    finally:
        conn.close()


def process_partner_payout(payout_id: int, approve: bool, admin_note: str = "") -> dict:
    """تأیید یا رد تسویه توسط ادمین."""
    ensure_partner_wallet_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        pay = conn.execute("SELECT * FROM partner_payouts WHERE id=?;", (payout_id,)).fetchone()
        if not pay:
            return {"ok": False, "error": "درخواست یافت نشد"}
        if pay["status"] != "pending":
            return {"ok": False, "error": "درخواست قبلاً پردازش شده"}
        new_status = "approved" if approve else "rejected"
        conn.execute("""UPDATE partner_payouts SET status=?, admin_note=?, processed_at=datetime('now')
            WHERE id=?;""", (new_status, admin_note, payout_id))
        if not approve:
            # رد شد → برگردان به کیفپول
            conn.execute("UPDATE partner_wallets SET balance=balance+?, updated_at=datetime('now') WHERE user_id=?;",
                         (pay["amount"], pay["user_id"]))
            conn.execute("INSERT INTO partner_transactions (user_id,type,amount,note) VALUES (?,?,?,?);",
                         (pay["user_id"], "payout_rejected", pay["amount"], "رد تسویه — برگشت موجودی"))
        conn.commit()
        return {"ok": True, "user_id": pay["user_id"], "amount": pay["amount"], "approved": approve}
    finally:
        conn.close()


def get_partner_transactions(user_id: int, limit: int = 20) -> list:
    ensure_partner_wallet_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""SELECT * FROM partner_transactions WHERE user_id=?
            ORDER BY id DESC LIMIT ?;""", (user_id, limit)).fetchall()
    finally:
        conn.close()


def get_partner_payouts(user_id: int = None, status: str = "", limit: int = 50) -> list:
    ensure_partner_wallet_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        wheres, params = [], []
        if user_id:
            wheres.append("p.user_id=?"); params.append(user_id)
        if status:
            wheres.append("p.status=?"); params.append(status)
        where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        params.append(limit)
        return conn.execute(f"""
            SELECT p.*, u.full_name, u.username
            FROM partner_payouts p
            LEFT JOIN users u ON u.user_id=p.user_id
            {where_sql}
            ORDER BY p.id DESC LIMIT ?;
        """, params).fetchall()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── دفتر یادداشت مدیران ────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_admin_notes_schema():
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_notes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                author     TEXT NOT NULL,
                text       TEXT NOT NULL,
                status     TEXT DEFAULT 'open',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_note_replies (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id    INTEGER NOT NULL,
                author     TEXT NOT NULL,
                text       TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
    finally:
        conn.close()


def get_admin_notes(status: str = "") -> list:
    ensure_admin_notes_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = "WHERE n.status=?" if status else ""
        params = (status,) if status else ()
        return conn.execute(f"""
            SELECT n.*,
                   (SELECT COUNT(*) FROM admin_note_replies r WHERE r.note_id=n.id) AS reply_count
            FROM admin_notes n {where}
            ORDER BY n.status='open' DESC, n.updated_at DESC;
        """, params).fetchall()
    finally:
        conn.close()


def get_admin_note(note_id: int) -> dict | None:
    ensure_admin_notes_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        n = conn.execute("SELECT * FROM admin_notes WHERE id=?;", (note_id,)).fetchone()
        if not n:
            return None
        replies = conn.execute(
            "SELECT * FROM admin_note_replies WHERE note_id=? ORDER BY id;", (note_id,)
        ).fetchall()
        return {"note": dict(n), "replies": [dict(r) for r in replies]}
    finally:
        conn.close()


def create_admin_note(author: str, text: str) -> int:
    ensure_admin_notes_schema()
    conn = _get_connection()
    try:
        cur = conn.execute("INSERT INTO admin_notes (author, text) VALUES (?,?);", (author, text))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def add_admin_note_reply(note_id: int, author: str, text: str):
    ensure_admin_notes_schema()
    conn = _get_connection()
    try:
        conn.execute("INSERT INTO admin_note_replies (note_id,author,text) VALUES (?,?,?);",
                     (note_id, author, text))
        conn.execute("UPDATE admin_notes SET updated_at=datetime('now') WHERE id=?;", (note_id,))
        conn.commit()
    finally:
        conn.close()


def toggle_admin_note_status(note_id: int) -> str:
    ensure_admin_notes_schema()
    conn = _get_connection()
    try:
        cur = conn.execute("SELECT status FROM admin_notes WHERE id=?;", (note_id,)).fetchone()
        new_status = "done" if (cur and cur[0] == "open") else "open"
        conn.execute("UPDATE admin_notes SET status=?,updated_at=datetime('now') WHERE id=?;",
                     (new_status, note_id))
        conn.commit()
        return new_status
    finally:
        conn.close()


def delete_admin_note(note_id: int):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM admin_note_replies WHERE note_id=?;", (note_id,))
        conn.execute("DELETE FROM admin_notes WHERE id=?;", (note_id,))
        conn.commit()
    finally:
        conn.close()


# ─── ستونهای اضافی partner_tiers ────────────────────────────────────────────

def ensure_partner_tiers_extended():
    ensure_partner_system_schema()  # ابتدا جدول پایه ساخته شود
    conn = _get_connection()
    try:
        for col, default in [
            ("commission_percent", "REAL DEFAULT 0"),
            ("commission_fixed",  "INTEGER DEFAULT 0"),
            ("color",             "TEXT DEFAULT '#6B7280'"),
            ("description",       "TEXT DEFAULT ''"),
            ("photo_file_id",     "TEXT DEFAULT ''"),
        ]:
            try:
                conn.execute(f"ALTER TABLE partner_tiers ADD COLUMN {col} {default};")
                conn.commit()
            except Exception:
                pass
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── اطلاعات بانکی همکار ────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_partner_bank_schema():
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partner_bank_info (
                user_id     INTEGER PRIMARY KEY,
                full_name   TEXT DEFAULT '',
                card_number TEXT DEFAULT '',
                iban        TEXT DEFAULT '',
                updated_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
        # migration: ستون آدرس
        try:
            conn.execute("ALTER TABLE partner_bank_info ADD COLUMN address TEXT DEFAULT '';")
            conn.commit()
        except Exception:
            pass
    finally:
        conn.close()


def get_partner_bank_info(user_id: int) -> dict | None:
    ensure_partner_bank_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM partner_bank_info WHERE user_id=?;", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_partner_bank_info(user_id: int, full_name: str, card_number: str, iban: str):
    ensure_partner_bank_schema()
    conn = _get_connection()
    try:
        existing = conn.execute("SELECT user_id FROM partner_bank_info WHERE user_id=?;", (user_id,)).fetchone()
        if existing:
            conn.execute("UPDATE partner_bank_info SET full_name=?,card_number=?,iban=?,updated_at=datetime('now') WHERE user_id=?;",
                         (full_name, card_number, iban, user_id))
        else:
            conn.execute("INSERT INTO partner_bank_info (user_id,full_name,card_number,iban) VALUES (?,?,?,?);",
                         (user_id, full_name, card_number, iban))
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── حسابداری موجودی (feed batch) ───────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_feed_batch_schema():
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feed_batches (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id      INTEGER NOT NULL,
                purchase_price  INTEGER DEFAULT 0,
                side_cost       INTEGER DEFAULT 0,
                item_count      INTEGER DEFAULT 0,
                notes           TEXT DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now'))
            );
        """)
        try:
            conn.execute("ALTER TABLE product_feed ADD COLUMN batch_id INTEGER DEFAULT NULL;")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


def create_feed_batch(product_id: int, purchase_price: int, side_cost: int, item_count: int, notes: str = "") -> int:
    ensure_feed_batch_schema()
    conn = _get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO feed_batches (product_id,purchase_price,side_cost,item_count,notes) VALUES (?,?,?,?,?);",
            (product_id, purchase_price, side_cost, item_count, notes)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def link_batch_to_feed(product_id: int, batch_id: int, offset: int, count: int):
    """لینک کردن آخرین count آیتم به batch_id."""
    ensure_feed_batch_schema()
    conn = _get_connection()
    try:
        conn.execute("""
            UPDATE product_feed SET batch_id=?
            WHERE id IN (
                SELECT id FROM product_feed
                WHERE product_id=? AND batch_id IS NULL AND delivered=0
                ORDER BY id DESC LIMIT ?
            );
        """, (batch_id, product_id, count))
        conn.commit()
    finally:
        conn.close()


def get_financial_report() -> dict:
    """گزارش مالی کامل فروشگاه."""
    conn = _get_connection()
    try:
        # مجموع فروش
        total_sales = conn.execute(
            "SELECT COALESCE(SUM(price),0) FROM orders WHERE status='active';"
        ).fetchone()[0]
        # مجموع هزینه خرید
        total_purchase = conn.execute(
            "SELECT COALESCE(SUM(fb.purchase_price * fb.item_count + fb.side_cost),0) FROM feed_batches fb;"
        ).fetchone()[0]
        # پورسانت پرداختی
        total_commission = conn.execute(
            "SELECT COALESCE(SUM(reward_amount),0) FROM referrals WHERE rewarded=1;"
        ).fetchone()[0]
        # تسویههای تأیید شده
        total_payouts = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM partner_payouts WHERE status='approved';"
        ).fetchone()[0]
        # فروش مستقیم (غیر همکار)
        direct_sales = conn.execute(
            "SELECT COALESCE(SUM(price),0) FROM orders WHERE status='active' AND (buyer_type!='partner' OR buyer_type IS NULL);"
        ).fetchone()[0]
        # فروش همکاری
        partner_sales = conn.execute(
            "SELECT COALESCE(SUM(price),0) FROM orders WHERE status='active' AND buyer_type='partner';"
        ).fetchone()[0]

        gross_profit   = int(total_sales or 0) - int(total_purchase or 0)
        net_profit     = gross_profit - int(total_commission or 0)

        return {
            "total_sales":       int(total_sales or 0),
            "total_purchase":    int(total_purchase or 0),
            "gross_profit":      gross_profit,
            "net_profit":        net_profit,
            "direct_sales":      int(direct_sales or 0),
            "partner_sales":     int(partner_sales or 0),
            "total_commission":  int(total_commission or 0),
            "total_payouts":     int(total_payouts or 0),
            "store_profit":      net_profit - int(total_payouts or 0),
        }
    except Exception:
        return {}
    finally:
        conn.close()


# ─── migration آدرس در partner_bank_info ────────────────────────────────────

def ensure_partner_bank_address():
    conn = _get_connection()
    try:
        conn.execute("ALTER TABLE partner_bank_info ADD COLUMN address TEXT DEFAULT '';")
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# ─── تنظیمات تسویه — فیلدهای اضافی ────────────────────────────────────────

def ensure_payout_settings_extended():
    conn = _get_connection()
    try:
        for col, default in [
            ("review_hours",        "INTEGER DEFAULT 48"),
            ("guide_text",          "TEXT DEFAULT ''"),
            ("approval_message",    "TEXT DEFAULT ''"),
            ("rejection_message",   "TEXT DEFAULT ''"),
        ]:
            try:
                conn.execute(f"ALTER TABLE partner_payout_settings ADD COLUMN {col} {default};")
                conn.commit()
            except Exception:
                pass
    finally:
        conn.close()


def get_payout_settings_full() -> dict:
    ensure_payout_settings_extended()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM partner_payout_settings WHERE id=1;").fetchone()
        if row:
            return dict(row)
        return {
            "min_amount": 50000, "max_amount": 0, "max_per_month": 2,
            "is_active": 1, "review_hours": 48,
            "guide_text": "", "approval_message": "", "rejection_message": "",
        }
    finally:
        conn.close()


def save_payout_settings_full(data: dict):
    ensure_payout_settings_extended()
    conn = _get_connection()
    try:
        conn.execute("""UPDATE partner_payout_settings
            SET min_amount=?, max_amount=?, max_per_month=?, is_active=?,
                review_hours=?, guide_text=?, approval_message=?, rejection_message=?,
                updated_at=datetime('now')
            WHERE id=1;""",
            (data.get("min_amount",50000), data.get("max_amount",0),
             data.get("max_per_month",2), data.get("is_active",1),
             data.get("review_hours",48), data.get("guide_text",""),
             data.get("approval_message",""), data.get("rejection_message","")))
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── سیستم حسابداری (Light Accounting) ──────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_accounting_schema():
    """ساخت جداول حسابداری."""
    conn = _get_connection()
    try:
        # هزینهها
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                category    TEXT DEFAULT 'سایر',
                amount      INTEGER NOT NULL DEFAULT 0,
                expense_date TEXT DEFAULT (date('now')),
                description TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        # دستهبندی هزینهها
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expense_categories (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  TEXT UNIQUE NOT NULL
            );
        """)
        # دستههای پیشفرض
        defaults = ['تبلیغات','سرور و هاست','دامنه','حقوق','اینترنت','تجهیزات','مالیات','سایر']
        for cat in defaults:
            try:
                conn.execute("INSERT OR IGNORE INTO expense_categories (name) VALUES (?);", (cat,))
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()


def get_accounting_kpis(date_from: str = "", date_to: str = "") -> dict:
    """محاسبه KPI های اصلی حسابداری."""
    conn = _get_connection()
    try:
        where_order = ""
        where_batch = ""
        params = []
        if date_from:
            where_order += f" AND date(o.created_at) >= '{date_from}'"
            where_batch  += f" AND date(fb.created_at) >= '{date_from}'"
        if date_to:
            where_order += f" AND date(o.created_at) <= '{date_to}'"
            where_batch  += f" AND date(fb.created_at) <= '{date_to}'"

        # فروش کل
        total_sales = conn.execute(
            f"SELECT COALESCE(SUM(price),0) FROM orders o WHERE status='active'{where_order};"
        ).fetchone()[0]

        # فروش امروز
        today_sales = conn.execute(
            "SELECT COALESCE(SUM(price),0) FROM orders WHERE status='active' AND date(created_at)=date('now');"
        ).fetchone()[0]

        # فروش این ماه
        month_sales = conn.execute(
            "SELECT COALESCE(SUM(price),0) FROM orders WHERE status='active' AND strftime('%Y-%m',created_at)=strftime('%Y-%m','now');"
        ).fetchone()[0]

        # تعداد سفارش
        total_orders = conn.execute(
            f"SELECT COUNT(*) FROM orders o WHERE status='active'{where_order};"
        ).fetchone()[0]

        # هزینه خرید — فقط برای آیتمهای تحویلشده (sold)
        try:
            total_cost = conn.execute("""
                SELECT COALESCE(SUM(
                    CASE WHEN fb.item_count > 0
                    THEN (fb.purchase_price + CAST(fb.side_cost AS REAL)/fb.item_count)
                    ELSE fb.purchase_price END
                ), 0)
                FROM product_feed pf
                JOIN feed_batches fb ON pf.batch_id = fb.id
                WHERE pf.delivered = 1;
            """).fetchone()[0]
        except Exception:
            total_cost = 0

        # پورسانت پرداختی
        commission_q = "SELECT COALESCE(SUM(reward_amount),0) FROM referrals WHERE rewarded=1"
        if date_from:
            commission_q += f" AND date(rewarded_at)>='{date_from}'" if 'rewarded_at' in [r[1] for r in conn.execute("PRAGMA table_info(referrals);").fetchall()] else ""
        total_commission = conn.execute(commission_q + ";").fetchone()[0]

        # هزینههای ثبتشده
        exp_q = "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE 1=1"
        if date_from: exp_q += f" AND expense_date>='{date_from}'"
        if date_to:   exp_q += f" AND expense_date<='{date_to}'"
        total_expenses = conn.execute(exp_q + ";").fetchone()[0]

        # تسویههای انجام شده
        try:
            payouts_done = conn.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM partner_payouts WHERE status='approved';").fetchone()
            payout_count = int(payouts_done[0] or 0)
            payout_total = int(payouts_done[1] or 0)
        except Exception:
            payout_count = payout_total = 0

        # موجودی انبار
        try:
            stock_count = conn.execute("SELECT COUNT(*) FROM product_feed WHERE delivered=0;").fetchone()[0]
        except Exception:
            stock_count = 0

        gross_profit = int(total_sales or 0) - int(total_cost or 0)
        net_profit   = gross_profit - int(total_commission or 0) - int(total_expenses or 0)

        avg_profit = int(net_profit / total_orders) if total_orders else 0
        margin_pct = round((net_profit / total_sales) * 100, 1) if total_sales else 0

        return {
            "today_sales":       int(today_sales or 0),
            "month_sales":       int(month_sales or 0),
            "total_sales":       int(total_sales or 0),
            "total_orders":      int(total_orders or 0),
            "total_cost":        int(total_cost or 0),
            "total_commission":  int(total_commission or 0),
            "total_expenses":    int(total_expenses or 0),
            "gross_profit":      gross_profit,
            "net_profit":        net_profit,
            "payout_count":      payout_count,
            "payout_total":      payout_total,
            "stock_count":       int(stock_count or 0),
            "avg_profit":        avg_profit,
            "margin_pct":        margin_pct,
        }
    finally:
        conn.close()


def get_product_accounting(limit: int = 20) -> list:
    """گزارش حسابداری به تفکیک محصول."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT
                p.id, p.title,
                COUNT(o.id)              AS sale_count,
                COALESCE(SUM(o.price),0) AS total_revenue,
                COALESCE((
                    SELECT AVG(fb.purchase_price) FROM feed_batches fb WHERE fb.product_id=p.id
                ),0)                     AS avg_cost,
                COALESCE((
                    SELECT fb.purchase_price FROM feed_batches fb WHERE fb.product_id=p.id ORDER BY fb.id DESC LIMIT 1
                ),0)                     AS last_cost,
                COALESCE((
                    SELECT COUNT(*) FROM product_feed pf WHERE pf.product_id=p.id AND pf.delivered=0
                ),0)                     AS stock
            FROM products p
            LEFT JOIN orders o ON o.title=p.title AND o.status='active'
            GROUP BY p.id
            ORDER BY total_revenue DESC
            LIMIT ?;
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_partner_accounting(limit: int = 20) -> list:
    """گزارش حسابداری به تفکیک همکار."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT
                u.user_id, u.full_name, u.username,
                COUNT(o.id)              AS sale_count,
                COALESCE(SUM(o.price),0) AS total_sales,
                COALESCE((
                    SELECT SUM(r.reward_amount) FROM referrals r
                    WHERE r.referrer_id=u.user_id AND r.rewarded=1
                ),0)                     AS commission_paid
            FROM users u
            JOIN partners pt ON pt.tg_user_id=u.user_id AND pt.status='approved'
            LEFT JOIN orders o ON CAST(o.user_id AS INTEGER)=u.user_id AND o.status='active' AND o.buyer_type='partner'
            GROUP BY u.user_id
            ORDER BY total_sales DESC
            LIMIT ?;
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_cashflow(date_from: str = "", date_to: str = "", limit: int = 100) -> list:
    """گردش مالی — همه رویدادهای مالی."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = "WHERE 1=1"
        if date_from: where += f" AND date(created_at)>='{date_from}'"
        if date_to:   where += f" AND date(created_at)<='{date_to}'"
        rows = conn.execute(f"""
            SELECT * FROM (
                SELECT created_at, 'فروش' as type, title as description,
                       price as amount, 'income' as direction
                FROM orders WHERE status='active'
                UNION ALL
                SELECT created_at, 'شارژ کیفپول' as type,
                       CAST(user_id AS TEXT) as description,
                       amount, 'income' as direction
                FROM zarinpal_transactions WHERE status='success'
                UNION ALL
                SELECT created_at, 'هزینه' as type,
                       title || ' (' || category || ')' as description,
                       amount, 'expense' as direction
                FROM expenses
                UNION ALL
                SELECT created_at, 'پورسانت' as type,
                       CAST(referrer_id AS TEXT) as description,
                       reward_amount as amount, 'expense' as direction
                FROM referrals WHERE rewarded=1
            ) {where}
            ORDER BY created_at DESC LIMIT ?;
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── CRUD هزینهها ────────────────────────────────────────────────────────────

def get_expenses(date_from="", date_to="", category="", limit=100) -> list:
    conn = _get_connection(); conn.row_factory = sqlite3.Row
    try:
        where = "WHERE 1=1"
        if date_from: where += f" AND expense_date>='{date_from}'"
        if date_to:   where += f" AND expense_date<='{date_to}'"
        if category:  where += f" AND category='{category.replace(chr(39),'')}'"
        return [dict(r) for r in conn.execute(
            f"SELECT * FROM expenses {where} ORDER BY expense_date DESC, id DESC LIMIT ?;", (limit,)
        ).fetchall()]
    finally: conn.close()


def create_expense(title: str, category: str, amount: int,
                   expense_date: str = "", description: str = "") -> int:
    ensure_accounting_schema()
    conn = _get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO expenses (title,category,amount,expense_date,description) VALUES (?,?,?,?,?);",
            (title, category, amount, expense_date or datetime.utcnow().strftime('%Y-%m-%d'), description)
        )
        conn.commit(); return cur.lastrowid
    finally: conn.close()


def delete_expense(eid: int):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM expenses WHERE id=?;", (eid,))
        conn.commit()
    finally: conn.close()


def get_expense_categories() -> list:
    ensure_accounting_schema()
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT name FROM expense_categories ORDER BY id;").fetchall()
        return [r[0] for r in rows]
    finally: conn.close()


def add_expense_category(name: str):
    ensure_accounting_schema()
    conn = _get_connection()
    try:
        conn.execute("INSERT OR IGNORE INTO expense_categories (name) VALUES (?);", (name,))
        conn.commit()
    finally: conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── فاز ۱: امتیازدهی + FAQ ──────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_ratings_schema():
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product_ratings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                order_id    INTEGER NOT NULL,
                product_id  INTEGER NOT NULL,
                rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                comment     TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(order_id)
            );
        """)
        conn.commit()
    finally:
        conn.close()


def save_rating(user_id: int, order_id: int, product_id: int, rating: int, comment: str = "") -> bool:
    ensure_ratings_schema()
    conn = _get_connection()
    try:
        conn.execute("""INSERT OR IGNORE INTO product_ratings
            (user_id, order_id, product_id, rating, comment) VALUES (?,?,?,?,?);""",
            (user_id, order_id, product_id, rating, comment))
        conn.commit()
        return conn.execute("SELECT changes();").fetchone()[0] > 0
    finally:
        conn.close()


def get_product_rating(product_id: int) -> dict:
    """میانگین امتیاز و تعداد نظرات یک محصول."""
    ensure_ratings_schema()
    conn = _get_connection()
    try:
        row = conn.execute("""
            SELECT COUNT(*) as cnt, ROUND(AVG(rating),1) as avg
            FROM product_ratings WHERE product_id=?;
        """, (product_id,)).fetchone()
        return {"count": int(row[0] or 0), "avg": float(row[1] or 0)}
    finally:
        conn.close()


def get_product_ratings_list(product_id: int, limit: int = 20) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("""
            SELECT pr.rating, pr.comment, pr.created_at, u.full_name
            FROM product_ratings pr
            LEFT JOIN users u ON u.user_id=pr.user_id
            WHERE pr.product_id=? ORDER BY pr.id DESC LIMIT ?;
        """, (product_id, limit)).fetchall()]
    finally:
        conn.close()


def has_rated_order(order_id: int) -> bool:
    ensure_ratings_schema()
    conn = _get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM product_ratings WHERE order_id=?;", (order_id,)
        ).fetchone()[0] > 0
    finally:
        conn.close()


# ─── FAQ ─────────────────────────────────────────────────────────────────────

def ensure_faq_schema():
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product_faqs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  INTEGER NOT NULL,
                question    TEXT NOT NULL,
                answer      TEXT NOT NULL,
                sort_order  INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
    finally:
        conn.close()


def get_product_faqs(product_id: int) -> list:
    ensure_faq_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM product_faqs WHERE product_id=? ORDER BY sort_order, id;",
            (product_id,)
        ).fetchall()]
    finally:
        conn.close()


def add_product_faq(product_id: int, question: str, answer: str) -> int:
    ensure_faq_schema()
    conn = _get_connection()
    try:
        mx = conn.execute(
            "SELECT COALESCE(MAX(sort_order),0)+1 FROM product_faqs WHERE product_id=?;",
            (product_id,)
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO product_faqs (product_id,question,answer,sort_order) VALUES (?,?,?,?);",
            (product_id, question, answer, mx)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_product_faq(faq_id: int):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM product_faqs WHERE id=?;", (faq_id,))
        conn.commit()
    finally:
        conn.close()


# ─── Maintenance Mode ─────────────────────────────────────────────────────────

_MAINT_CACHE = {"t": 0.0, "v": False}

def get_maintenance_mode() -> bool:
    import time as _t
    now = _t.time()
    if now - _MAINT_CACHE["t"] < 10:
        return _MAINT_CACHE["v"]
    _MAINT_CACHE["t"] = now
    conn = _get_connection()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS bot_config
            (key TEXT PRIMARY KEY, value TEXT);""")
        row = conn.execute("SELECT value FROM bot_config WHERE key='maintenance';").fetchone()
        _MAINT_CACHE["v"] = bool(row and row[0] == "1")
        return _MAINT_CACHE["v"]
    except Exception:
        return False
    finally:
        conn.close()


def set_maintenance_mode(enabled: bool):
    _MAINT_CACHE["t"] = 0.0
    conn = _get_connection()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS bot_config
            (key TEXT PRIMARY KEY, value TEXT);""")
        conn.execute("INSERT OR REPLACE INTO bot_config (key,value) VALUES ('maintenance',?);",
                     ("1" if enabled else "0",))
        conn.commit()
    finally:
        conn.close()


# ─── رسیدهای کارتبهکارت ────────────────────────────────────────────────────

def ensure_card_receipts_schema():
    conn = _get_connection()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS card_receipts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            amount      INTEGER NOT NULL,
            file_id     TEXT NOT NULL,
            status      TEXT DEFAULT 'pending',
            admin_note  TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now'))
        );""")
        conn.commit()
    finally:
        conn.close()


def save_card_receipt(user_id: int, amount: int, file_id: str) -> int:
    ensure_card_receipts_schema()
    conn = _get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO card_receipts (user_id,amount,file_id) VALUES (?,?,?);",
            (user_id, amount, file_id))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_card_receipts(status: str = "pending") -> list:
    ensure_card_receipts_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = f"WHERE r.status='{status}'" if status else ""
        return [dict(r) for r in conn.execute(f"""
            SELECT r.*, u.full_name, u.username
            FROM card_receipts r
            LEFT JOIN users u ON u.user_id=r.user_id
            {where} ORDER BY r.id DESC LIMIT 100;
        """).fetchall()]
    finally:
        conn.close()


def update_card_receipt(rid: int, status: str, note: str = "", amount: int = None):
    conn = _get_connection()
    try:
        if amount is not None:
            conn.execute("""UPDATE card_receipts SET status=?,admin_note=?,amount=?,updated_at=datetime('now')
                WHERE id=?;""", (status, note, amount, rid))
        else:
            conn.execute("""UPDATE card_receipts SET status=?,admin_note=?,updated_at=datetime('now')
                WHERE id=?;""", (status, note, rid))
        conn.commit()
    finally:
        conn.close()


# ─── آرشیو و حذف تیکتها ──────────────────────────────────────────────────────

def ensure_ticket_archive_schema():
    conn = _get_connection()
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tickets);").fetchall()]
        if "archived" not in cols:
            conn.execute("ALTER TABLE tickets ADD COLUMN archived INTEGER DEFAULT 0;")
        conn.commit()
    finally:
        conn.close()


def archive_ticket(tid: int):
    ensure_ticket_archive_schema()
    conn = _get_connection()
    try:
        conn.execute("UPDATE tickets SET archived=1 WHERE id=?;", (tid,))
        conn.commit()
    finally:
        conn.close()


def unarchive_ticket(tid: int):
    ensure_ticket_archive_schema()
    conn = _get_connection()
    try:
        conn.execute("UPDATE tickets SET archived=0 WHERE id=?;", (tid,))
        conn.commit()
    finally:
        conn.close()


def delete_ticket(tid: int):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM ticket_messages WHERE ticket_id=?;", (tid,))
        conn.execute("DELETE FROM tickets WHERE id=?;", (tid,))
        conn.commit()
    finally:
        conn.close()


# ─── حذف رسیدهای کارتبهکارت ─────────────────────────────────────────────────

def delete_card_receipt(rid: int):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM card_receipts WHERE id=?;", (rid,))
        conn.commit()
    finally:
        conn.close()


def delete_all_card_receipts():
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM card_receipts;")
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── 🚀 لایه رشد و فروش — Flash Sale، بازگردانی، لیدربرد، نظرات، رمزارز ────
# ══════════════════════════════════════════════════════════════════════════════

import json as _json
import time as _time

_CFG_CACHE: dict = {}
_CFG_TTL = 60  # ثانیه


def get_cfg(key: str, default: str = "") -> str:
    """خواندن تنظیم از bot_config با کش ۶۰ ثانیه‌ای."""
    now = _time.time()
    hit = _CFG_CACHE.get(key)
    if hit and now - hit[1] < _CFG_TTL:
        return hit[0]
    val = default
    conn = _get_connection()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS bot_config (key TEXT PRIMARY KEY, value TEXT);")
        row = conn.execute("SELECT value FROM bot_config WHERE key=?;", (key,)).fetchone()
        if row is not None and row[0] is not None:
            val = str(row[0])
    except Exception:
        pass
    finally:
        conn.close()
    _CFG_CACHE[key] = (val, now)
    return val


def set_cfg(key: str, value) -> None:
    conn = _get_connection()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS bot_config (key TEXT PRIMARY KEY, value TEXT);")
        conn.execute(
            "INSERT INTO bot_config (key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value;",
            (key, str(value)))
        conn.commit()
    finally:
        conn.close()
    _CFG_CACHE.pop(key, None)


def get_cfg_json(key: str, default: dict) -> dict:
    raw = get_cfg(key, "")
    if not raw:
        return dict(default)
    try:
        d = dict(default)
        d.update(_json.loads(raw))
        return d
    except Exception:
        return dict(default)


_GROWTH_SCHEMA_READY = False

def ensure_growth_schema():
    """جدول‌های فروش فوری و بازگردانی + مهاجرت رسیدها — فقط یک‌بار در هر پروسه."""
    global _GROWTH_SCHEMA_READY
    if _GROWTH_SCHEMA_READY:
        return
    _GROWTH_SCHEMA_READY = True
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS flash_sales (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                percent    INTEGER NOT NULL,
                starts_at  TEXT NOT NULL,
                ends_at    TEXT NOT NULL,
                is_active  INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS winback_log (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code_id INTEGER,
                sent_at TEXT DEFAULT (datetime('now','localtime'))
            );""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product_ratings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                order_id    INTEGER NOT NULL,
                product_id  INTEGER NOT NULL,
                rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                comment     TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(order_id)
            );""")
        # مهاجرت card_receipts برای رمزارز (قانون ۱۳)
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(card_receipts);").fetchall()}
            if cols:
                if "method" not in cols:
                    conn.execute("ALTER TABLE card_receipts ADD COLUMN method TEXT DEFAULT 'card';")
                if "txid" not in cols:
                    conn.execute("ALTER TABLE card_receipts ADD COLUMN txid TEXT DEFAULT '';")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


# ─── ۳) فروش فوری (Flash Sale) ────────────────────────────────────────────

def create_flash_sale(product_id: int, percent: int, hours: int) -> int:
    ensure_growth_schema()
    conn = _get_connection()
    try:
        # فقط یک فروش فعال برای هر محصول
        conn.execute("UPDATE flash_sales SET is_active=0 WHERE product_id=?;", (product_id,))
        cur = conn.execute("""
            INSERT INTO flash_sales (product_id, percent, starts_at, ends_at)
            VALUES (?,?, datetime('now','localtime'), datetime('now','localtime', ?));
        """, (product_id, max(1, min(90, int(percent))), f"+{int(hours)} hours"))
        conn.commit()
        try: flash_map_invalidate()
        except Exception: pass
        return cur.lastrowid
    finally:
        conn.close()


def deactivate_flash_sale(sale_id: int):
    conn = _get_connection()
    try:
        conn.execute("UPDATE flash_sales SET is_active=0 WHERE id=?;", (sale_id,))
        conn.commit()
        try: flash_map_invalidate()
        except Exception: pass
    finally:
        conn.close()


def get_flash_sale(product_id: int):
    """فروش فوری فعال محصول — dict یا None."""
    ensure_growth_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("""
            SELECT *, CAST((julianday(ends_at)-julianday('now','localtime'))*24*60 AS INTEGER) AS mins_left
            FROM flash_sales
            WHERE product_id=? AND is_active=1
              AND datetime('now','localtime') BETWEEN starts_at AND ends_at
            ORDER BY id DESC LIMIT 1;
        """, (product_id,)).fetchone()
        if not row:
            return None
        mins = max(0, int(row["mins_left"] or 0))
        if mins >= 60:
            left = f"{mins//60} ساعت و {mins%60} دقیقه"
        else:
            left = f"{mins} دقیقه"
        return {"id": row["id"], "percent": int(row["percent"]),
                "ends_at": row["ends_at"], "mins_left": mins, "left_str": left}
    finally:
        conn.close()


def apply_flash_price(product_id: int, price: int):
    """(قیمت نهایی، فروش‌فوری یا None)"""
    try:
        sale = get_flash_sale(product_id)
        if sale:
            return max(0, int(price) - int(price) * sale["percent"] // 100), sale
    except Exception:
        pass
    return int(price), None


def list_flash_sales(limit: int = 30) -> list:
    ensure_growth_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT f.*, COALESCE(p.title,'#'||f.product_id) AS title,
                   (datetime('now','localtime') BETWEEN f.starts_at AND f.ends_at AND f.is_active=1) AS live
            FROM flash_sales f LEFT JOIN products p ON p.id=f.product_id
            ORDER BY f.id DESC LIMIT ?;
        """, (limit,)).fetchall()
    finally:
        conn.close()


# ─── ۶) امتیاز محصول ─────────────────────────────────────────────────────

def save_product_rating(user_id: int, order_id: int, product_id: int, rating: int) -> bool:
    ensure_growth_schema()
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO product_ratings (user_id,order_id,product_id,rating) VALUES (?,?,?,?);",
            (user_id, order_id, product_id, max(1, min(5, int(rating)))))
        ok = conn.execute("SELECT changes();").fetchone()[0]
        conn.commit()
        return bool(ok)
    finally:
        conn.close()


# نکته: get_product_rating نسخه dict قدیمی (بالاتر در همین فایل) مرجع است.


# ─── ۲) پیشنهاد بعد از خرید (Upsell) ─────────────────────────────────────

def get_upsell_products(product_id: int, category_id, limit: int = 2) -> list:
    """پرفروش‌های موجودِ همان دسته، غیر از محصول خریداری‌شده."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT p.id, p.title, p.price, p.category_id,
                   (SELECT COUNT(*) FROM product_feed f WHERE f.product_id=p.id AND f.delivered=0) AS stock,
                   (SELECT COUNT(*) FROM orders o WHERE o.product_id=p.id
                        AND COALESCE(o.status,'active')!='returned') AS sold
            FROM products p
            WHERE p.id != ? AND COALESCE(p.is_active,1)=1
              AND (? IS NULL OR p.category_id = ?)
            GROUP BY p.id
            HAVING stock > 0
            ORDER BY sold DESC, p.id DESC
            LIMIT ?;
        """, (product_id, category_id, category_id, limit)).fetchall()
    except Exception:
        return []
    finally:
        conn.close()


# ─── ۱) کمپین بازگردانی (Win-back) ────────────────────────────────────────

WINBACK_DEFAULTS = {
    "enabled": 0, "days_inactive": 14, "percent": 15,
    "expire_days": 3, "cooldown_days": 30, "hour": 11, "batch": 30,
    "message": ("سلام {name} 👋\n\nدلمون برات تنگ شده! 💜\n"
                "یه هدیه مخصوص خودت داریم:\n\n"
                "🎁 کد تخفیف <code>{code}</code> — {percent}٪ تخفیف\n"
                "⏳ فقط تا {days} روز اعتبار داره!\n\n"
                "همین حالا از منوی فروشگاه استفاده‌ش کن 🛍"),
}


def get_winback_settings() -> dict:
    return get_cfg_json("winback", WINBACK_DEFAULTS)


def find_winback_candidates(days_inactive: int, cooldown_days: int, batch: int = 30) -> list:
    """کاربرانی که خرید داشته‌اند ولی N روز است نخریده‌اند و اخیراً پیام نگرفته‌اند."""
    ensure_growth_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT CAST(o.user_id AS INTEGER) AS uid,
                   COALESCE(u.full_name, u.username, '') AS name,
                   MAX(o.created_at) AS last_order
            FROM orders o
            LEFT JOIN users u ON CAST(u.user_id AS INTEGER)=CAST(o.user_id AS INTEGER)
            WHERE COALESCE(o.status,'active') != 'returned'
            GROUP BY CAST(o.user_id AS INTEGER)
            HAVING MAX(o.created_at) < datetime('now','localtime', ?)
               AND NOT EXISTS (
                   SELECT 1 FROM winback_log w
                   WHERE w.user_id = CAST(o.user_id AS INTEGER)
                     AND w.sent_at > datetime('now','localtime', ?)
               )
            ORDER BY last_order ASC
            LIMIT ?;
        """, (f"-{int(days_inactive)} days", f"-{int(cooldown_days)} days", int(batch))).fetchall()
    finally:
        conn.close()


def create_winback_code(user_id: int, percent: int, expire_days: int) -> str:
    """کد تخفیف شخصی یک‌بارمصرف — برمی‌گرداند: متن کد."""
    ensure_discount_table()
    import random, string
    conn = _get_connection()
    try:
        for _ in range(6):
            code = "WB" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            try:
                cur = conn.execute("""
                    INSERT INTO discount_codes
                        (code, type, value, max_uses, max_uses_per_user, is_active,
                         expires_at, description)
                    VALUES (?,?,?,?,?,?, datetime('now','localtime', ?), ?);
                """, (code, "percent", int(percent), 1, 1, 1,
                      f"+{int(expire_days)} days", f"بازگردانی کاربر {user_id}"))
                code_id = cur.lastrowid
                conn.execute("INSERT INTO winback_log (user_id, code_id) VALUES (?,?);",
                             (user_id, code_id))
                conn.commit()
                return code
            except sqlite3.IntegrityError:
                continue
        return ""
    finally:
        conn.close()


# ─── ۴) لیدربرد هفتگی همکاران ────────────────────────────────────────────

LEADERBOARD_DEFAULTS = {
    "enabled": 0, "weekday": 4,  # 4 = جمعه (Mon=0)
    "rewards": "100000,60000,30000",
    "message": ("🏆 <b>نتایج مسابقه هفتگی همکاران</b>\n\n"
                "تبریک! شما در جایگاه {rank} این هفته قرار گرفتید 🎉\n"
                "🛒 فروش شما: {count} سفارش\n"
                "🎁 جایزه: <b>{reward}</b> تومان به کیف‌پول همکاری شما اضافه شد.\n\n"
                "هفته بعد هم منتظرتیم 💪"),
}


def get_leaderboard_settings() -> dict:
    return get_cfg_json("leaderboard", LEADERBOARD_DEFAULTS)


def weekly_top_partners(limit: int = 3) -> list:
    """برترین همکاران ۷ روز اخیر بر اساس تعداد خرید همکاری."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT CAST(user_id AS INTEGER) AS uid, COUNT(*) AS cnt,
                   COALESCE(SUM(price),0) AS total
            FROM orders
            WHERE buyer_type='partner'
              AND COALESCE(status,'active') != 'returned'
              AND created_at > datetime('now','localtime','-7 days')
            GROUP BY CAST(user_id AS INTEGER)
            ORDER BY cnt DESC, total DESC
            LIMIT ?;
        """, (limit,)).fetchall()
    finally:
        conn.close()


# ─── ۷) تنظیمات رمزارز / کانال / تبلیغ / وب‌اپ ────────────────────────────

CRYPTO_DEFAULTS = {"enabled": 0, "usdt_trc20": "", "trx": "",
                   "note": "پس از واریز، TXID تراکنش را ارسال کنید. شارژ بعد از تأیید انجام می‌شود."}
SOCIAL_DEFAULTS = {"channel_id": "", "sale_post": 0, "rating": 1, "upsell": 1,
                   "sale_post_text": "✅ همین حالا «{title}» خریداری شد 🎉\n\n🛍 شما هم از ربات ما خرید کنید!"}
PROMO_DEFAULTS  = {"text": ("🔥 فروشگاه دیجیتال StockLand\n\n"
                            "✅ تحویل آنی و خودکار\n✅ پشتیبانی واقعی\n✅ قیمت‌های رقابتی\n\n"
                            "با لینک اختصاصی من عضو شو و خرید کن:\n{link}")}


def get_crypto_settings() -> dict:
    return get_cfg_json("crypto", CRYPTO_DEFAULTS)


def get_social_settings() -> dict:
    return get_cfg_json("social", SOCIAL_DEFAULTS)


def get_promo_settings() -> dict:
    return get_cfg_json("promo", PROMO_DEFAULTS)


def save_crypto_receipt(user_id: int, amount: int, network: str, txid: str) -> int:
    """رسید رمزارز — در همان جدول card_receipts با method مجزا."""
    ensure_card_receipts_schema()
    ensure_growth_schema()
    conn = _get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO card_receipts (user_id, amount, file_id, method, txid) VALUES (?,?,?,?,?);",
            (user_id, amount, "", f"crypto_{network}", txid.strip()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ─── ۶) پاداش عضویت (به‌جای اولین خرید) + مسیریابی کیف‌پول ─────────────────

def _is_approved_partner(user_id: int) -> bool:
    conn = _get_connection()
    try:
        r = conn.execute(
            "SELECT 1 FROM partners WHERE CAST(tg_user_id AS INTEGER)=? AND status='approved' LIMIT 1;",
            (int(user_id),)).fetchone()
        return bool(r)
    except Exception:
        return False
    finally:
        conn.close()


def credit_referrer(referrer_id: int, amount: int, note: str) -> str:
    """پرداخت به معرف — همکار → کیف همکاری، کاربر عادی → کیف اصلی. برمی‌گرداند نوع کیف."""
    if _is_approved_partner(referrer_id):
        credit_partner_wallet(referrer_id, amount, note=note)
        return "partner"
    add_wallet_balance(referrer_id, amount)
    return "main"


def pay_signup_referral_reward(referrer_id: int, referred_id: int) -> dict:
    """پاداش ثابت معرفی — همان لحظه عضویت، فقط یک‌بار (قفل با پرچم rewarded).
    Returns: {paid, amount, wallet}"""
    ensure_referral_schema()
    settings = get_referral_settings()
    if not settings.get("is_active"):
        return {"paid": False}
    amount = int(settings.get("reward_amount") or 0)
    if amount <= 0:
        return {"paid": False}
    conn = _get_connection()
    try:
        # قفل اتمیک: فقط اگر rewarded=0 بود، 1 کن
        conn.execute(
            "UPDATE referrals SET rewarded=1 WHERE referrer_id=? AND referred_id=? AND rewarded=0;",
            (referrer_id, referred_id))
        changed = conn.execute("SELECT changes();").fetchone()[0]
        conn.commit()
    finally:
        conn.close()
    if not changed:
        return {"paid": False}
    wallet = credit_referrer(referrer_id, amount,
                             note=f"پاداش معرفی کاربر {referred_id}")
    return {"paid": True, "amount": amount, "wallet": wallet}


_FLASH_MAP_CACHE = {"t": 0.0, "map": {}}

def get_active_flash_map() -> dict:
    """{product_id: percent} فروش‌های فوری زنده — کش ۳۰ ثانیه برای لیبل لیست‌ها."""
    now = _time.time()
    if now - _FLASH_MAP_CACHE["t"] < 30:
        return _FLASH_MAP_CACHE["map"]
    ensure_growth_schema()
    m = {}
    conn = _get_connection()
    try:
        for r in conn.execute("""
            SELECT product_id, percent FROM flash_sales
            WHERE is_active=1 AND datetime('now','localtime') BETWEEN starts_at AND ends_at;"""):
            m[int(r[0])] = int(r[1])
    except Exception:
        pass
    finally:
        conn.close()
    _FLASH_MAP_CACHE["t"] = now
    _FLASH_MAP_CACHE["map"] = m
    return m


def flash_map_invalidate():
    _FLASH_MAP_CACHE["t"] = 0.0
