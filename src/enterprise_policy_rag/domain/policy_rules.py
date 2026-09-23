"""制度规则纯函数（SPEC §4.2 状态机 + §4.1 chunk 不变量）。

domain 纯净：仅依赖标准库与 domain.entities。
"""

from enterprise_policy_rag.domain.entities import DocumentStatus, KnowledgeChunk

_ALLOWED_TRANSITIONS = frozenset(
    {
        (DocumentStatus.PENDING, DocumentStatus.PROCESSING),
        (DocumentStatus.PROCESSING, DocumentStatus.ACTIVE),
        (DocumentStatus.PROCESSING, DocumentStatus.FAILED),
        (DocumentStatus.ACTIVE, DocumentStatus.SUPERSEDED),
        (DocumentStatus.ACTIVE, DocumentStatus.EXPIRED),
        (DocumentStatus.FAILED, DocumentStatus.PROCESSING),  # 仅显式重试
    }
)


def can_transition(from_status: DocumentStatus, to_status: DocumentStatus) -> bool:
    """判断文档状态迁移是否合法（SPEC §4.2）。"""
    return (from_status, to_status) in _ALLOWED_TRANSITIONS


def validate_chunk_source(chunk: KnowledgeChunk, source_text: str) -> None:
    """校验 chunk.text == source_text[char_start:char_end]，且区间不越界（不跨页）。"""
    if (
        chunk.char_start < 0
        or chunk.char_end > len(source_text)
        or chunk.char_start >= chunk.char_end
    ):
        raise ValueError("chunk 字符区间非法或越界")
    if chunk.text != source_text[chunk.char_start : chunk.char_end]:
        raise ValueError("chunk.text 必须等于 source_text[char_start:char_end]")


def validate_chunk_ordinals(chunks: list[KnowledgeChunk]) -> None:
    """校验同一文档内 ordinal 唯一（SPEC §4.1）。"""
    seen: dict[str, set[int]] = {}
    for chunk in chunks:
        ordinals = seen.setdefault(chunk.document_id, set())
        if chunk.ordinal in ordinals:
            raise ValueError(f"同一文档 ordinal 重复: {chunk.document_id}@{chunk.ordinal}")
        ordinals.add(chunk.ordinal)
