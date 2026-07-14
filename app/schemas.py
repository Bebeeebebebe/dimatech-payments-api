from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginInput(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.casefold()
        if "@" not in value:
            raise ValueError("invalid email")
        return value


class UserCreateInput(LoginInput):
    full_name: str = Field(min_length=1, max_length=200)


class UserUpdateInput(ApiModel):
    email: str | None = Field(default=None, min_length=3, max_length=320)
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.casefold()
        if "@" not in value:
            raise ValueError("invalid email")
        return value


class WebhookInput(ApiModel):
    transaction_id: str = Field(min_length=1, max_length=128)
    account_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    signature: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


def validate_json(model: type[ApiModel], value: Any) -> ApiModel:
    return model.model_validate(value or {})

