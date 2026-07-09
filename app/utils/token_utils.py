import uuid

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.extensions import db
from app.models.user import User


def _serializer():
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt="campushire-password-reset",
    )


def generate_password_reset_token(user):
    payload = {
        "user_id": str(user.id),
        "pwd_hash": user.password_hash[:32],
    }
    return _serializer().dumps(payload)


def verify_password_reset_token(token):
    if not token:
        return None

    max_age = current_app.config.get("PASSWORD_RESET_TOKEN_MAX_AGE", 3600)
    try:
        payload = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None

    try:
        uid = uuid.UUID(str(payload.get("user_id")))
    except (ValueError, TypeError, AttributeError):
        return None

    user = db.session.get(User, uid)
    if not user or not user.is_active:
        return None

    if user.password_hash[:32] != payload.get("pwd_hash"):
        return None

    return user
