"""IngestPolicy 原子发布契约测试（SPEC §8.3 / §4.2）。

验证：同内容 sha256 拒绝；索引构建失败不切换 revision；
成功切换 revision；多次导入累积文档与切片（active revision 覆盖完整语料）。
"""

import hashlib
from datetime import datetime
from pathlib import Path

from enterprise_policy_rag.application.contracts.documents import DocumentSummaryDTO
from enterprise_policy_rag.application.ingestion.ingest_policy import (
    IngestPolicy,
)
from enterprise_policy_rag.application.ports.document_parser import (
    ParsedDocumentDTO,
    ParsedPageDTO,
)
from enterprise_policy_rag.domain.entities import (
    CorpusSnapshot,
    DocumentStatus,
    KnowledgeChunk,
    PolicyDocument,
)
from enterprise_policy_rag.domain.errors import ErrorCode


class FakeParser:
    def __init__(self, text: str = "第一条：员工应按时上下班。"):
        self._text = text

    def parse(self, file_path: Path, document_id: str) -> ParsedDocumentDTO:
        return ParsedDocumentDTO(
            document_id=document_id,
            pages=(
                ParsedPageDTO(
                    page_number=1, source_text=self._text, source_text_sha256="x"
                ),
            ),
        )


class FakeDocumentRepo:
    def __init__(self, existing_sha256: str | None = None):
        self._existing_sha256 = existing_sha256
        self.added: list[PolicyDocument] = []
        self._chunks_by_doc: dict[str, list[KnowledgeChunk]] = {}
        self.pages_added: list[object] = []

    def add(self, document: PolicyDocument) -> None:
        self.added.append(document)

    def get(self, document_id: str) -> PolicyDocument | None:
        return None

    def get_by_sha256(self, sha256: str) -> PolicyDocument | None:
        if sha256 == self._existing_sha256:
            return PolicyDocument(
                id="dup", title="旧制度", version="v1",
                effective_at=None, expires_at=None, scope="全员",
                source_kind="PUBLIC_SAMPLE", status=DocumentStatus.ACTIVE,
                sha256=sha256, page_count=1,
            )
        return None

    def add_parsed_pages(self, pages) -> None:
        self.pages_added.extend(pages)

    def add_chunks(self, chunks: tuple[KnowledgeChunk, ...], revision: str) -> None:
        for chunk in chunks:
            self._chunks_by_doc.setdefault(chunk.document_id, []).append(chunk)

    def list_chunks_by_documents(
        self, document_ids: list[str]
    ) -> tuple[KnowledgeChunk, ...]:
        result: list[KnowledgeChunk] = []
        for doc_id in document_ids:
            result.extend(self._chunks_by_doc.get(doc_id, []))
        return tuple(result)


class FakeRevisionRepo:
    def __init__(self, active: CorpusSnapshot | None = None):
        self._active = active
        self.activated: list[str] = []
        self.activations: list[tuple[str, str, str, list[str]]] = []

    def activate(
        self, revision, index_relpath, manifest_sha256, document_ids
    ) -> None:
        self.activated.append(revision)
        self.activations.append(
            (revision, index_relpath, manifest_sha256, list(document_ids))
        )
        self._active = CorpusSnapshot(
            revision=revision,
            active_document_ids=tuple(document_ids),
            index_path=index_relpath,
            created_at=datetime(2024, 1, 1),
        )

    def get_active(self) -> CorpusSnapshot | None:
        return self._active


class FakeIndexBuilder:
    def __init__(self, fail: bool = False):
        self._fail = fail
        self.builds: list[tuple[tuple[KnowledgeChunk, ...], str]] = []

    def build(self, chunks: tuple[KnowledgeChunk, ...], revision: str) -> str:
        self.builds.append((chunks, revision))
        if self._fail:
            raise RuntimeError("index build failed")
        return f"idx/{revision}"


def _make_policy(existing_sha256=None, fail_build=False, active=None):
    return IngestPolicy(
        parser=FakeParser(),
        document_repo=FakeDocumentRepo(existing_sha256=existing_sha256),
        revision_repo=FakeRevisionRepo(active=active),
        index_builder=FakeIndexBuilder(fail=fail_build),
        workspace_root=Path("workspace"),
    )


def _file(tmp_path: Path, content: bytes = b"%PDF-1.4 fake") -> Path:
    f = tmp_path / "a.pdf"
    f.write_bytes(content)
    return f


def test_ingest_duplicate_sha256_rejected(tmp_path):
    content = b"%PDF-1.4 fake"
    sha = hashlib.sha256(content).hexdigest()
    policy = _make_policy(existing_sha256=sha)
    result = policy.ingest(
        _file(tmp_path, content),
        title="考勤制度", version="v1", scope="全员", source_kind="PUBLIC_SAMPLE",
    )
    assert result.success is False
    assert result.error is not None
    assert result.error.code is ErrorCode.DUPLICATE_DOCUMENT


def test_ingest_build_failure_does_not_switch_revision(tmp_path):
    old = CorpusSnapshot(
        revision="rev-old", active_document_ids=("d0",),
        index_path="idx/old", created_at=datetime(2024, 1, 1),
    )
    revision_repo = FakeRevisionRepo(active=old)
    policy = IngestPolicy(
        parser=FakeParser(),
        document_repo=FakeDocumentRepo(),
        revision_repo=revision_repo,
        index_builder=FakeIndexBuilder(fail=True),
        workspace_root=Path("workspace"),
    )
    result = policy.ingest(
        _file(tmp_path),
        title="考勤制度", version="v1", scope="全员", source_kind="PUBLIC_SAMPLE",
    )
    assert result.success is False
    assert revision_repo.get_active() is old
    assert revision_repo.activated == []


def test_ingest_success_switches_revision(tmp_path):
    policy = _make_policy(active=None)
    result = policy.ingest(
        _file(tmp_path),
        title="考勤制度", version="v1", scope="全员", source_kind="PUBLIC_SAMPLE",
    )
    assert result.success is True
    assert isinstance(result.data, DocumentSummaryDTO)
    # revision 是 32 位 hex（uuid），而非字面量 "index"
    assert len(result.data.corpus_revision) == 32


def test_ingest_accumulates_documents_and_chunks(tmp_path):
    """多次导入累积：active revision 覆盖完整语料，activate 收到累积 document_ids。"""
    repo = FakeDocumentRepo()
    revision_repo = FakeRevisionRepo(active=None)
    index_builder = FakeIndexBuilder()
    policy = IngestPolicy(
        parser=FakeParser(), document_repo=repo,
        revision_repo=revision_repo, index_builder=index_builder,
        workspace_root=Path("workspace"),
    )

    r1 = policy.ingest(
        _file(tmp_path, b"%PDF-1.4 one"), "A", "v1", "全员", "PUBLIC_SAMPLE"
    )
    assert r1.success is True
    first_doc_id = r1.data.id

    r2 = policy.ingest(
        _file(tmp_path, b"%PDF-1.4 two"), "B", "v1", "全员", "PUBLIC_SAMPLE"
    )
    assert r2.success is True
    second_doc_id = r2.data.id

    # activate 第二次收到累积的 [first, second]
    assert set(revision_repo.activations[1][3]) == {first_doc_id, second_doc_id}
    # index_builder 第二次 build 收到累积 chunks（第一份 + 第二份）
    assert len(index_builder.builds[1][0]) == len(index_builder.builds[0][0]) + 1
