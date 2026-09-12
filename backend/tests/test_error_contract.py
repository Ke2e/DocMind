"""任务 1.6 验证：所有错误出口都归一为 `{code, message, detail?}`，且不含内部细节。"""

from __future__ import annotations

from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.errors import ErrorCode
from app.main import create_app

LEAK_MARKERS = ("Traceback", "site-packages", "SELECT", "secret", "app/core")


def _app_with_probe_routes():
    """在真实应用上挂两条探针路由，用于触发 422 与未捕获异常。"""
    app = create_app()
    router = APIRouter()

    @router.get("/__probe/echo")
    async def echo(n: int) -> dict[str, int]:
        return {"n": n}

    @router.get("/__probe/boom")
    async def boom() -> None:
        raise RuntimeError(
            "内部细节泄漏测试：Traceback 位于 /srv/app/core/secret.py，"
            "SELECT * FROM users WHERE api_key='sk-leak'"
        )

    app.include_router(router)
    return app


def _client(app, *, raise_app_exceptions: bool) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions),
        base_url="http://testserver",
    )


def _assert_contract(body: dict) -> None:
    assert set(body) <= {"code", "message", "detail"}
    assert isinstance(body["code"], str) and body["code"]
    assert isinstance(body["message"], str) and body["message"]
    assert "code" in body and "message" in body


def _assert_no_leak(text: str) -> None:
    for marker in LEAK_MARKERS:
        assert marker not in text, f"错误响应泄漏了内部细节：{marker}"


async def test_framework_404_uses_contract() -> None:
    async with _client(_app_with_probe_routes(), raise_app_exceptions=True) as ac:
        resp = await ac.get("/__probe/does-not-exist")

    assert resp.status_code == 404
    body = resp.json()
    _assert_contract(body)
    assert body["code"] == ErrorCode.NOT_FOUND.value
    _assert_no_leak(resp.text)


async def test_framework_422_uses_contract() -> None:
    async with _client(_app_with_probe_routes(), raise_app_exceptions=True) as ac:
        resp = await ac.get("/__probe/echo", params={"n": "not-a-number"})

    assert resp.status_code == 422
    body = resp.json()
    _assert_contract(body)
    assert body["code"] == ErrorCode.VALIDATION_ERROR.value
    assert body["detail"][0]["field"].endswith("n")
    _assert_no_leak(resp.text)


async def test_unexpected_exception_hides_internals() -> None:
    app = _app_with_probe_routes()
    async with _client(app, raise_app_exceptions=False) as ac:
        resp = await ac.get("/__probe/boom")

    assert resp.status_code == 500
    body = resp.json()
    _assert_contract(body)
    assert body["code"] == ErrorCode.INTERNAL_ERROR.value
    assert "detail" not in body
    _assert_no_leak(resp.text)


async def test_business_error_uses_contract(app) -> None:
    """service 层抛 AppError 时同样归一（后续 4.x / 7.x 依赖此行为）。"""
    from fastapi import APIRouter
    from app.core.errors import NotFoundError

    router = APIRouter()

    @router.get("/__probe/business")
    async def business() -> None:
        raise NotFoundError("知识库不存在")

    app.include_router(router)
    async with _client(app, raise_app_exceptions=False) as ac:
        resp = await ac.get("/__probe/business")

    assert resp.status_code == 404
    body = resp.json()
    _assert_contract(body)
    assert body["message"] == "知识库不存在"
    _assert_no_leak(resp.text)
