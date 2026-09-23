"""chunk_pages 纯函数契约测试（SPEC §5，Step 5-RED）。

引用尚未实现的 chunk_pages，运行时应以 ImportError 失败。
"""

from enterprise_policy_rag.application.ingestion.chunk_pages import chunk_pages
from enterprise_policy_rag.domain.entities import ParsedPage


def _page(number: int, text: str) -> ParsedPage:
    return ParsedPage(
        document_id="d1",
        page_number=number,
        source_text=text,
        source_text_sha256="x",
    )


def test_chunk_pages_deterministic():
    pages = (_page(1, "abcdefgh"),)
    chunks1 = chunk_pages(pages, "d1", chunk_size=2)
    chunks2 = chunk_pages(pages, "d1", chunk_size=2)
    assert [(c.page, c.char_start, c.char_end, c.text) for c in chunks1] == [
        (c.page, c.char_start, c.char_end, c.text) for c in chunks2
    ]


def test_chunk_pages_no_cross_page():
    pages = (_page(1, "aaaa"), _page(2, "bbbb"))
    chunks = chunk_pages(pages, "d1", chunk_size=2)
    for c in chunks:
        page = pages[c.page - 1]
        assert 0 <= c.char_start < c.char_end <= len(page.source_text)


def test_chunk_pages_char_range_recoverable():
    page = _page(1, "abcdef")
    chunks = chunk_pages((page,), "d1", chunk_size=2)
    assert len(chunks) > 0
    for c in chunks:
        assert c.text == page.source_text[c.char_start : c.char_end]


def test_chunk_pages_ordinal_unique():
    page = _page(1, "abcdefgh")
    chunks = chunk_pages((page,), "d1", chunk_size=2)
    ordinals = [c.ordinal for c in chunks]
    assert len(ordinals) == len(set(ordinals))
    assert ordinals == sorted(ordinals)
