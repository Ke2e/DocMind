"""任务 1.2 验证：空应用可启动，`/health/live` 返回 200 且不依赖外部服务。"""

from __future__ import annotations

from httpx import AsyncClient


async def test_live_returns_ok_without_external_deps(client: AsyncClient) -> None:
    resp = await client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_ready_reports_dependency_status(client: AsyncClient) -> None:
    """就绪端点必须给出可读的依赖结论：全通 200，否则 503 且逐个说明。"""
    resp = await client.get("/health/ready")
    body = resp.json()

    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert body["status"] == "ok"
        assert set(body["checks"]) == {"database", "redis"}
        assert all(reason is None for reason in body["checks"].values())
    else:
        assert body["code"] == "upstream_error"
        assert set(body["detail"]["checks"]) == {"database", "redis"}
        assert any(body["detail"]["checks"].values())
        # 不得泄漏连接串或密钥
        assert "@" not in resp.text or "postgresql" not in resp.text
