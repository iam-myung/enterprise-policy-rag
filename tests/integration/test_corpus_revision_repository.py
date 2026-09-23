"""CorpusRevisionRepository 原子切换 active revision 测试（Step 3-RED）。

引用尚未实现的 Repository，运行时应以 ImportError 失败。
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from enterprise_policy_rag.adapters.persistence.document_repository import (
    CorpusRevisionRepository,
)
from enterprise_policy_rag.adapters.persistence.sqlite_models import (
    Base,
    CorpusRevisionModel,
)


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_activate_switches_active_revision(session):
    repo = CorpusRevisionRepository(session)
    repo.activate(
        revision="rev1", index_relpath="idx/rev1",
        manifest_sha256="m1", document_ids=["d1"],
    )
    active = repo.get_active()
    assert active is not None
    assert active.revision == "rev1"

    repo.activate(
        revision="rev2", index_relpath="idx/rev2",
        manifest_sha256="m2", document_ids=["d1"],
    )
    active = repo.get_active()
    assert active is not None
    assert active.revision == "rev2"


def test_only_one_active_revision_enforced(session):
    """partial unique index 保证任一时刻唯一 ACTIVE。"""
    session.add(
        CorpusRevisionModel(
            revision="r1", status="ACTIVE", index_relpath="x",
            manifest_sha256="y", created_at_utc=datetime(2024, 1, 1),
        )
    )
    session.commit()
    session.add(
        CorpusRevisionModel(
            revision="r2", status="ACTIVE", index_relpath="x",
            manifest_sha256="y", created_at_utc=datetime(2024, 1, 1),
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
