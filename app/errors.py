from sanic import Request
from sanic.response import json


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def handle_api_error(_: Request, error: ApiError):
    return json(
        {"error": {"code": error.code, "message": error.message}},
        status=error.status,
    )

