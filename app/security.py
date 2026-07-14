from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from hmac import compare_digest

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int, role: str, secret: str, ttl_minutes: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, secret: str) -> dict:
    return jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["sub", "exp"]})


def canonical_amount(amount: Decimal) -> str:
    value = format(amount, "f")
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value


def build_webhook_signature(
    *, account_id: int, amount: Decimal, transaction_id: str, user_id: int, secret: str
) -> str:
    raw = f"{account_id}{canonical_amount(amount)}{transaction_id}{user_id}{secret}"
    return sha256(raw.encode("utf-8")).hexdigest()


def valid_webhook_signature(
    *, account_id: int, amount: Decimal, transaction_id: str, user_id: int,
    signature: str, secret: str
) -> bool:
    expected = build_webhook_signature(
        account_id=account_id,
        amount=amount,
        transaction_id=transaction_id,
        user_id=user_id,
        secret=secret,
    )
    return compare_digest(expected, signature.casefold())

