from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/payments"
    jwt_secret: str = "local-development-secret-at-least-32-bytes"
    webhook_secret: str = "gfdmhghif38yrf9ew0jkf32"
    access_token_ttl_minutes: int = Field(default=60, ge=1, le=1440)
