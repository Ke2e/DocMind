"""第 5 组（文档上传与受理）的端到端验收：**经 nginx 打真实 HTTP** + **查库核对**。

为什么要有这一份：`pytest` 走 ASGI 直连，证明代码逻辑对，但证明不了
「容器 + nginx + 共享卷 + broker」这条真实链路可用（第 1 组的教训：容器 healthy ≠ 对外可用）。
本组尤其如此 —— 落盘发生在容器的共享卷上、投递要真的到 worker、大小上限要真的由应用层判定。

运行方式（必须用 backend 的 venv，且 PATH 里要有 docker；本机无 curl）：

    export PATH="/d/Docker/App/resources/bin:...:/usr/bin:/bin"
    cd backend
    .venv/Scripts/python.exe ../tools/verify_document_e2e.py

前提：`docker compose up -d --build` 已完成且容器**稳定**
（不要紧接在重建之后就跑 —— 跨容器切换窗口的写请求不可信，见 docs/findings.md D-031）。

两条本组专属的验收点：

- **SC-001**：10MB PDF 提交 ≤ 2 秒返回受理，且**期间服务仍能响应其他请求**（本脚本边上传边打健康探针）；
- **投递真的发生了**：不只看库里那行 `processing_tasks`，还核对 **worker 日志**里
  确实打印了"收到文档处理任务"—— 前者只证明 API 写了库。

收尾：脚本会清掉自己建的账号、知识库、文档，以及落在共享卷上的文件，并**查库确认**清空。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS = REPO_ROOT / "fixtures" / "acceptance"
PG_CONTAINER = "docmind-pg"
API_CONTAINER = "docmind-api"
WORKER_CONTAINER = "docmind-worker"
UPLOAD_DIR_IN_CONTAINER = "/data/uploads"

# SC-001 的判据（秒）。规格原文是"秒级内"，任务 5.1 把它量化为 2 秒。
SC001_BUDGET_SECONDS = 2.0
# 上传期间健康探针的最大可接受延迟：规格要求"服务对其他请求的响应无明显变慢"
HEALTH_PROBE_BUDGET_SECONDS = 1.0


def _local_env() -> dict[str, str]:
    """读仓库根 `.env`（与 backend/tests/conftest.py 同一套约定）。

    端口、库名、账号全部从配置取，不在脚本里写死 —— 硬编码会在开发者改了 `.env`
    之后变成假失败。
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
DOCS = "/api/documents"
KBS = "/api/knowledge-bases"
KB_MAIN = f"e2e 文档主库 {STAMP}"
KB_SECOND = f"e2e 文档副库 {STAMP}"
KB_BOB = f"e2e bob 的库 {STAMP}"
USER_TAG = f"e2e_5x_{STAMP}"

# 四种受支持格式的验收语料（由 tools/gen_acceptance_corpus.py 确定性生成）
SAMPLES = [
    ("docmind_handbook.md", "md"),
    ("docmind_course_notes.txt", "txt"),
    ("docmind_product_spec.docx", "docx"),
    ("docmind_manual.pdf", "pdf"),
]
BIG_PDF = "docmind_manual_10mb.pdf"

results: list[tuple[str, str, str]] = []


def check(name: str, cond: bool, info: str = "") -> None:
    results.append((name, "PASS" if cond else "FAIL", info))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"   [{info}]" if info else ""))


def _run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """跑一个宿主命令。**必须显式 `encoding="utf-8"`**：本机 locale 是 GBK，
    而容器里的 psql / python 输出 UTF-8，用默认编码解码会把中文读成乱码，
    让"查库核对"变成假失败（第 4 组实测，见 findings D-036）。"""
    return subprocess.run(
        argv, capture_output=True, encoding="utf-8", errors="replace"
    )


def psql(sql: str) -> str:
    proc = _run(
        ["docker", "exec", PG_CONTAINER, "psql", "-U", PG_USER, "-d", PG_DB, "-tAc", sql]
    )
    if proc.returncode != 0:
        raise RuntimeError(f"psql 执行失败：{proc.stderr.strip()}")
    return proc.stdout.strip()


