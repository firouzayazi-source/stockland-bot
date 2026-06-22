import os
import sqlite3
from datetime import datetime

from config import DB_PATH, BASE_DIR

# اگر DB_PATH در config نسبی باشد، به BASE_DIR وصل می‌کنیم
DB_FULL_PATH = DB_PATH
if not os.path.isabs(DB_FULL_PATH):
    DB_FULL_PATH = os.path.join(BASE_DIR, DB_PATH)


def _get_connection():
    """
    همیشه یک کانکشن جدید می‌سازد تا با Threadهای تلگرام مشکل نداشته باشیم.
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
    ساخت / به‌روزرسانی جداول دیتابیس.
    اگر قبلاً ساخته شده باشد، فقط مهاجرت‌های لازم را انجام می‌دهد.
    """
    global DB_FULL_PATH
    if db_path:
        if not os.path.isabs(db_path):
            DB_FULL_PATH = os.path.join(BASE_DIR, db_path)
        else:
            DB_FULL_PATH = db_path

    os.makedirs(os.path.dirname(DB_FULL_PATH), exist_ok=True)

    conn = _get_connection()
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

    # مهاجرت: ستون‌های حد خرید روزانه برای محصولات
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


    
    
    # مهاجرت/ایندکس‌ها برای partners
    try:
        cur.execute("PRAGMA table_info(partners);")
        cols = {row[1] for row in cur.fetchall()}
        # ستون‌های اصلی
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

