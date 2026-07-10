"""سرویس کیف‌پول — منطق خالص."""


def get_balance(user_id: int) -> int:
    import db
    return int(db.get_wallet_balance(user_id) or 0)


def credit(user_id: int, amount: int, reason: str = "") -> bool:
    """شارژ کیف‌پول."""
    if amount <= 0:
        return False
    import db
    db.add_wallet_balance(user_id, amount)
    return True


def debit(user_id: int, amount: int, reason: str = "") -> bool:
    """کسر — False اگر موجودی کافی نیست."""
    if amount <= 0:
        return False
    import db
    bal = int(db.get_wallet_balance(user_id) or 0)
    if bal < amount:
        return False
    db.add_wallet_balance(user_id, -amount)
    return True
