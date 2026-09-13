"""第 4 组（知识库）的端到端验收：**经 nginx 打真实 HTTP** + **查库核实**。

为什么要有这一份（与 `verify_auth_e2e.py` 同理）：
`pytest` 走 ASGI 直连，证明代码逻辑对，但证明不了「容器 + nginx」这条链路可用；
第 1 组的教训是「容器 healthy ≠ 对外可用」。

本脚本比第 3 组多一条规矩：**写操作的"成功"以查库为准**，不只看接口回了 201。
非空拒删 / 墓碑计数这两个验收点必须造出"库里有文档"的状态，而 5.x 的上传接口还没实现，
所以脚本用 `docker exec docmind-pg psql` 直接插桩（只插桩**数据**，被测的是 4.x 的接口）。

运行方式（必须用 backend 的 venv，且 PATH 里要有 docker；本机无 curl）：

    export PATH="/d/Docker/App/resources/bin:...:/usr/bin:/bin"
    cd backend
    .venv/Scripts/python.exe ../tools/verify_knowledge_base_e2e.py

前提：`docker compose up -d --build` 已完成且容器**稳定**
（不要紧接在重建之后就跑——跨容器切换窗口的写请求不可信，见 docs/findings.md D-031）。

收尾：脚本末尾会清掉自己建的两个账号及其知识库（文档随知识库物理清除），并**查库确认**清空。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
PG_CONTAINER = "docmind-pg"

# 名称上限不写死：与实现共用同一个常量（`KB_NAME_MAX_LENGTH` = DDL 的 VARCHAR(128)）。
# 脚本以 `backend/` 为工作目录运行，故把 backend 加进 sys.path 才能 import app 包。
sys.path.insert(0, str(REPO_ROOT / "backend"))
from app.models.knowledge_base import KB_NAME_MAX_LENGTH  # noqa: E402


def _local_env() -> dict[str, str]:
    """读仓库根 `.env`（与 backend/tests/conftest.py 同一套约定）。

    端口、库名、账号全部从配置取，不在脚本里写死 —— 硬编码会在开发者改了 `.env`
    之后变成假失败（第 3 组 standards 审查点名过这一点）。
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
PG_USER = _ENV.get("POSTGRES_USER", "docmind")
PG_DB = _ENV.get("POSTGRES_DB", "docmind")

STAMP = int(time.time())
PASSWORD = "docmind123"
KBS = "/api/knowledge-bases"
# 名字带时间戳：清理时能精确定位本轮造的数据，不会误伤开发库里别的东西
KB_NAME = f"e2e 库 {STAMP}"
KB_NAME_RENAMED = f"e2e 库 {STAMP} 改名后"
SPOOF_KB_NAME = f"e2e 伪装归属 {STAMP}"
TOMB_KB_NAME = f"e2e 只剩墓碑 {STAMP}"

results: list[tuple[str, str, str]] = []


def check(name: str, cond: bool, info: str = "") -> None:
    results.append((name, "PASS" if cond else "FAIL", info))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"   [{info}]" if info else ""))


def psql(sql: str) -> str:
    """在 pg 容器里跑一条 SQL 并取裸值（`-tAc`）。宿主没有 psql，只能走容器。

    `encoding="utf-8"` 不能省：本机 locale 是 GBK，而容器里的 psql 输出 UTF-8，
    用默认编码解码会把知识库名读成乱码，让"查库核对"变成假失败。
    """
    proc = subprocess.run(
        ["docker", "exec", PG_CONTAINER, "psql", "-U", PG_USER, "-d", PG_DB, "-tAc", sql],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"psql 执行失败：{proc.stderr.strip()}")
    return proc.stdout.strip()


def kb_name_in_db(kb_id: int) -> str:
    return psql(f"SELECT name FROM knowledge_bases WHERE id = {kb_id}")