# جدول سفارش‌ها
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

    # جدول تراکنش‌های زرین‌پال
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
    # اگر DB قدیمی authority تکراری داشته باشد، ابتدا dedupe می‌کنیم و سپس ایندکس یکتا را می‌سازیم.
    try:
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_zarinpal_transactions_authority "
            "ON zarinpal_transactions(authority);"
        )
    except (sqlite3.IntegrityError, sqlite3.OperationalError):
        # نگه داشتن قدیمی‌ترین رکورد هر authority و حذف بقیه
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

    # جدول سرویس‌های «سایر محصولات» (زیرشاخه‌های پویا مثل Gmail/Yahoo و ...)
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



    # اگر هیچ سرویسی تعریف نشده بود، پیش‌فرض جیمیل را اضافه کن
    cur.execute("SELECT COUNT(*) FROM other_services;")
    svc_count = cur.fetchone()[0] or 0
    if seed_defaults and svc_count == 0:
        now = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT INTO other_services (service_key, title, emoji, is_active, created_at) VALUES (?, ?, ?, ?, ?);",
            ("gmail", "سرویس‌های جیمیل", "✉️", 1, now),
        )


    # اگر هیچ محصولی وجود نداشت، چند محصول نمونه اضافه کن
    cur.execute("SELECT COUNT(*) FROM products;")
    count = cur.fetchone()[0] or 0
    if seed_defaults and count == 0:
        sample_products = [
            ("apple", "apple_ready_1", "اپل آیدی آماده ریجن آمریکا", 250000,
             "تحویل فوری، آمریکا، بدون سوال امنیتی.", 1),
            ("apple", "apple_ready_2", "اپل آیدی آماده ریجن ترکیه", 130000,
             "تحویل فوری، ترکیه، مناسب خریدهای ارزان‌تر.", 1),
            ("apple", "apple_ready_3", "ساخت اپل آیدی با ایمیل شما", 170000,
             "ساخت دستی، تنظیم ریجن مناسب، تحویل ۳۰ دقیقه‌ای.", 1),
            ("gmail", "gmail_ready_1", "جیمیل آماده سنی وریفای شده", 90000,
             "ایده‌آل برای سرویس‌های تحریم‌محور، سنی بالای ۱۸ سال.", 1),
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

    # جدول دسته‌بندی‌های داینامیک (نامحدود، درختی)
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

    # جدول پیام‌های تیکت (تاریخچه مکالمه)
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

    # جدول متن‌های رابط کاربری (UI)
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
    موجودی را افزایش می‌دهد و موجودی جدید را برمی‌گرداند.
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
    اگر موجودی کافی باشد، مبلغ را کم می‌کند و True برمی‌گرداند؛ در غیر این صورت False.
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
    مستقیماً موجودی کیف پول را روی مقدار دلخواه تنظیم می‌کند (برای ادمین).
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
    یک سفارش جدید ثبت می‌کند و id سفارش را برمی‌گرداند.
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
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, title, price, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?;
        """,
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_recent_orders_global(limit: int = 15):
    conn = _get_connection()
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
    conn.close()
    return rows


# ========= PRODUCTS =========


def get_products_by_category(category: str):
    """
    محصولات یک دسته را برمی‌گرداند.
    خروجی همیشه ۷ فیلد است:
    (id, category, title, price, description, is_active, partner_price)
    اگر ستون partner_price وجود نداشت، مقدار آن None خواهد بود.
    """
    conn = _get_connection()
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
    conn.close()
    return rows

def get_product_by_id(pid: int):
    conn = _get_connection()
    cur = conn.cursor()
    # بررسی وجود ستون‌ها (برای سازگاری با دیتابیس‌های قدیمی)
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
    cur = conn.cursor()
    cur.execute(
        f"UPDATE products SET {field} = ? WHERE id = ?;",
        (value, pid),
    )
    conn.commit()
    conn.close()


def toggle_product_active(pid: int):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT is_active FROM products WHERE id = ?;", (pid,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return
    current = int(row[0]) or 0
    new_val = 0 if current else 1
    cur.execute(
        "UPDATE products SET is_active = ? WHERE id = ?;",
        (new_val, pid),
    )
    conn.commit()
    conn.close()


def add_product(category: str, title: str, price: int, description: str = "", is_active: int = 1, partner_price: int | None = None) -> int:
    """
    یک محصول جدید اضافه می‌کند و id آن را برمی‌گرداند.
    product_key یا code به‌صورت خودکار از روی عنوان ساخته می‌شود.
    اگر جدول محصولات ستون product_key یا code داشته باشد، مقدار مناسب در هر ستون درج می‌شود.
    اگر ستون partner_price وجود داشته باشد و partner_price داده شود، در همان ستون درج می‌شود.
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

    علاوه بر حذف رکورد محصول، آیتم‌های فید مرتبط با آن نیز پاک می‌شوند تا رکورد یتیم باقی نماند.
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
    """برگشت آمار کلی: (تعداد کیف‌ها، جمع موجودی‌ها، تعداد سفارش‌ها، مجموع فروش، تعداد محصولات فعال)"""
    conn = _get_connection()
    cur = conn.cursor()
    # کیف پول‌ها
    cur.execute("SELECT COUNT(*), COALESCE(SUM(balance), 0) FROM wallets;")
    wallet_row = cur.fetchone()
    total_wallets = wallet_row[0] or 0
    total_balance = wallet_row[1] or 0
    # سفارش‌ها
    cur.execute("SELECT COUNT(*), COALESCE(SUM(price), 0) FROM orders;")
    order_row = cur.fetchone()
    total_orders = order_row[0] or 0
    total_sales = order_row[1] or 0
    # محصولات فعال
    cur.execute("SELECT COUNT(*) FROM products WHERE is_active = 1;")
    active_products = cur.fetchone()[0] or 0
    conn.close()
    return total_wallets, total_balance, total_orders, total_sales, active_products
def create_zarinpal_pending_transaction(user_id: int, amount: int, authority: str) -> bool:
    """یک رکورد pending برای authority می‌سازد. اگر authority قبلا ثبت شده باشد False برمی‌گرداند."""
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
    """status را تغییر می‌دهد. اگر expected_current داده شود فقط وقتی status فعلی همان باشد update می‌کند.
    خروجی: تعداد ردیف‌های تغییرکرده (0 یا 1).
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

    # کیف پول‌ها
    cur.execute("SELECT COUNT(*), COALESCE(SUM(balance), 0) FROM wallets;")
    wallet_row = cur.fetchone()
    total_wallets = wallet_row[0] or 0
    total_balance = wallet_row[1] or 0

    # سفارش‌ها
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
    چند آیتم (مثلا اپل آیدی) را برای یک محصول ثبت می‌کند.
    هر خط یک آیتم است.
    """
    if not items:
        return 0

    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    cur = conn.cursor()
    rows = [(product_id, item, 0, now) for item in items]
    cur.executemany(
        """
        INSERT INTO product_feed (product_id, data, delivered, created_at)
        VALUES (?, ?, ?, ?);
        """,
        rows,
    )
    conn.commit()
    conn.close()
    return len(rows)


def get_feed_stats(product_id: int):
    """
    تعداد کل، تعداد تحویل نشده، تعداد تحویل شده را برمی‌گرداند.
    """
    conn = _get_connection()
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
    conn.close()
    return total, remaining, delivered


def claim_next_feed_item(product_id: int, order_id: int = None):
    """
    اتمیک: اولین آیتم تحویل‌نشده را claim می‌کند (delivered=1) و برمی‌گرداند: (feed_id, data) یا None.
    از BEGIN IMMEDIATE برای جلوگیری از race condition در خریدهای همزمان استفاده می‌شه.
    """
    conn = _get_connection()
    cur = conn.cursor()
    try:
        # migration: اضافه کردن ستون‌های tracking اگه نباشن
        try:
            cur.execute("ALTER TABLE product_feed ADD COLUMN order_id INTEGER;")
            cur.execute("ALTER TABLE product_feed ADD COLUMN delivered_at TEXT;")
            conn.commit()
        except Exception:
            pass  # ستون‌ها قبلاً اضافه شدن

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
    conn.close()
    if not row:
        return None
    return row[0], row[1]


def mark_feed_item_delivered(feed_id: int):
    """
    Marks a feed item delivered. Prefer claim_next_feed_item for user delivery path.
    """
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE product_feed SET delivered = 1 WHERE id = ?;",
        (feed_id,),
    )
    conn.commit()
    conn.close()



