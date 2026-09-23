"""Alembic upgrade/downgrade 往返测试（Step 3-RED）。

引用尚未实现的 migrations/（env.py + versions），运行时应失败。
"""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _make_config(tmp_path):
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'mig.db'}")
    return cfg


def test_upgrade_downgrade_roundtrip_empty(tmp_path):
    cfg = _make_config(tmp_path)
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{tmp_path / 'mig.db'}")
    tables = set(inspect(engine).get_table_names())
    assert {
        "policy_documents", "knowledge_chunks", "parsed_pages",
        "corpus_revisions", "corpus_revision_documents",
        "ingestion_runs", "query_runs",
    } <= tables
    command.downgrade(cfg, "base")
    remaining = set(inspect(engine).get_table_names())
    # 业务表已删除，仅 alembic 内部版本表 alembic_version 保留
    assert remaining <= {"alembic_version"}


def test_upgrade_after_existing_data_roundtrip(tmp_path):
    cfg = _make_config(tmp_path)
    command.upgrade(cfg, "head")
    # 已有数据：upgrade → downgrade → 再 upgrade，结构可重建
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{tmp_path / 'mig.db'}")
    assert "policy_documents" in set(inspect(engine).get_table_names())
