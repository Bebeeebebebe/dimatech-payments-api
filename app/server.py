from uuid import uuid4

from sanic import Sanic

from app.api import api
from app.config import Settings
from app.database import build_database
from app.errors import ApiError, handle_api_error


def create_app(settings: Settings | None = None, *, name: str | None = None) -> Sanic:
    app = Sanic(name or f"DimaTechPayments_{uuid4().hex}")
    app.ctx.settings = settings or Settings()
    app.ctx.engine, app.ctx.session_factory = build_database(app.ctx.settings.database_url)
    app.blueprint(api)
    app.exception(ApiError)(handle_api_error)

    @app.after_server_stop
    async def close_database(app: Sanic):
        await app.ctx.engine.dispose()

    return app


app = create_app(name="DimaTechPayments")