def list_feed_items(product_id: int, delivered: int | None = None, limit: int = 10, offset: int = 0):
    """لیست آیتم‌های فید یک محصول را برمی‌گرداند.

    delivered:
      - None: همه
      - 0: فقط تحویل‌نشده
      - 1: فقط تحویل‌شده
    """
    conn = _get_connection()
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
    cur = conn.cursor()
    cur.execute(
        "UPDATE product_feed SET delivered = ? WHERE id = ?;",
        (int(1 if delivered else 0), int(feed_id)),
    )
    conn.commit()
    conn.close()


def delete_feed_item(feed_id: int):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM product_feed WHERE id = ?;", (int(feed_id),))
    conn.commit()
    conn.close()



def list_other_services(active_only: bool = True):
    """لیست سرویس‌های «سایر محصولات» را برمی‌گرداند."""
    conn = _get_connection()
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
    conn.close()
    return rows


def add_other_service(service_key: str, title: str, emoji: str = "🧩") -> bool:
    """یک سرویس جدید اضافه می‌کند. اگر کلید تکراری باشد False برمی‌گرداند."""
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
    """یک سرویس را حذف می‌کند. در صورت delete_products محصولات و فیدهای آن سرویس هم پاک می‌شود."""
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
    """برمی‌گرداند: (threshold, last_notified_remaining). اگر تنظیمی نبود threshold=5."""
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT threshold, last_notified_remaining FROM feed_alert_settings WHERE product_id=?;",
        (product_id,),
    )
    row = cur.fetchone()
    if not row:
        # مقدار پیش‌فرض
        threshold = 5
        last = None
        now = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT OR IGNORE INTO feed_alert_settings (product_id, threshold, last_notified_remaining, updated_at) VALUES (?, ?, NULL, ?);",
            (product_id, threshold, now),
        )
        conn.commit()
        conn.close()
        return threshold, last
    conn.close()
    return int(row[0]), row[1]