def container_file_size(storage_name: str) -> int:
    """返回共享卷里那个文件的字节数；不存在返回 -1。

    不给用户/文档 id 之类的变量走 psql 的 `-v`（`docker exec` 会把它吞掉，见 D-038），
    这里直接把文件名当 `python -c` 的 argv 传，绕开 shell 与引号。
    """
    code = (
        "import os,sys;"
        f"p=os.path.join('{UPLOAD_DIR_IN_CONTAINER}', sys.argv[1]);"
        "print(os.path.getsize(p) if os.path.exists(p) else -1)"
    )
    proc = _run(["docker", "exec", API_CONTAINER, "python", "-c", code, storage_name])
    if proc.returncode != 0:
        raise RuntimeError(f"容器内取文件大小失败：{proc.stderr.strip()}")
    return int(proc.stdout.strip())


def remove_container_file(storage_name: str) -> None:
    _run(["docker", "exec", API_CONTAINER, "rm", "-f", "--", f"{UPLOAD_DIR_IN_CONTAINER}/{storage_name}"])


def worker_task_log_count() -> int:
    """worker 日志里"收到文档处理任务"的行数 —— 投递真的到达执行层的证据。"""
    proc = _run(["docker", "logs", WORKER_CONTAINER, "--tail", "800"])
    text = proc.stdout + proc.stderr
    return text.count("收到文档处理任务")


def upload(
    client: httpx.Client,
    headers: dict[str, str],
    *,
    kb_id: int,
    path: Path | None = None,
    filename: str | None = None,
    body: bytes | None = None,
):
    name = filename or (path.name if path else "unnamed")
    payload = body if body is not None else (path.read_bytes() if path else b"")
    return client.post(
        DOCS,
        files={"file": (name, payload, "application/octet-stream")},
        data={"kb_id": str(kb_id)},
        headers=headers,
        timeout=120,
    )


def storage_of(document_id: int) -> tuple[str, int]:
    """从库里取 (storage_path, file_size_bytes)。"""
    raw = psql(
        f"SELECT storage_path || '|' || file_size_bytes FROM documents WHERE id = {document_id}"
    )
    storage_path, _, size = raw.partition("|")
    return storage_path, int(size)


