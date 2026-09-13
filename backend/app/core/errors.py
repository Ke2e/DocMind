"""统一错误响应契约（任务 1.6）。

约定：所有错误响应体固定为 `{code, message, detail?}`。
- `code`：机器可读的错误分类，取值见 `ErrorCode`
- `message`：面向用户的可读说明，可直接展示
- `detail`：可选补充（如字段级校验信息），缺省时不出现

**硬约束**：任何错误响应都不得包含堆栈、模块路径、SQL 语句等内部细节。
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """机器可读错误码。新增错误一律先在此登记，避免各处散落字符串。"""

    VALIDATION_ERROR = "validation_error"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    UPSTREAM_ERROR = "upstream_error"
    INTERNAL_ERROR = "internal_error"


# 框架抛出的 HTTP 状态码 -> 业务错误码
_STATUS_TO_CODE: dict[int, ErrorCode] = {
    400: ErrorCode.VALIDATION_ERROR,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.CONFLICT,
    413: ErrorCode.PAYLOAD_TOO_LARGE,
    415: ErrorCode.UNSUPPORTED_MEDIA_TYPE,
    422: ErrorCode.VALIDATION_ERROR,
}

_DEFAULT_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.VALIDATION_ERROR: "请求参数不合法",
    ErrorCode.UNAUTHORIZED: "请先登录",
    ErrorCode.FORBIDDEN: "没有权限执行该操作",
    ErrorCode.NOT_FOUND: "请求的资源不存在",
    ErrorCode.CONFLICT: "请求与当前资源状态冲突",
    ErrorCode.PAYLOAD_TOO_LARGE: "提交内容超出体积上限",
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: "不支持该文件类型",
    ErrorCode.UPSTREAM_ERROR: "上游服务暂时不可用，请稍后重试",
    ErrorCode.INTERNAL_ERROR: "服务器内部错误",
}


def error_payload(
    code: ErrorCode,
    message: str,
    detail: Any | None = None,
) -> dict[str, Any]:
    """构造错误响应体。`detail` 为 None 时不输出该键。"""
    payload: dict[str, Any] = {"code": code.value, "message": message}
    if detail is not None:
        payload["detail"] = detail
    return payload


class AppError(Exception):
    """业务错误基类。service 层抛它，由全局处理器翻译成错误响应体。"""

    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        *,
        status_code: int,
        detail: Any | None = None,
    ) -> None:
        self.code = code
        self.message = message or _DEFAULT_MESSAGES.get(code, "请求处理失败")
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)


class NotFoundError(AppError):
    def __init__(self, message: str | None = None, *, detail: Any | None = None) -> None:
        super().__init__(ErrorCode.NOT_FOUND, message, status_code=404, detail=detail)


class ConflictError(AppError):
    def __init__(self, message: str | None = None, *, detail: Any | None = None) -> None:
        super().__init__(ErrorCode.CONFLICT, message, status_code=409, detail=detail)


class ValidationFailedError(AppError):
    def __init__(self, message: str | None = None, *, detail: Any | None = None) -> None:
        super().__init__(ErrorCode.VALIDATION_ERROR, message, status_code=400, detail=detail)


class ForbiddenError(AppError):
    def __init__(self, message: str | None = None, *, detail: Any | None = None) -> None:
        super().__init__(ErrorCode.FORBIDDEN, message, status_code=403, detail=detail)


class UnauthorizedError(AppError):
    """未登录 / 凭证不可用（任务 3.2 / 3.3）。

    凭证过期、签名不符、账号已不存在……一律用它，且**不要**在 message 里区分原因。
    """

    def __init__(self, message: str | None = None, *, detail: Any | None = None) -> None:
        super().__init__(ErrorCode.UNAUTHORIZED, message, status_code=401, detail=detail)


class PayloadTooLargeError(AppError):
    """提交内容超出体积上限（任务 5.1，`MAX_UPLOAD_MB`）。

    `code`/`status_code` 取自 1.6 契约里早已登记、此前无人使用的 `payload_too_large` / 413；
    与 nginx 外层闸门（`client_max_body_size`）同码，前端只需处理一种。
    """

    def __init__(self, message: str | None = None, *, detail: Any | None = None) -> None:
        super().__init__(ErrorCode.PAYLOAD_TOO_LARGE, message, status_code=413, detail=detail)


class UnsupportedMediaTypeError(AppError):
    """文件类型不在白名单内（任务 5.1，`ALLOWED_EXTENSIONS`）。

    刻意用 415 而非笼统的 422：前端要能把它与"字段缺失/格式不对"分开提示。
    """

    def __init__(self, message: str | None = None, *, detail: Any | None = None) -> None:
        super().__init__(
            ErrorCode.UNSUPPORTED_MEDIA_TYPE, message, status_code=415, detail=detail
        )


class UpstreamError(AppError):
    """上游依赖（broker / 外部服务）不可用（任务 5.3 起使用）。

    与"我们自己的代码出错"（500）区分开：这类失败通常是暂时性的、重试可能成功，
    所以用 503 且文案里明说"请稍后重试"。`code`/`status_code` 取 1.6 契约里
    已登记的 `upstream_error`。
    """

    def __init__(self, message: str | None = None, *, detail: Any | None = None) -> None:
        super().__init__(ErrorCode.UPSTREAM_ERROR, message, status_code=503, detail=detail)


def _sanitize_validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    """只保留字段位置与原因，丢掉 pydantic 附加的内部上下文。"""
    return [
        {
            "field": ".".join(str(part) for part in err.get("loc", ())),
            "reason": err.get("msg", "不合法"),
            "type": err.get("type", "unknown"),
        }
        for err in exc.errors()
    ]


def register_exception_handlers(app: FastAPI) -> None:
    """把全部异常出口收归到统一错误响应体。"""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_payload(
                ErrorCode.VALIDATION_ERROR,
                _DEFAULT_MESSAGES[ErrorCode.VALIDATION_ERROR],
                _sanitize_validation_errors(exc),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_TO_CODE.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        message = exc.detail if isinstance(exc.detail, str) else _DEFAULT_MESSAGES[code]
        return JSONResponse(status_code=exc.status_code, content=error_payload(code, message))

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        # 内部细节只进日志，不进响应体
        logger.exception("未处理异常：%s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_payload(ErrorCode.INTERNAL_ERROR, _DEFAULT_MESSAGES[ErrorCode.INTERNAL_ERROR]),
        )
