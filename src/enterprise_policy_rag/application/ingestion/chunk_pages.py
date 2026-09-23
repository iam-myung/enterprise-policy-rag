"""页内切片纯函数（SPEC §5）。

Application 层纯函数，不走 Port，不引入 LLM 语义切片。
"""

import hashlib

from enterprise_policy_rag.domain.entities import KnowledgeChunk, ParsedPage


def chunk_pages(
    pages: tuple[ParsedPage, ...],
    document_id: str,
    chunk_size: int,
) -> tuple[KnowledgeChunk, ...]:
    """确定性页内切片：每页按 chunk_size 字符切分，不跨页，ordinal 唯一。"""
    chunks: list[KnowledgeChunk] = []
    ordinal = 0
    for page in pages:
        text = page.source_text
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            ordinal += 1
            chunk_text = text[start:end]
            chunks.append(
                KnowledgeChunk(
                    id=f"{document_id}-{ordinal}",
                    document_id=document_id,
                    ordinal=ordinal,
                    page=page.page_number,
                    char_start=start,
                    char_end=end,
                    text=chunk_text,
                    text_sha256=hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
                    token_count=len(chunk_text),
                )
            )
            start = end
    return tuple(chunks)
