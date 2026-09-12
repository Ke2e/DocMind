"""任务 2.1 的机器核验：五张表的形状必须与 ADR-0001 及 Key Entities 清单一致。

本文件只读 SQLAlchemy metadata，**不连数据库**；DDL 层面的核对（索引真实存在、
downgrade 回到初始结构）在 2.2 用真实库的 information_schema / pg_indexes 复查。

判据来源：
- `docs/adr/0001-knowledge-base-entity.md`（`uq_kb_user_name` / `idx_documents_kb` / kb_id NOT NULL）
- `specs/001-doc-ingest-pipeline/spec.md` Key Entities（Document 的 FR-018 字段、Processing Task 的两个计数器）
- `openspec/changes/add-doc-ingest-pipeline/design.md` D3 / D4 / D8
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sqlalchemy import BigInteger, Integer, String, UniqueConstraint

from app.models import Base
from app.models.enums import STATUS_SEQUENCE, DocumentStatus

EXPECTED_TABLES = {
    "users",
    "knowledge_bases",
    "documents",
    "chunks",
    "processing_tasks",
}
BACKEND_DIR = Path(__file__).resolve().parents[1]


def _fk(col):
    fks = list(col.foreign_keys)
    assert len(fks) == 1, f"{col} 应恰好有一个外键，实际 {len(fks)} 个"
    return fks[0]


def _fk_target(col) -> str:
    return _fk(col).target_fullname


def _fk_ondelete(col) -> str | None:
    return _fk(col).ondelete


def _indexes(table) -> dict:
    return {idx.name: idx for idx in table.indexes}


def _unique_constraints(table) -> list[UniqueConstraint]:
    return [c for c in table.constraints if isinstance(c, UniqueConstraint)]


def test_five_tables_registered():
    """2.1 验证：模型可导入，metadata 里就是这 5 张表，不多不少。"""
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_models_import_without_circular_dependency():
    """2.1 验证：子模块各自导入不产生循环依赖，且导入后 5 张表都在 metadata 里。

    用子进程做干净导入——同进程里模块已被缓存，测不出循环依赖。
    """
    code = (
        "from app.models.base import Base;"
        "from app.models.user import User;"
        "from app.models.knowledge_base import KnowledgeBase;"
        "from app.models.document import Document;"
        "from app.models.chunk import Chunk;"
        "from app.models.processing_task import ProcessingTask;"
        "print(sorted(Base.metadata.tables))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"导入失败（疑似循环依赖）：{proc.stderr}"
    assert proc.stdout.strip() == str(sorted(EXPECTED_TABLES))


def test_users_shape():
    t = Base.metadata.tables["users"]
    assert set(t.c.keys()) == {"id", "username", "password_hash", "created_at"}
    assert isinstance(t.c.id.type, BigInteger) and t.c.id.primary_key
    assert isinstance(t.c.username.type, String) and t.c.username.type.length == 64
    assert not t.c.username.nullable
    assert not t.c.password_hash.nullable
    assert t.c.created_at.server_default is not None

    uqs = _unique_constraints(t)
    assert [c.name for c in uqs] == ["uq_users_username"]
    assert [col.name for col in uqs[0].columns] == ["username"]


def test_knowledge_bases_matches_adr_0001():
    t = Base.metadata.tables["knowledge_bases"]
    assert set(t.c.keys()) == {"id", "user_id", "name", "description", "created_at"}
    assert isinstance(t.c.id.type, BigInteger) and t.c.id.primary_key
    assert _fk_target(t.c.user_id) == "users.id"
    assert not t.c.user_id.nullable
    assert isinstance(t.c.name.type, String) and t.c.name.type.length == 128
    assert not t.c.name.nullable
    assert t.c.description.nullable

    idx = _indexes(t)
    assert "uq_kb_user_name" in idx, "ADR-0001 要求的唯一索引名缺失"
    assert idx["uq_kb_user_name"].unique is True
    assert [c.name for c in idx["uq_kb_user_name"].columns] == ["user_id", "name"]


def test_documents_shape():
    t = Base.metadata.tables["documents"]
    # FR-018：原始文件名 / 类型 / 字节大小 / 状态 / 失败原因 / 片段数量 / 归属知识库 / 创建时间
    assert {
        "original_filename",
        "file_type",
        "file_size_bytes",
        "status",
        "error_message",
        "chunk_count",
        "kb_id",
        "created_at",
    } <= set(t.c.keys())

    # ADR-0001：kb_id NOT NULL，并建 idx_documents_kb
    assert not t.c.kb_id.nullable
    assert _fk_target(t.c.kb_id) == "knowledge_bases.id"
    idx = _indexes(t)
    assert "idx_documents_kb" in idx, "ADR-0001 要求的索引名缺失"
    assert [c.name for c in idx["idx_documents_kb"].columns] == ["kb_id"]

    # 所有查询都要带 user_id 过滤（AGENTS.md §6）→ 该列必须有索引
    assert "ix_documents_user_id" in idx
    assert _fk_target(t.c.user_id) == "users.id"

    assert isinstance(t.c.file_size_bytes.type, BigInteger)
    assert isinstance(t.c.chunk_count.type, Integer)
    assert t.c.chunk_count.server_default is not None
    # D8 的删除标记：可空时间戳，非空即视为已删除
    assert t.c.deleted_at.nullable
    assert t.c.error_message.nullable


def test_documents_status_column_is_varchar_backed():
    """状态列落库为 VARCHAR（native_enum=False），值是小写英文取值。

    理由：避免 PG 原生枚举的 ALTER TYPE 迁移负担；中文文案由接口层翻译，
    不固化进数据库（enums.py 的注释）。
    """
    typ = Base.metadata.tables["documents"].c.status.type
    assert typ.native_enum is False
    assert typ.length == 20
    assert typ.enums == [member.value for member in DocumentStatus]
    assert not Base.metadata.tables["documents"].c.status.nullable


def test_chunks_unique_constraint_and_cascade():
    """D4：幂等靠 `(document_id, chunk_index)` 唯一约束兜底。"""
    t = Base.metadata.tables["chunks"]
    assert set(t.c.keys()) == {
        "id",
        "document_id",
        "chunk_index",
        "content",
        "token_count",
        "created_at",
    }
    uqs = _unique_constraints(t)
    assert [c.name for c in uqs] == ["uq_chunks_document_chunk_index"]
    assert [col.name for col in uqs[0].columns] == ["document_id", "chunk_index"]
    assert _fk_ondelete(t.c.document_id) == "CASCADE"
    assert not t.c.content.nullable
    assert not t.c.chunk_index.nullable


def test_processing_tasks_one_row_per_document():
    """5.3：并发提交同一文档只产生一条处理记录 → document_id 唯一。"""
    t = Base.metadata.tables["processing_tasks"]
    assert set(t.c.keys()) == {
        "id",
        "document_id",
        "stage",
        "auto_retry_count",
        "manual_retry_count",
        "last_run_at",
        "created_at",
        "updated_at",
    }
    uqs = _unique_constraints(t)
    assert [c.name for c in uqs] == ["uq_processing_tasks_document_id"]
    assert [col.name for col in uqs[0].columns] == ["document_id"]
    assert _fk_ondelete(t.c.document_id) == "CASCADE"

    for name in ("stage", "auto_retry_count", "manual_retry_count"):
        assert t.c[name].server_default is not None, f"{name} 应有默认值"
    # 8.3 的卡死扫描以它为基准，未执行过时为空
    assert t.c.last_run_at.nullable


def test_status_sequence_is_forward_only_order():
    """7.1 的"已完成阶段"依据：推进顺序里不含终态 failed。"""
    assert STATUS_SEQUENCE == (
        DocumentStatus.UPLOADED,
        DocumentStatus.PARSING,
        DocumentStatus.CHUNKING,
        DocumentStatus.VECTORIZING,
        DocumentStatus.READY,
    )
    assert DocumentStatus.FAILED not in STATUS_SEQUENCE
    assert len(STATUS_SEQUENCE) == len(set(STATUS_SEQUENCE))


async def test_metadata_builds_in_real_test_database(db_engine, db_schema):
    """2.1/2.2 联验：测试库按 metadata 真能建出这 5 张表。

    顺带看住 conftest 的连接串来源——若口令/端口写错，本用例会变成 skipped 而不是
    failed，容易被当成功（D-026）：跑完后请确认 pytest 汇总里没有 skip。
    """
    from sqlalchemy import inspect

    def _table_names(sync_conn) -> set[str]:
        return set(inspect(sync_conn).get_table_names())

    async with db_engine.connect() as conn:
        names = await conn.run_sync(_table_names)
    assert EXPECTED_TABLES <= names
