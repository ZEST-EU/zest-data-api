"""Service error hierarchy + FastAPI handlers.

Mirrors the sibling zest-model-service contract: every error response is
``{"error": {"code", "message", "detail"}}`` with a stable string code.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ServiceError(Exception):
    """Base class for expected, client-facing errors."""

    code = "INTERNAL_ERROR"
    status_code = 500

    def __init__(self, message: str, detail: Any = None):
        super().__init__(message)
        self.message = message
        self.detail = detail

    def to_response(self) -> JSONResponse:
        body = {"error": {"code": self.code, "message": self.message, "detail": self.detail}}
        return JSONResponse(status_code=self.status_code, content=body)


class NotFoundError(ServiceError):
    code = "NOT_FOUND"
    status_code = 404


class ConflictError(ServiceError):
    code = "CONFLICT"
    status_code = 409


class ValidationError(ServiceError):
    code = "INVALID_REQUEST"
    status_code = 422


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def _service_error(_: Request, exc: ServiceError) -> JSONResponse:
        return exc.to_response()

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Request validation failed.",
                    "detail": exc.errors(),
                }
            },
        )