def stub_document(user_id: int, kb_id: int, *, index: int, deleted: bool) -> None:
    """插一条文档桩（5.x 落地后可换成走上传接口）。

    `status='ready'` 是 `documents.status` 的合法取值（app/models/enums.py）。

    文件名由 `index` 在脚本内部拼出，**不接受外部字符串** —— 这样这条 SQL 里
    所有的值都是 int / bool，f-string 拼接不会成为注入面。
    （试过用 psql 的 `-v` 变量传字符串，但 `docker exec` 会把它吞掉、变量不会被替换。）
    """
    deleted_expr = "NOW()" if deleted else "NULL"
    psql(
        "INSERT INTO documents (user_id, kb_id, original_filename, storage_path, file_type, "
        "file_size_bytes, status, deleted_at) VALUES "
        f"({user_id}, {kb_id}, 'stub-{index}.pdf', 'uploads/stub.pdf', 'pdf', 1024, 'ready', {deleted_expr})"
    )


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=30) as c:
        r = c.get("/health/ready")
        check(
            "回归：/health/ready 200",
            r.status_code == 200 and r.json().get("status") == "ok",
            str(r.status_code),
        )

        # ---- 准备两个账号（双账号交叉是所有越权用例的前提）----
        accounts: dict[str, dict[str, object]] = {}
        for tag in ("a", "b"):
            username = f"e2e_4x_{tag}_{STAMP}"
            reg = c.post("/api/auth/register", json={"username": username, "password": PASSWORD})
            if reg.status_code != 201:
                check(f"准备：注册账号 {tag} 201", False, f"{reg.status_code} {reg.text[:70]}")
                return _summary()
            login = c.post("/api/auth/login", json={"username": username, "password": PASSWORD})
            accounts[tag] = {
                "username": username,
                "id": reg.json()["id"],
                "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
            }
        alice, bob = accounts["a"], accounts["b"]
        alice_id, bob_id = int(alice["id"]), int(bob["id"])  # type: ignore[arg-type]
        check("准备：双账号注册并登录", True, f"a.id={alice_id} b.id={bob_id}")

        # ---------------- 4.1 创建 ----------------
        r = c.post(
            KBS, json={"name": KB_NAME, "description": "e2e"}, headers=alice["headers"]
        )
        created = r.status_code == 201
        check("4.1 创建成功 201", created, f"{r.status_code} {r.text[:90]}")
        kb_id = int(r.json()["id"]) if created else 0
        check(
            "4.1 响应含 document_count=0",
            created and r.json().get("document_count") == 0,
            str(r.json().get("document_count")),
        )
        owner = psql(f"SELECT user_id FROM knowledge_bases WHERE id = {kb_id}")
        check("4.1 归属落库正确（查库）", owner == str(alice_id), f"owner={owner}")

        r = c.post(KBS, json={"name": KB_NAME}, headers=alice["headers"])
        check(
            "4.1 同账号重名 409",
            r.status_code == 409 and r.json().get("code") == "conflict",
            f"{r.status_code} {r.text[:80]}",
        )
        check(
            "4.1 重名后库里仍只有 1 个库（查库）",
            psql(f"SELECT count(*) FROM knowledge_bases WHERE user_id = {alice_id}") == "1",
        )

        r = c.post(KBS, json={"name": "   "}, headers=alice["headers"])
        check(
            "4.1 空名 422 且说明原因",
            r.status_code == 422 and "不能为空" in json.dumps(r.json(), ensure_ascii=False),
            f"{r.status_code} {r.text[:90]}",
        )

        r = c.post(KBS, json={"name": "库" * (KB_NAME_MAX_LENGTH + 1)}, headers=alice["headers"])
        check(
            f"4.1 超长名（{KB_NAME_MAX_LENGTH + 1} 字符）422",
            r.status_code == 422
            and f"长度不超过 {KB_NAME_MAX_LENGTH}" in json.dumps(r.json(), ensure_ascii=False),
            f"{r.status_code} {r.text[:90]}",
        )

        # 跨账号同名应当允许（唯一性范围是"同一账号下"）
        r = c.post(KBS, json={"name": KB_NAME}, headers=bob["headers"])
        bob_kb_id = int(r.json()["id"]) if r.status_code == 201 else 0
        check("4.1 跨账号同名允许 201", r.status_code == 201, f"{r.status_code} {r.text[:80]}")

        # 归属只由凭证推导：请求体里塞别人的 user_id 不生效
        r = c.post(
            KBS,
            json={"name": SPOOF_KB_NAME, "user_id": bob_id},
            headers=alice["headers"],
        )
        spoofed_kb_id = int(r.json()["id"]) if r.status_code == 201 else 0
        spoof_owner = psql(f"SELECT user_id FROM knowledge_bases WHERE id = {spoofed_kb_id}")
        check(
            "4.1 请求体里的 user_id 被忽略（查库归属）",
            r.status_code == 201 and spoof_owner == str(alice_id),
            f"{r.status_code} owner={spoof_owner}（写在 body 里的是 bob={bob_id}）",
        )

        # ---------------- 4.1 列表 ----------------
        r = c.get(KBS, headers=alice["headers"])
        names = [item["name"] for item in r.json()]
        check(
            "4.1 列表只含自己的库（不含 bob 的）",
            r.status_code == 200 and KB_NAME in names and len(names) == 2,
            f"{r.status_code} {names}",
        )
        bob_kb_ids = {int(item["id"]) for item in c.get(KBS, headers=bob["headers"]).json()}
        check(
            "4.1 bob 的列表里没有 alice 的库",
            kb_id not in bob_kb_ids and spoofed_kb_id not in bob_kb_ids,
            f"bob 看到 {sorted(bob_kb_ids)}",
        )

        # 文档数量：2 条在册 + 1 条墓碑 → 只应算 2
        stub_document(alice_id, kb_id, index=1, deleted=False)
        stub_document(alice_id, kb_id, index=2, deleted=False)
        stub_document(alice_id, kb_id, index=3, deleted=True)
        counts = {
            int(item["id"]): item["document_count"]
            for item in c.get(KBS, headers=alice["headers"]).json()
        }
        check(
            "4.1 列表文档数量=2（墓碑行不计入）",
            counts.get(kb_id) == 2,
            f"document_count={counts.get(kb_id)}，库里实际 3 行",
        )

        # ---------------- 4.1 重命名 ----------------
        r = c.patch(f"{KBS}/{kb_id}", json={"name": KB_NAME_RENAMED}, headers=alice["headers"])
        check(
            "4.1 重命名生效 200",
            r.status_code == 200 and r.json()["name"] == KB_NAME_RENAMED,
            f"{r.status_code} {r.text[:80]}",
        )
        stored = kb_name_in_db(kb_id)
        check("4.1 重命名落库（查库）", stored == KB_NAME_RENAMED, f"库里是 {stored!r}")

        r = c.patch(f"{KBS}/{kb_id}", json={"name": "被 bob 抢改"}, headers=bob["headers"])
        stored = kb_name_in_db(kb_id)
        check(
            "4.1 重命名他人知识库 404 且数据不变（查库）",
            r.status_code == 404 and stored == KB_NAME_RENAMED,
            f"{r.status_code} 库里仍是 {stored!r}",
        )

        # ---------------- 4.2 删除 ----------------
        r = c.delete(f"{KBS}/{bob_kb_id}", headers=alice["headers"])
        check(
            "4.2 删除他人知识库 404（查库仍在）",
            r.status_code == 404
            and psql(f"SELECT count(*) FROM knowledge_bases WHERE id = {bob_kb_id}") == "1",
            f"{r.status_code}",
        )

        r = c.delete(f"{KBS}/{kb_id}", headers=alice["headers"])
        body = r.json() if "json" in r.headers.get("content-type", "") else {}
        check(
            "4.2 非空拒删 409 且给出未清空数量",
            r.status_code == 409 and body.get("detail", {}).get("document_count") == 2,
            f"{r.status_code} {r.text[:110]}",
        )
        remaining_docs = psql(f"SELECT count(*) FROM documents WHERE kb_id = {kb_id}")
        check(
            "4.2 拒删后库与文档都完好（查库）",
            psql(f"SELECT count(*) FROM knowledge_bases WHERE id = {kb_id}") == "1"
            and remaining_docs == "3",
            f"documents={remaining_docs}（含 1 条墓碑）",
        )

        # 空库可删
        r = c.delete(f"{KBS}/{spoofed_kb_id}", headers=alice["headers"])
        check("4.2 空库删除 204", r.status_code == 204, f"{r.status_code} {r.text[:60]}")
        check(
            "4.2 删除后从库中消失（查库）",
            psql(f"SELECT count(*) FROM knowledge_bases WHERE id = {spoofed_kb_id}") == "0",
        )

        # 只剩墓碑行的库必须也能删掉（D-024 衔接点：先物理清墓碑，否则被 RESTRICT 外键拦住）
        r = c.post(KBS, json={"name": TOMB_KB_NAME}, headers=alice["headers"])
        tomb_kb_id = int(r.json()["id"])
        stub_document(alice_id, tomb_kb_id, index=1, deleted=True)
        r = c.delete(f"{KBS}/{tomb_kb_id}", headers=alice["headers"])
        check(
            "4.2 只剩墓碑行的库可删 204（D-024 衔接点）",
            r.status_code == 204,
            f"{r.status_code} {r.text[:80]}",
        )
        check(
            "4.2 墓碑行随库一并物理清除（查库）",
            psql(f"SELECT count(*) FROM documents WHERE kb_id = {tomb_kb_id}") == "0"
            and psql(f"SELECT count(*) FROM knowledge_bases WHERE id = {tomb_kb_id}") == "0",
        )

        # 未登录一律拒绝
        check(
            "4.1/4.2 无凭证被拒 401",
            c.get(KBS).status_code == 401
            and c.delete(f"{KBS}/{kb_id}").status_code == 401
            and c.patch(f"{KBS}/{kb_id}", json={"name": "x"}).status_code == 401,
        )

        # ---------------- 收尾：清掉本轮造的账号与知识库（查库确认）----------------
        # 顺序不能反：documents → knowledge_bases → users，每层都受外键约束
        psql(f"DELETE FROM documents WHERE user_id IN (SELECT id FROM users WHERE username LIKE 'e2e_4x_%')")
        psql(
            "DELETE FROM knowledge_bases WHERE user_id IN "
            "(SELECT id FROM users WHERE username LIKE 'e2e_4x_%')"
        )
        psql("DELETE FROM users WHERE username LIKE 'e2e_4x_%'")

    leftover = psql(
        "SELECT count(*) FROM users WHERE username LIKE 'e2e_4x_%'"
        f" UNION ALL SELECT count(*) FROM knowledge_bases WHERE name LIKE 'e2e %'"
    )
    check("收尾：本轮测试数据已清空（查库）", set(leftover.splitlines()) == {"0"}, leftover)
    return _summary()


def _summary() -> int:
    print()
    failed = [name for name, status, _ in results if status == "FAIL"]
    print(f"合计 {len(results)} 项，FAIL {len(failed)} 项" + (f"：{failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
