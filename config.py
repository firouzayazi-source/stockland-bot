import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ─── Database ────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH")
if not DB_PATH:
    raise RuntimeError("DB_PATH environment variable is required")
DB_FULL_PATH = DB_PATH

# ─── Telegram ────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID   = int(os.getenv("ADMIN_ID", "0") or "0")

# ─── App settings ────────────────────────────────────────────
MIN_TOPUP_AMOUNT = int(os.getenv("MIN_TOPUP_AMOUNT", "10000"))  # تومان


def validate_config() -> None:
    """Fail fast if critical env vars are missing."""
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is required")
    if not ADMIN_ID:
        raise RuntimeError("ADMIN_ID is required")