def main() -> int:  # noqa: C901 - 脚本按验收清单线性铺开，拆函数反而看不出对照关系
    if not CORPUS.exists():
        print(f"缺少验收语料：{CORPUS}")
        print("请先跑：.venv/Scripts/python.exe tools/gen_acceptance_corpus.py")
        return 2

    with httpx.Client(base_url=BASE, timeout=60) as c:
        r = c.get("/health/ready")
        check(
            "回归：/health/ready 200",
            r.status_code == 200 and r.json().get("status") == "ok",
            str(r.status_code),
        )

        # ---- 准备：两个账号 + 三个知识库 ----
        accounts: dict[str, dict[str, object]] = {}
        for tag in ("a", "b"):
            username = f"{USER_TAG}_{tag}"
            reg = c.post("/api/auth/register", json={"username": username, "password": PASSWORD})
            if reg.status_code != 201:
                check(f"准备：注册账号 {tag} 201", False, f"{reg.status_code} {reg.text[:70]}")
                return _summary()
            login = c.post("/api/auth/login", json={"username": username, "password": PASSWORD})
            accounts[tag] = {
                "id": reg.json()["id"],
                "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
            }
        alice, bob = accounts["a"], accounts["b"]
        alice_id, bob_id = int(alice["id"]), int(bob["id"])  # type: ignore[arg-type]
        alice_h = alice["headers"]  # type: ignore[assignment]
        bob_h = bob["headers"]  # type: ignore[assignment]
        check("准备：双账号注册并登录", True, f"a.id={alice_id} b.id={bob_id}")

        def make_kb(name: str, headers) -> int:
            resp = c.post(KBS, json={"name": name}, headers=headers)
            assert resp.status_code == 201, resp.text
            return int(resp.json()["id"])

        kb_main = make_kb(KB_MAIN, alice_h)
        kb_second = make_kb(KB_SECOND, alice_h)
        kb_bob = make_kb(KB_BOB, bob_h)

        # ---------------- 5.1 四种格式 ----------------
        uploaded: dict[str, int] = {}
        for name, ext in SAMPLES:
            path = CORPUS / name
            resp = upload(c, alice_h, kb_id=kb_main, path=path)
            ok = resp.status_code == 201
            check(f"5.1 上传 {name} → 201", ok, f"{resp.status_code} {resp.text[:80]}")
            if not ok:
                continue
            body = resp.json()
            uploaded[name] = int(body["id"])
            size_on_disk = container_file_size(storage_of(body["id"])[0])
            check(
                f"5.1 {name} 落盘到共享卷且字节数一致（查库 + 查容器）",
                body["status"] == "uploaded"
                and body["file_type"] == ext
                and body["chunk_count"] == 0
                and size_on_disk == path.stat().st_size,
                f"status={body['status']} 库内={body['file_size_bytes']} 卷上={size_on_disk}",
            )

        # ---------------- SC-001：10MB 不阻塞 ----------------
        big = CORPUS / BIG_PDF
        big_size = big.stat().st_size
        health_latencies: list[float] = []

        def _do_upload():
            # 单独开一个 client：这个请求要在别的线程里跑，别和主线程共用连接
            with httpx.Client(base_url=BASE, timeout=120) as inner:
                started = time.perf_counter()
                resp = upload(inner, alice_h, kb_id=kb_main, path=big)
                return resp, time.perf_counter() - started

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_do_upload)
            while not future.done():
                probe_started = time.perf_counter()
                probe = c.get("/health/ready", timeout=10)
                health_latencies.append(time.perf_counter() - probe_started)
                if probe.status_code != 200:
                    check("SC-001 上传期间 /health/ready 仍 200", False, str(probe.status_code))
                    break
                time.sleep(0.05)
            big_resp, big_elapsed = future.result()

        check(
            f"SC-001 10MB PDF（{big_size / 1024 / 1024:.2f}MB）提交 ≤ {SC001_BUDGET_SECONDS}s 返回受理",
            big_resp.status_code == 201 and big_elapsed <= SC001_BUDGET_SECONDS,
            f"{big_resp.status_code}，耗时 {big_elapsed:.3f}s",
        )
        worst = max(health_latencies) if health_latencies else float("nan")
        check(
            "SC-001 上传期间服务仍响应其他请求",
            bool(health_latencies) and worst <= HEALTH_PROBE_BUDGET_SECONDS,
            f"{len(health_latencies)} 次探针，最慢 {worst:.4f}s",
        )
        if big_resp.status_code == 201:
            uploaded[BIG_PDF] = int(big_resp.json()["id"])
            check(
                "SC-001 10MB 文档落盘字节数一致（查库 + 查容器）",
                container_file_size(storage_of(uploaded[BIG_PDF])[0]) == big_size,
                f"卷上 {container_file_size(storage_of(uploaded[BIG_PDF])[0])} / 本地 {big_size}",
            )

        # 副库放一份，供"按知识库筛选不跨库"用
        sid = upload(c, alice_h, kb_id=kb_second, path=CORPUS / "docmind_handbook.md")
        check("准备：副库上传一份 → 201", sid.status_code == 201, str(sid.status_code))
        second_doc_id = int(sid.json()["id"]) if sid.status_code == 201 else 0

        # bob 也有一份，供跨账号列表/详情/片段用例
        bid = upload(c, bob_h, kb_id=kb_bob, path=CORPUS / "docmind_course_notes.txt")
        check("准备：bob 上传一份 → 201", bid.status_code == 201, str(bid.status_code))
        bob_doc_id = int(bid.json()["id"]) if bid.status_code == 201 else 0

        # ---------------- 5.1 拒绝路径 ----------------
        before_docs = int(psql(f"SELECT count(*) FROM documents WHERE user_id = {alice_id}"))
        resp = upload(
            c,
            alice_h,
            kb_id=kb_main,
            path=CORPUS / "unsupported_sample.csv",
        )
        check(
            "5.1 不支持的格式（csv）→ 415 且说明原因",
            resp.status_code == 415
            and resp.json().get("code") == "unsupported_media_type"
            and "csv" in resp.json().get("message", ""),
            f"{resp.status_code} {resp.text[:90]}",
        )
        check(
            "5.1 被拒的提交不产生文档记录（查库）",
            int(psql(f"SELECT count(*) FROM documents WHERE user_id = {alice_id}")) == before_docs,
        )

        oversize = b"x" * (51 * 1024 * 1024)  # 51MB > MAX_UPLOAD_MB=50，但 < nginx 的 60m
        resp = upload(c, alice_h, kb_id=kb_main, filename="oversize.pdf", body=oversize)
        check(
            "5.1 超出 50MB 上限 → 413 且说明上限",
            resp.status_code == 413
            and resp.json().get("code") == "payload_too_large"
            and "50MB" in resp.json().get("message", ""),
            f"{resp.status_code} {resp.text[:90]}",
        )
        check(
            "5.1 超限的提交不产生文档记录（查库）",
            int(psql(f"SELECT count(*) FROM documents WHERE user_id = {alice_id}")) == before_docs,
        )

        # ---------------- 5.2 归属约束 ----------------
        before_docs_b = int(psql(f"SELECT count(*) FROM documents WHERE user_id = {bob_id}"))
        resp = upload(c, bob_h, kb_id=kb_main, path=CORPUS / "docmind_handbook.md")
        check(
            "5.2 向他人知识库提交 → 404",
            resp.status_code == 404 and resp.json().get("code") == "not_found",
            f"{resp.status_code} {resp.text[:80]}",
        )
        check(
            "5.2 越权提交不产生文档记录（查库）",
            int(psql(f"SELECT count(*) FROM documents WHERE user_id = {bob_id}")) == before_docs_b,
        )
        resp = upload(c, alice_h, kb_id=999_999, path=CORPUS / "docmind_handbook.md")
        check("5.2 不存在的知识库 → 404", resp.status_code == 404, f"{resp.status_code}")

        # ---------------- 5.3 投递与并发保护 ----------------
        total_docs = int(psql(f"SELECT count(*) FROM documents WHERE user_id = {alice_id}"))
        tasks_for_alice = int(
            psql(
                "SELECT count(*) FROM processing_tasks WHERE document_id IN "
                f"(SELECT id FROM documents WHERE user_id = {alice_id})"
            )
        )
        check(
            "5.3 每个文档恰好一条处理记录（无重复投递）",
            tasks_for_alice == total_docs,
            f"documents={total_docs} / processing_tasks={tasks_for_alice}",
        )
        check(
            "5.3 处理记录总数与文档数一致（查库，按文档分组最大值=1）",
            psql(
                "SELECT COALESCE(max(c), 0) FROM (SELECT count(*) AS c FROM processing_tasks "
                f"WHERE document_id IN (SELECT id FROM documents WHERE user_id = {alice_id}) "
                "GROUP BY document_id) t"
            )
            == "1",
        )
        expected_tasks = len(uploaded) + 2  # alice 的 5+1 份 + bob 的 1 份
        check(
            "5.3 任务确实投递到了 worker（worker 日志核对）",
            worker_task_log_count() >= expected_tasks,
            f"日志中 {worker_task_log_count()} 条 >= 期望 {expected_tasks} 条",
        )

        # ---------------- 5.4 片段反查 ----------------
        target = uploaded.get("docmind_manual.pdf") or next(iter(uploaded.values()))
        # 片段是 6.x 的产物；5.x 阶段直接插桩，被测的是 5.4 的读取（内容全 ASCII，避免编码干扰）
        psql(
            "INSERT INTO chunks (document_id, chunk_index, content, token_count) VALUES "
            f"({target}, 2, 'e2e-c2', 12), ({target}, 0, 'e2e-c0', 10), ({target}, 1, 'e2e-c1', 11)"
        )
        psql(f"UPDATE documents SET chunk_count = 3 WHERE id = {target}")
        resp = c.get(f"{DOCS}/{target}/chunks", headers=alice_h)
        payload = resp.json() if resp.status_code == 200 else []
        check(
            "5.4 片段按 chunk_index 升序返回",
            resp.status_code == 200
            and [chunk["chunk_index"] for chunk in payload] == [0, 1, 2]
            and payload[0]["content"] == "e2e-c0",
            f"{resp.status_code} {[chunk.get('chunk_index') for chunk in payload]}",
        )
        detail = c.get(f"{DOCS}/{target}", headers=alice_h).json()
        check(
            "5.4 片段总数与文档 chunk_count 一致",
            len(payload) == detail.get("chunk_count") == 3,
            f"接口 {len(payload)} / 文档 {detail.get('chunk_count')}",
        )
        resp = c.get(f"{DOCS}/{target}/chunks", headers=bob_h)
        check(
            "5.4 越权访问他人文档的片段 → 404",
            resp.status_code == 404,
            f"{resp.status_code}",
        )

        # ---------------- 5.5 列表与详情 ----------------
        listed = c.get(DOCS, headers=alice_h).json()
        listed_ids = {int(item["id"]) for item in listed}
        check(
            "5.5 列表只含自己的文档",
            bob_doc_id not in listed_ids and set(uploaded.values()) <= listed_ids,
            f"alice 看到 {len(listed_ids)} 份",
        )
        filtered = c.get(f"{DOCS}?kb_id={kb_second}", headers=alice_h).json()
        check(
            "5.5 按知识库筛选不跨库（SC-008）",
            {int(item["id"]) for item in filtered} == {second_doc_id}
            and all(int(item["kb_id"]) == kb_second for item in filtered),
            f"副库返回 {[item['id'] for item in filtered]}",
        )
        resp = c.get(f"{DOCS}?kb_id={kb_main}", headers=bob_h)
        check(
            "5.5 用他人知识库筛选 → 404（不是空列表）",
            resp.status_code == 404,
            f"{resp.status_code}",
        )
        resp = c.get(f"{DOCS}/{target}", headers=alice_h)
        body = resp.json() if resp.status_code == 200 else {}
        check(
            "5.5 详情含归属知识库 / 状态 / 片段数量",
            resp.status_code == 200
            and body.get("kb_id") == kb_main
            and body.get("status") == "uploaded"
            and body.get("chunk_count") == 3
            and "storage_path" not in body,
            f"{resp.status_code} {json.dumps(body, ensure_ascii=False)[:90]}",
        )
        check(
            "5.5 读取他人文档详情 → 404",
            c.get(f"{DOCS}/{target}", headers=bob_h).status_code == 404
            and c.get(f"{DOCS}/{bob_doc_id}", headers=alice_h).status_code == 404,
        )

        check(
            "5.1/5.4/5.5 无凭证一律 401",
            c.get(DOCS).status_code == 401
            and c.get(f"{DOCS}/{target}").status_code == 401
            and c.get(f"{DOCS}/{target}/chunks").status_code == 401
            and c.post(DOCS, data={"kb_id": str(kb_main)}).status_code == 401,
        )

        # ---------------- 收尾：删账号 / 知识库 / 文档 + 共享卷上的文件 ----------------
        created_ids = sorted(set(uploaded.values()) | ({second_doc_id, bob_doc_id} - {0}))
        storage_names = [
            line
            for line in psql(
                "SELECT storage_path FROM documents WHERE user_id IN "
                f"(SELECT id FROM users WHERE username LIKE '{USER_TAG}%')"
            ).splitlines()
            if line
        ]
        for name in storage_names:
            remove_container_file(name)

        psql(
            "DELETE FROM documents WHERE user_id IN "
            f"(SELECT id FROM users WHERE username LIKE '{USER_TAG}%')"
        )
        psql(
            "DELETE FROM knowledge_bases WHERE user_id IN "
            f"(SELECT id FROM users WHERE username LIKE '{USER_TAG}%')"
        )
        psql(f"DELETE FROM users WHERE username LIKE '{USER_TAG}%'")

    # 按"本轮创建的那几个 id"核对，而不是按文件名/前缀猜 —— 精确且不受开发库里既有数据干扰
    created_ids = created_ids if created_ids else [0]
    leftover_docs = psql(
        f"SELECT count(*) FROM documents WHERE id IN ({','.join(map(str, created_ids))})"
    )
    leftover_accounts = psql(
        f"SELECT count(*) FROM users WHERE username LIKE '{USER_TAG}%'"
        " UNION ALL SELECT count(*) FROM knowledge_bases WHERE name LIKE 'e2e 文档%'"
    )
    check(
        "收尾：本轮账号 / 知识库已清空（查库）",
        set(leftover_accounts.splitlines()) == {"0"},
        leftover_accounts,
    )
    check("收尾：本轮文档已清空（按 id 查库）", leftover_docs == "0", f"残留 {leftover_docs}")
    survivors = [name for name in storage_names if container_file_size(name) != -1]
    check(
        "收尾：共享卷上的本轮文件已删除（查容器）",
        not survivors,
        f"残留 {survivors}" if survivors else f"清理了 {len(storage_names)} 个文件",
    )
    return _summary()


def _summary() -> int:
    print()
    failed = [name for name, status, _ in results if status == "FAIL"]
    print(f"合计 {len(results)} 项，FAIL {len(failed)} 项" + (f"：{failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