def set_feed_alert_threshold(product_id: int, threshold: int):
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO feed_alert_settings (product_id, threshold, last_notified_remaining, updated_at) VALUES (?, ?, NULL, ?) "
        "ON CONFLICT(product_id) DO UPDATE SET threshold=excluded.threshold, updated_at=excluded.updated_at;",
        (product_id, int(threshold), now),
    )
    conn.commit()
    conn.close()


def reset_feed_alert_notification(product_id: int):
    """پس از شارژ مجدد موجودی، هشدار قبلی ریست می‌شود تا دوباره ارسال شود."""
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO feed_alert_settings (product_id, threshold, last_notified_remaining, updated_at) VALUES (?, 5, NULL, ?) "
        "ON CONFLICT(product_id) DO UPDATE SET last_notified_remaining=NULL, updated_at=excluded.updated_at;",
        (product_id, now),
    )
    conn.commit()
    conn.close()


def set_feed_alert_last_notified(product_id: int, remaining: int):
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO feed_alert_settings (product_id, threshold, last_notified_remaining, updated_at) VALUES (?, 5, ?, ?) "
        "ON CONFLICT(product_id) DO UPDATE SET last_notified_remaining=excluded.last_notified_remaining, updated_at=excluded.updated_at;",
        (product_id, int(remaining), now),
    )
    conn.commit()
    conn.close()

# =====================
# Partner / Reseller API
# =====================

def upsert_partner_request(tg_user_id: int, phone: str, username: str = "", full_name: str = "", note: str = "", city: str = "", shop_name: str = ""):
    """ثبت درخواست نمایندگی.

    سیاست فعلی: هر کاربر/شماره فقط یک‌بار می‌تواند درخواست ثبت کند.
    بنابراین اگر رکوردی وجود داشته باشد، وضعیت آن را به pending برنمی‌گردانیم.
    - pending: فقط اطلاعات پروفایل را به‌روزرسانی می‌کنیم (بدون تغییر created_at)
    - approved: فقط اطلاعات پروفایل را به‌روزرسانی می‌کنیم (بدون تغییر approved_at)
    - rejected: فقط اطلاعات پروفایل را به‌روزرسانی می‌کنیم
    """
    conn = _get_connection()
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
            # وضعیت‌های ناشناخته: مثل pending رفتار کن
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
    conn.close()



def update_partner_city_shop(tg_user_id: int, city: str = "", shop_name: str = ""):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE partners SET city = COALESCE(?, city), shop_name = COALESCE(?, shop_name) WHERE tg_user_id = ?;",
        (city or None, shop_name or None, tg_user_id),
    )
    conn.commit()
    conn.close()


def get_partner_by_user_id(tg_user_id: int):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, tg_user_id, phone, status, username, full_name, note, created_at, approved_at
        FROM partners WHERE tg_user_id = ? ORDER BY id DESC LIMIT 1;
        """,
        (tg_user_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def get_partner_by_phone(phone: str):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, tg_user_id, phone, status, username, full_name, note, created_at, approved_at
        FROM partners WHERE phone = ? ORDER BY id DESC LIMIT 1;
        """,
        (phone,),
    )
    row = cur.fetchone()
    conn.close()
    return row

def list_partner_requests(status: str | None = None, query: str | None = None, limit: int = 50, offset: int = 0):
    """لیست درخواست‌های همکار با امکان فیلتر وضعیت و جستجو.

    خروجی: (id, tg_user_id, phone, username, full_name, city, shop_name, status, created_at, approved_at)
    """
    conn = _get_connection()
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
    conn.close()
    return rows


def list_pending_partners():
    # برای سازگاری با کدهای قبلی
    return list_partner_requests(status='pending', query=None, limit=200, offset=0)

def approve_partner(tg_user_id: int):
    conn = _get_connection()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat(timespec='seconds')
    cur.execute(
        """UPDATE partners SET status='approved', approved_at=? WHERE tg_user_id=?;""",
        (now, tg_user_id),
    )
    conn.commit()
    changed = cur.rowcount
    conn.close()
    return changed > 0

