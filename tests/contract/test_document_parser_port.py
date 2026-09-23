"""DocumentParserPort / ParsedDocumentDTO 契约测试（SPEC §5，Step 4-RED）。

引用尚未实现的 document_parser，运行时应以 ImportError 失败。
"""

import hashlib

from enterprise_policy_rag.application.ports.document_parser import (
    DocumentParserPort,
    ParsedDocumentDTO,
    ParsedPageDTO,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_parsed_page_dto_preserves_page_number_and_text():
    text = "第一页规范文本"
    page = ParsedPageDTO(
        page_number=1, source_text=text, source_text_sha256=_sha256(text)
    )
    assert page.page_number == 1
    assert page.source_text == text
    assert page.source_text_sha256 == _sha256(text)


def test_parsed_document_dto_holds_ordered_pages():
    p1 = ParsedPageDTO(page_number=1, source_text="a", source_text_sha256=_sha256("a"))
    p2 = ParsedPageDTO(page_number=2, source_text="b", source_text_sha256=_sha256("b"))
    doc = ParsedDocumentDTO(document_id="d1", pages=(p1, p2))
    assert doc.document_id == "d1"
    assert [p.page_number for p in doc.pages] == [1, 2]


def test_document_parser_port_declares_parse():
    assert hasattr(DocumentParserPort, "parse")
