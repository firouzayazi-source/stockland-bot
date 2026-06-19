from config import ADMIN_ID


STATE = {
    "user": {},
    "admin": {},
}

# Backward compatibility for existing handlers.
user_states = STATE["user"]
admin_states = STATE["admin"]
reseller_signup = {}


def clear_user_state(uid: int):
    user_states.pop(uid, None)


def clear_admin_state(aid: int):
    admin_states.pop(aid, None)


def ensure_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID
