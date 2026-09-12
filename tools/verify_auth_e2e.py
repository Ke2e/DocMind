"""第 3 组（账号体系）的端到端验收：**经 nginx 打真实 HTTP**，不是 ASGI 直连。

为什么要单独有这么一份：
- `pytest` 走的是 ASGI 直连（`ASGITransport`），它证明代码逻辑对，但**证明不了容器 + nginx 这条链路可用**；
- 第 1 组的教训是"容器 healthy ≠ 对外可用"，所以凡是"链路通"的结论都必须打真实请求。

运行方式（必须用 backend 的 venv，本机无 curl）：

    cd backend
    .venv/Scripts/python.exe ../tools/verify_auth_e2e.py

前提：`docker compose up -d --build` 已完成且容器稳定
（**不要紧接在重建之后就跑**——跨容器切换窗口的写请求不可信，见 docs/findings.md D-031）。

收尾：脚本会在开发库 `docmind` 里留下一个 `e2e_3x_*` 账号，清理方式见脚本末尾打印的提示。
（10.1 的端到端验收脚本会把这部分并入统一入口。）
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]


def _local_env() -> dict[str, str]:
    """读仓库根 `.env`，只解析 KEY=VALUE 与 `#` 注释（与 backend/tests/conftest.py 同一套约定）。

    端口与有效期都从配置取，不在脚本里写死 —— 本文件被 standards 审查点名过这一点：
    硬编码 8080 / 86400 会在开发者改了 `.env` 之后变成假失败。
    """
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return {}
    values: dict[str, str] = {}
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


_ENV = _local_env()
BASE = f"http://127.0.0.1:{_ENV.get('NGINX_HOST_PORT', '8080')}"
EXPECTED_EXPIRES_IN = int(_ENV.get("TOKEN_EXPIRE_MINUTES", "1440")) * 60

STAMP = int(time.time())
USERNAME = f"e2e_3x_{STAMP}"
PASSWORD = "docmind123"

results: list[tuple[str, str, str]] = []


def check(name: str, cond: bool, info: str = "") -> None:
    results.append((name, "PASS" if cond else "FAIL", info))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"   [{info}]" if info else ""))


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=30) as c:
        r = c.get("/health/ready")
        check(
            "回归：/health/ready 200",
            r.status_code == 200 and r.json().get("status") == "ok",
            str(r.status_code),
        )

        # ---- 任务 3.1 注册 ----
        r = c.post("/api/auth/register", json={"username": USERNAME, "password": PASSWORD})
        check("3.1 注册成功 201", r.status_code == 201, f"{r.status_code} {r.text[:70]}")
        user_id = r.json().get("id") if r.status_code == 201 else None
        check("3.1 响应不含口令或摘要", "password" not in r.text, r.text[:70])

        r = c.post("/api/auth/register", json={"username": USERNAME, "password": PASSWORD})
        check(
            "3.1 用户名重复 409",
            r.status_code == 409 and r.json().get("code") == "conflict",
            f"{r.status_code} {r.text[:70]}",
        )

        r = c.post("/api/auth/register", json={"username": USERNAME + "_w", "password": "abcdefgh"})
        check(
            "3.1 弱密码 422 且点名原因",
            r.status_code == 422 and "包含数字" in json.dumps(r.json(), ensure_ascii=False),
            f"{r.status_code} {r.text[:110]}",
        )

        # ---- 任务 3.2 登录 ----
        r = c.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
        logged_in = r.status_code == 200
        check("3.2 登录成功并返回凭证", logged_in and bool(r.json().get("access_token")), str(r.status_code))
        token = r.json().get("access_token", "") if logged_in else ""
        check(
            f"3.2 expires_in = {EXPECTED_EXPIRES_IN}（取自 .env 的 TOKEN_EXPIRE_MINUTES）",
            r.json().get("expires_in") == EXPECTED_EXPIRES_IN,
            str(r.json().get("expires_in")),
        )

        # ---- 任务 3.3 鉴权 ----
        r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        check(
            "3.3 带凭证访问受保护接口 200",
            r.status_code == 200 and r.json().get("id") == user_id,
            f"{r.status_code} {r.text[:70]}",
        )

        r = c.get("/api/auth/me")
        check(
            "3.3 无凭证被拒 401",
            r.status_code == 401 and r.json().get("code") == "unauthorized",
            f"{r.status_code} {r.text[:70]}",
        )

        r = c.get("/api/auth/me", headers={"Authorization": "Bearer forged.token.value"})
        check("3.3 伪造凭证被拒 401", r.status_code == 401, f"{r.status_code} {r.text[:70]}")

        # ---- 任务 3.2 失败不可区分 ----
        r1 = c.post("/api/auth/login", json={"username": USERNAME, "password": "wrong123"})
        r2 = c.post("/api/auth/login", json={"username": f"ghost_{STAMP}", "password": "wrong123"})
        check(
            "3.2 密码错与用户不存在的响应完全一致",
            r1.status_code == r2.status_code == 401 and r1.json() == r2.json(),
            f"{r1.status_code}/{r2.status_code} {r1.text[:60]}",
        )

    print()
    print(f"本轮注册的测试账号：{USERNAME}  (id={user_id})")
    print(
        "清理：docker exec docmind-pg psql -U docmind -d docmind "
        "-c \"DELETE FROM users WHERE username LIKE 'e2e%';\""
    )
    failed = [name for name, status, _ in results if status == "FAIL"]
    print(f"合计 {len(results)} 项，FAIL {len(failed)} 项" + (f"：{failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
