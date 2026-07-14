from __future__ import annotations

from decimal import Decimal

import jwt
from pydantic import ValidationError
from sanic import Blueprint, Request
from sanic.response import empty, json
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import ApiError
from app.models import Account, Payment, User
from app.schemas import LoginInput, UserCreateInput, UserUpdateInput, WebhookInput, validate_json
from app.security import (
    build_webhook_signature,
    create_access_token,
    decode_access_token,
    hash_password,
    valid_webhook_signature,
    verify_password,
)


api = Blueprint("api", url_prefix="/api/v1")


def _account_data(account: Account) -> dict:
    return {
        "id": account.id,
        "user_id": account.user_id,
        "balance": format(account.balance, ".2f"),
        "created_at": account.created_at.isoformat() if account.created_at else None,
    }


def _payment_data(payment: Payment) -> dict:
    return {
        "id": payment.id,
        "transaction_id": payment.transaction_id,
        "user_id": payment.user_id,
        "account_id": payment.account_id,
        "amount": format(payment.amount, ".2f"),
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
    }


def _user_data(user: User, *, include_accounts: bool = False) -> dict:
    result = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
    if include_accounts:
        result["accounts"] = [_account_data(account) for account in user.accounts]
    return result


def _payload(model, request: Request):
    try:
        return validate_json(model, request.json)
    except ValidationError as error:
        raise ApiError(422, "validation_error", "Request body is invalid") from error


async def _current_user(
    request: Request, session: AsyncSession, *, roles: set[str] | None = None
) -> User:
    token = request.token
    if not token:
        raise ApiError(401, "missing_token", "Bearer token is required")

    try:
        claims = decode_access_token(token, request.app.ctx.settings.jwt_secret)
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
        raise ApiError(401, "invalid_token", "Bearer token is invalid or expired") from error

    user = await session.get(User, user_id)
    if user is None:
        raise ApiError(401, "invalid_token", "Token owner no longer exists")
    if roles is not None and user.role not in roles:
        raise ApiError(403, "forbidden", "Insufficient permissions")
    return user


@api.get("/health")
async def health(_: Request):
    return json({"status": "ok"})


@api.post("/auth/login")
async def login(request: Request):
    payload = _payload(LoginInput, request)
    async with request.app.ctx.session_factory() as session:
        user = await session.scalar(select(User).where(User.email == payload.email))
        if user is None or not verify_password(user.password_hash, payload.password):
            raise ApiError(401, "invalid_credentials", "Invalid email or password")

        token = create_access_token(
            user.id,
            user.role,
            request.app.ctx.settings.jwt_secret,
            request.app.ctx.settings.access_token_ttl_minutes,
        )
        return json({"access_token": token, "token_type": "Bearer"})


@api.get("/me")
async def me(request: Request):
    async with request.app.ctx.session_factory() as session:
        user = await _current_user(request, session)
        return json(_user_data(user))


@api.get("/accounts")
async def my_accounts(request: Request):
    async with request.app.ctx.session_factory() as session:
        user = await _current_user(request, session)
        accounts = (
            await session.scalars(
                select(Account).where(Account.user_id == user.id).order_by(Account.id)
            )
        ).all()
        return json({"items": [_account_data(account) for account in accounts]})


@api.get("/payments")
async def my_payments(request: Request):
    async with request.app.ctx.session_factory() as session:
        user = await _current_user(request, session)
        payments = (
            await session.scalars(
                select(Payment)
                .where(Payment.user_id == user.id)
                .order_by(Payment.created_at.desc(), Payment.id.desc())
            )
        ).all()
        return json({"items": [_payment_data(payment) for payment in payments]})


@api.get("/admin/users")
async def list_users(request: Request):
    async with request.app.ctx.session_factory() as session:
        await _current_user(request, session, roles={"admin"})
        users = (
            await session.scalars(
                select(User)
                .where(User.role == "user")
                .options(selectinload(User.accounts))
                .order_by(User.id)
            )
        ).all()
        return json({"items": [_user_data(user, include_accounts=True) for user in users]})