def reject_partner(tg_user_id: int):
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE partners SET status='rejected' WHERE tg_user_id=?;", (tg_user_id,))
    conn.commit()
    changed = cur.rowcount
    conn.close()
    return changed > 0

def is_partner_approved(tg_user_id: int) -> bool:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM partners WHERE tg_user_id=? AND status='approved' LIMIT 1;", (tg_user_id,))
    ok = cur.fetchone() is not None
    conn.close()
    return ok


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


def get_category_by_button_text(text: str):
    """یافتن دسته ریشه بر اساس متن دکمه Reply Keyboard"""
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
    """حذف دسته و همه زیردسته‌ها و محصولات مرتبط"""
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
    """همه دسته‌ها برای نمایش در select box پنل"""
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
    """تعداد تیکت‌هایی که ادمین باید پاسخ بده (badge count)."""
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

        # تکلیف کیف‌پول
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
      - اگر feed_id موجود باشد، آیتم فید به delivered=0 برمی‌گردد (موجودی +1)
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

        # علامت‌گذاری سفارش به‌عنوان برگشتی
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
    """آمار سفارش‌های برگشتی."""
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
    """تعداد آیتم‌های برگشتی یک محصول (سفارش‌های returned با این product_id)."""
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS discount_codes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT    UNIQUE NOT NULL COLLATE NOCASE,
            type        TEXT    NOT NULL DEFAULT 'percent',   -- 'percent' | 'fixed'
            value       INTEGER NOT NULL,
            max_uses    INTEGER DEFAULT 0,
            used_count  INTEGER DEFAULT 0,
            min_amount  INTEGER DEFAULT 0,
            product_id  INTEGER DEFAULT NULL,
            expires_at  TEXT    DEFAULT NULL,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT    DEFAULT (datetime('now','localtime'))
        );
    """)
    conn.commit()
    conn.close()


def validate_discount(code: str, product_id: int = None, amount: int = 0) -> dict:
    """
    اعتبارسنجی کد تخفیف.
    Returns: {valid, discount_amount, type, value, code_id, error}
    """
    ensure_discount_table()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM discount_codes WHERE code=? COLLATE NOCASE AND is_active=1 LIMIT 1;",
            (code.strip(),)
        ).fetchone()
        if not row:
            return {"valid": False, "error": "کد تخفیف یافت نشد یا غیرفعال است"}
        if row["max_uses"] > 0 and row["used_count"] >= row["max_uses"]:
            return {"valid": False, "error": "ظرفیت استفاده از این کد تمام شده است"}
        if row["expires_at"] and row["expires_at"] < datetime.utcnow().isoformat():
            return {"valid": False, "error": "کد تخفیف منقضی شده است"}
        if row["min_amount"] > 0 and amount < row["min_amount"]:
            return {"valid": False, "error": f"حداقل مبلغ خرید برای این کد {row['min_amount']:,} تومان است"}
        if row["product_id"] and product_id and int(row["product_id"]) != int(product_id):
            return {"valid": False, "error": "این کد برای محصول دیگری است"}

        discount = row["value"] if row["type"] == "fixed" else int(amount * row["value"] / 100)
        discount = min(discount, amount)
        return {"valid": True, "discount_amount": discount, "type": row["type"],
                "value": row["value"], "code_id": row["id"], "error": None}
    finally:
        conn.close()


def use_discount(code_id: int):
    """افزایش شمارنده استفاده از کد."""
    conn = _get_connection()
    try:
        conn.execute("UPDATE discount_codes SET used_count=used_count+1 WHERE id=?;", (code_id,))
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── اشتراک موجودی ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_subscription_table():
    conn = _get_connection()
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
    """وقتی موجودی اومد، اشتراک‌ها رو reset کن برای دور بعد."""
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
    """اضافه کردن ستون support_after_purchase به products."""
    conn = _get_connection()
    try:
        try:
            conn.execute("ALTER TABLE products ADD COLUMN support_after_purchase INTEGER DEFAULT 0;")
            conn.commit()
        except Exception:
            pass  # ستون قبلاً وجود داشت
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

