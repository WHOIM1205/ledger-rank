"""Centralized exception handling -> uniform error envelope.

Every error the API can emit is rendered as:

    {"error": {"code": "...", "message": "...", "details": {...}}}

Three handlers cover everything:

* LedgerRankError      -> uses the exception's own http_status + code
                          (UserNotFoundError 404, DuplicateRequestConflictError
                          409, InvalidTransactionTypeError 422,
                          TransactionProcessingError 500, ...).
* RequestValidationError (FastAPI/Pydantic) -> 422, reshaped into the same
                          envelope so schema failures look like every other error.
* Exception (catch-all) -> 500, logged server-side, never leaks internals.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import LedgerRankError

logger = logging.getLogger("ledgerrank")


async def _ledgerrank_error_handler(
    _request: Request, exc: LedgerRankError
) -> JSONResponse:
    """Render any typed domain error using its declared status + envelope."""
    return JSONResponse(status_code=exc.http_status, content=exc.to_envelope())


async def _validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Reshape Pydantic/FastAPI validation errors into our envelope (422)."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                # jsonable_encoder makes Pydantic's error objects JSON-safe.
                "details": {"errors": jsonable_encoder(exc.errors())},
            }
        },
    )


async def _unhandled_error_handler(
    _request: Request, exc: Exception
) -> JSONResponse:
    """Last-resort 500. Log the real cause; return a generic, safe message."""
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
                "details": {},
            }
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    """Wire all handlers onto the app. Called once at startup."""
    app.add_exception_handler(LedgerRankError, _ledgerrank_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
