from decimal import Decimal

import pytest

from app.security import build_webhook_signature
from tests.conftest import login


@pytest.mark.asyncio
async def test_user_can_login_and_read_profile(app):
    token = await login(app, "user@example.com", "UserPass123!")
    _, response = await app.asgi_client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status == 200
    assert response.json["id"] == 1
    assert response.json["role"] == "user"


@pytest.mark.asyncio
async def test_payment_webhook_is_idempotent(app):
    payload = {
        "transaction_id": "5eae174f-7cd0-472c-bd36-35660f00132b",
        "user_id": 1,
        "account_id": 1,
        "amount": 100,
    }
    payload["signature"] = build_webhook_signature(
        account_id=1,
        amount=Decimal("100"),
        transaction_id=payload["transaction_id"],
        user_id=1,
        secret="gfdmhghif38yrf9ew0jkf32",
    )

    _, first = await app.asgi_client.post("/api/v1/payments/webhook", json=payload)
    _, second = await app.asgi_client.post("/api/v1/payments/webhook", json=payload)

    assert first.status == 201
    assert first.json["status"] == "processed"
    assert first.json["balance"] == "100.00"
    assert second.status == 200
    assert second.json["status"] == "duplicate"
    assert second.json["balance"] == "100.00"

    token = await login(app, "user@example.com", "UserPass123!")
    headers = {"Authorization": f"Bearer {token}"}
    _, accounts = await app.asgi_client.get("/api/v1/accounts", headers=headers)
    _, payments = await app.asgi_client.get("/api/v1/payments", headers=headers)
    assert accounts.json["items"][0]["balance"] == "100.00"
    assert len(payments.json["items"]) == 1


@pytest.mark.asyncio
async def test_invalid_webhook_signature_is_rejected(app):
    _, response = await app.asgi_client.post(
        "/api/v1/payments/webhook",
        json={
            "transaction_id": "bad-signature-transaction",
            "user_id": 1,
            "account_id": 1,
            "amount": 100,
            "signature": "0" * 64,
        },
    )
    assert response.status == 400
    assert response.json["error"]["code"] == "invalid_signature"


@pytest.mark.asyncio
async def test_admin_can_create_update_list_and_delete_user(app):
    token = await login(app, "admin@example.com", "AdminPass123!")
    headers = {"Authorization": f"Bearer {token}"}

    _, created = await app.asgi_client.post(
        "/api/v1/admin/users",
        headers=headers,
        json={
            "email": "new@example.com",
            "password": "NewUserPass123!",
            "full_name": "New User",
        },
    )
    assert created.status == 201
    user_id = created.json["id"]

    _, updated = await app.asgi_client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers=headers,
        json={"full_name": "Updated User"},
    )
    assert updated.status == 200
    assert updated.json["full_name"] == "Updated User"

    _, listed = await app.asgi_client.get("/api/v1/admin/users", headers=headers)
    assert listed.status == 200
    assert any(item["id"] == user_id for item in listed.json["items"])

    _, deleted = await app.asgi_client.delete(
        f"/api/v1/admin/users/{user_id}", headers=headers
    )
    assert deleted.status == 204

