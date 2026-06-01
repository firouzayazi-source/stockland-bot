# -*- coding: utf-8 -*-
import os
import hmac
import hashlib
import sqlite3
from datetime import datetime, timezone

from flask import Flask, request, abort, jsonify

# One source of truth for DB path: config.DB_FULL_PATH (which uses env DB_PATH)
try:
    from config import DB_FULL_PATH
except Exception:
    # fallback: resolve DB_PATH relative to project root
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_FULL_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "db.sqlite"))

# One source of truth for secret: INTERNAL_API_SECRET (fallback to INTERNAL_SECRET for backward compatibility)
SECRET = (os.environ.get("INTERNAL_API_SECRET") or os.environ.get("INTERNAL_SECRET") or "").strip()
if not SECRET:
    raise RuntimeError("INTERNAL_API_SECRET (or INTERNAL_SECRET) is required")

DEBUG = (os.environ.get("DEBUG_INTERNAL_API") or "false").strip().lower() in ("1", "true", "yes", "on")

app = Flask(__name__)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_sig(raw: bytes) -> str:
    return hmac.new(SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()


def verify_sig(raw: bytes, header_sig: str) -> bool:
    if not header_sig:
        return False
    computed = _compute_sig(raw)
    return hmac.compare_digest(computed, header_sig.strip())


def _db():
    con = sqlite3.connect(DB_FULL_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON;")
    con.execute("PRAGMA busy_timeout=5000;")
    return con


@app.get("/health")
def health():
    try:
        con = _db()
        con.execute("SELECT 1;").fetchone()
        con.close()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/finalize_wallet_charge")
def finalize_wallet_charge():
    """
    Idempotent finalize endpoint.

    Expected JSON:
      - authority (str) [required]
      - uid / user_id (int) [required]
      - amount_toman / amount (int) [required]
      - ref_id (optional, ignored in DB schema unless you add it later)

    Headers:
      - X-SIGN: HMAC-SHA256 of raw body using INTERNAL_API_SECRET
    """
    raw = request.get_data() or b""
    sig = request.headers.get("X-SIGN", "")

    if not verify_sig(raw, sig):
        abort(401, "bad signature")

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, "json must be object")

    authority = str(data.get("authority") or "").strip()
    uid = data.get("uid", None) or data.get("user_id", None)
    amount = data.get("amount_toman", None) or data.get("amount", None)

    if not authority:
        abort(400, "authority required")
    if uid is None:
        abort(400, "uid required")
    if amount is None:
        abort(400, "amount required")

    try:
        uid_i = int(uid)
        amt_i = int(amount)
    except Exception:
        abort(400, "uid/amount must be integer")

    con = _db()
    try:
        con.execute("BEGIN IMMEDIATE;")

        row = con.execute(
            "SELECT status, user_id, amount FROM zarinpal_transactions WHERE authority=? ORDER BY id DESC LIMIT 1",
            (authority,)
        ).fetchone()

        if not row:
            # If transaction record wasn't created by bot, we refuse: prevents arbitrary wallet top-ups.
            con.execute("ROLLBACK;")
            return jsonify({"ok": False, "error": "authority not found"}), 404

        st = (row["status"] or "").lower().strip()
        if st == "paid":
            con.execute("COMMIT;")
            return jsonify({"ok": True, "duplicate": True, "authority": authority})

        # Safety: enforce matching uid/amount with stored tx (prevents tampering)
        try:
            db_uid = int(row["user_id"])
            db_amt = int(row["amount"])
        except Exception:
            db_uid = uid_i
            db_amt = amt_i

        if db_uid != uid_i or db_amt != amt_i:
            con.execute("ROLLBACK;")
            return jsonify({"ok": False, "error": "uid/amount mismatch"}), 409

        con.execute(
            "UPDATE zarinpal_transactions SET status='paid' WHERE authority=?",
            (authority,)
        )
        
        # بررسی نوع پرداخت
        row2 = con.execute(
            "SELECT payment_type, product_id, wallet_reserved FROM zarinpal_transactions WHERE authority=? ORDER BY id DESC LIMIT 1",
            (authority,)
        ).fetchone()

        ptype = (row2["payment_type"] or "").lower()
        product_id = row2["product_id"]
        wallet_reserved = row2["wallet_reserved"] or 0

        if ptype == "product":
                # کم کردن سهم کیف پول
            if wallet_reserved > 0:
                con.execute(
                    "UPDATE wallets SET balance = balance - ? WHERE user_id=?",
                    (wallet_reserved, uid_i)
                )

            # تحویل محصول
            from bot import deliver_product
            deliver_product(uid_i, product_id)

        else:
            # شارژ کیف پول
            con.execute(
                "INSERT INTO wallets(user_id, balance, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET balance = balance + excluded.balance, updated_at = excluded.updated_at",
                (uid_i, amt_i, now_iso())
            )
