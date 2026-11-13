"""공통 오류 본문 {code, message, details}."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def bad(message: str, field: str | None = None, code: str = "VALIDATION_ERROR") -> ApiError:
    return ApiError(400, code, message, {"field": field} if field else {})


def not_found(code: str, message: str) -> ApiError:
    return ApiError(404, code, message)


def conflict(code: str, message: str, details: dict | None = None) -> ApiError:
    return ApiError(409, code, message, details)


def duplicate(message: str, field: str | None = None) -> ApiError:
    return ApiError(409, "DUPLICATE", message, {"field": field} if field else {})


def forbidden(menu_id: str | None = None, message: str = "권한이 없습니다.", code: str = "FORBIDDEN") -> ApiError:
    return ApiError(403, code, message, {"menu_id": menu_id} if menu_id else {})


UNAUTH_MESSAGE = "세션이 만료되었거나 유효하지 않습니다."


def unauthorized(message: str = UNAUTH_MESSAGE, code: str = "UNAUTHORIZED") -> ApiError:
    return ApiError(401, code, message)


def _body(code, message, details=None):
    return {"code": code, "message": message, "details": details or {}}


_HTTP_CODES = {404: ("NOT_FOUND", "요청한 리소스를 찾을 수 없습니다."),
               405: ("METHOD_NOT_ALLOWED", "허용되지 않는 요청 방식입니다."),
               401: ("UNAUTHORIZED", UNAUTH_MESSAGE),
               403: ("FORBIDDEN", "권한이 없습니다.")}


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, e: ApiError):
        return JSONResponse(_body(e.code, e.message, e.details), status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError):
        errs = [{"loc": [str(x) for x in err.get("loc", [])], "type": err.get("type")} for err in e.errors()]
        return JSONResponse(_body("INVALID_FORMAT", "요청 형식이 올바르지 않습니다.", {"errors": errs}), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, e: StarletteHTTPException):
        code, msg = _HTTP_CODES.get(e.status_code, ("HTTP_ERROR", "요청을 처리할 수 없습니다."))
        return JSONResponse(_body(code, msg), status_code=e.status_code)