@api.post("/admin/users")
async def create_user(request: Request):
    payload = _payload(UserCreateInput, request)
    async with request.app.ctx.session_factory() as session:
        await _current_user(request, session, roles={"admin"})
        user = User(
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
            role="user",
        )
        session.add(user)
        try:
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            raise ApiError(409, "email_exists", "A user with this email already exists") from error
        await session.refresh(user)
        return json(_user_data(user), status=201)


@api.patch("/admin/users/<user_id:int>")
async def update_user(request: Request, user_id: int):
    payload = _payload(UserUpdateInput, request)
    if not payload.model_fields_set:
        raise ApiError(422, "validation_error", "At least one field is required")

    async with request.app.ctx.session_factory() as session:
        await _current_user(request, session, roles={"admin"})
        user = await session.get(User, user_id)
        if user is None or user.role != "user":
            raise ApiError(404, "user_not_found", "User was not found")

        if payload.email is not None:
            user.email = payload.email
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.password is not None:
            user.password_hash = hash_password(payload.password)

        try:
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            raise ApiError(409, "email_exists", "A user with this email already exists") from error
        await session.refresh(user)
        return json(_user_data(user))


@api.delete("/admin/users/<user_id:int>")
async def delete_user(request: Request, user_id: int):
    async with request.app.ctx.session_factory() as session:
        await _current_user(request, session, roles={"admin"})
        user = await session.get(User, user_id)
        if user is None or user.role != "user":
            raise ApiError(404, "user_not_found", "User was not found")
        await session.delete(user)
        await session.commit()
        return empty(status=204)


@api.post("/payments/webhook")
async def payment_webhook(request: Request):
    payload: WebhookInput = _payload(WebhookInput, request)
    settings = request.app.ctx.settings
    if not valid_webhook_signature(
        account_id=payload.account_id,
        amount=payload.amount,
        transaction_id=payload.transaction_id,
        user_id=payload.user_id,
        signature=payload.signature,
        secret=settings.webhook_secret,
    ):
        raise ApiError(400, "invalid_signature", "Webhook signature is invalid")

    try:
        async with request.app.ctx.session_factory.begin() as session:
            user = await session.scalar(
                select(User).where(User.id == payload.user_id).with_for_update()
            )
            if user is None or user.role != "user":
                raise ApiError(404, "user_not_found", "User was not found")

            existing = await session.scalar(
                select(Payment).where(Payment.transaction_id == payload.transaction_id)
            )
            if existing is not None:
                account = await session.get(Account, existing.account_id)
                return json(
                    {
                        "status": "duplicate",
                        "transaction_id": existing.transaction_id,
                        "balance": format(account.balance, ".2f") if account else None,
                    }
                )

            account = await session.scalar(
                select(Account).where(Account.id == payload.account_id).with_for_update()
            )
            if account is None:
                account = Account(
                    id=payload.account_id,
                    user_id=user.id,
                    balance=Decimal("0.00"),
                )
                session.add(account)
                await session.flush()
            elif account.user_id != user.id:
                raise ApiError(409, "account_owner_mismatch", "Account belongs to another user")

            account.balance += payload.amount
            payment = Payment(
                transaction_id=payload.transaction_id,
                user_id=user.id,
                account_id=account.id,
                amount=payload.amount,
            )
            session.add(payment)
            await session.flush()
            balance = format(account.balance, ".2f")
    except IntegrityError:
        # A concurrent request with the same transaction_id won the race.
        async with request.app.ctx.session_factory() as session:
            existing = await session.scalar(
                select(Payment).where(Payment.transaction_id == payload.transaction_id)
            )
            if existing is None:
                raise
            account = await session.get(Account, existing.account_id)
            return json(
                {
                    "status": "duplicate",
                    "transaction_id": existing.transaction_id,
                    "balance": format(account.balance, ".2f") if account else None,
                }
            )

    return json(
        {
            "status": "processed",
            "transaction_id": payload.transaction_id,
            "balance": balance,
        },
        status=201,
    )


__all__ = ["api", "build_webhook_signature"]

