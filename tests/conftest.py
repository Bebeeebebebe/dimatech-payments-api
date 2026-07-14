from pathlib import Path
from uuid import uuid4

import pytest_asyncio

from app.config import Settings
from app.models import Account, Base, User
from app.security import hash_password
from app.server import create_app


@pytest_asyncio.fixture
async def app(tmp_path: Path):
    database_file = tmp_path / "test.db"
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{database_file.as_posix()}",
        jwt_secret="test-jwt-secret-at-least-32-bytes",
        webhook_secret="gfdmhghif38yrf9ew0jkf32",
        access_token_ttl_minutes=60,
    )
    sanic_app = create_app(settings, name=f"TestPayments_{uuid4().hex}")

    async with sanic_app.ctx.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sanic_app.ctx.session_factory.begin() as session:
        session.add_all(
            [
                User(
                    id=1,
                    email="user@example.com",
                    full_name="Test User",
                    password_hash=hash_password("UserPass123!"),
                    role="user",
                ),
                User(
                    id=2,
                    email="admin@example.com",
                    full_name="Test Administrator",
                    password_hash=hash_password("AdminPass123!"),
                    role="admin",
                ),
                Account(id=1, user_id=1, balance=0),
            ]
        )

    yield sanic_app
    await sanic_app.ctx.engine.dispose()


async def login(app, email: str, password: str) -> str:
    _, response = await app.asgi_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status == 200
    return response.json["access_token"]
