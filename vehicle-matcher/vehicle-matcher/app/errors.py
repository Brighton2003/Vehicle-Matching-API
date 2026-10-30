"""Consistent JSON error responses: {"error": "<code>", "message": "<text>"}.

Nothing in the API should ever surface a raw Python exception or FastAPI's
default ``{"detail": [...]}`` payload.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("vehicle_matcher")


class APIError(Exception):
    """Raise from anywhere to return a clean error response."""

    def __init__(self, status_code: int, error: str, message: str):
        self.status_code = status_code
        self.error = error
        self.message = message


def _num(value) -> str:
    return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)


def _describe(err: dict) -> tuple[str, str]:
    """Turn one pydantic error into (field, human readable message)."""
    loc = list(err.get("loc", ()))
    field = ".".join(str(p) for p in loc[1:])  # loc[0] is "body" / "query"
    etype, ctx, msg = err.get("type", ""), err.get("ctx", {}) or {}, err.get("msg", "")

    if etype == "json_invalid":
        return "", "Request body is not valid JSON"
    if not field:  # error about the body / query string as a whole
        if etype == "missing":
            return "", "Request body is required"
        if etype in ("model_attributes_type", "dict_type", "model_type"):
            return "", "Request body must be a JSON object"
        return "", msg.removeprefix("Value error, ")

    if etype == "value_error":
        return field, f"{field} {msg.removeprefix('Value error, ')}"

    text = {
        "greater_than": lambda: f"must be greater than {_num(ctx.get('gt'))}",
        "greater_than_equal": lambda: f"must be greater than or equal to {_num(ctx.get('ge'))}",
        "less_than": lambda: f"must be less than {_num(ctx.get('lt'))}",
        "less_than_equal": lambda: f"must be less than or equal to {_num(ctx.get('le'))}",
        "missing": lambda: "is required",
        "extra_forbidden": lambda: "is not a recognised field",
        "string_type": lambda: "must be a string",
        "int_type": lambda: "must be a whole number",
        "int_parsing": lambda: "must be a whole number",
        "int_from_float": lambda: "must be a whole number",
        "float_type": lambda: "must be a number",
        "float_parsing": lambda: "must be a number",
        "bool_type": lambda: "must be true or false",
        "bool_parsing": lambda: "must be true or false",
        "literal_error": lambda: f"must be one of: {ctx.get('expected', '').replace(chr(39), '')}",
        "string_too_long": lambda: f"must be at most {ctx.get('max_length')} characters",
    }.get(etype)
    return field, f"{field} {text()}" if text else f"{field}: {msg}"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.error, "message": exc.message})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            field, message = _describe(err)
            details.append({"field": field, "message": message})
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "message": "; ".join(d["message"] for d in details),
                "details": details,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        codes = {404: "not_found", 405: "method_not_allowed"}
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": codes.get(exc.status_code, "http_error"), "message": str(exc.detail)},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error", "message": "An unexpected error occurred."},
        )
