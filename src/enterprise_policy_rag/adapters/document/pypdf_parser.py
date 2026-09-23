"""PDF 解析适配器（SPEC §5 DocumentParserPort）。

Phase 1 用 pypdf 提取文本 PDF 的规范页文本；DocumentParserPort 隔离供应商，
后续如需复杂布局/扫描件解析可另接重型解析器（如 MinerU）。
"""

import hashlib
from pathlib import Path

from pypdf import PdfReader

from enterprise_policy_rag.adapters.document.file_validation import FileValidationError
from enterprise_policy_rag.application.ports.document_parser import (
    ParsedDocumentDTO,
    ParsedPageDTO,
)
from enterprise_policy_rag.domain.errors import ErrorCode


class PypdfParser:
    """DocumentParserPort 的 PDF 解析实现（Phase 1 用 pypdf 提取文本）。"""

    def parse(self, file_path: Path, document_id: str) -> ParsedDocumentDTO:
        try:
            reader = PdfReader(str(file_path))
            pages: list[ParsedPageDTO] = []
            for index, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                pages.append(
                    ParsedPageDTO(
                        page_number=index,
                        source_text=text,
                        source_text_sha256=hashlib.sha256(
                            text.encode("utf-8")
                        ).hexdigest(),
                    )
                )
            return ParsedDocumentDTO(document_id=document_id, pages=tuple(pages))
        except FileValidationError:
            raise
        except Exception as exc:
            raise FileValidationError(
                ErrorCode.DOCUMENT_PARSE_FAILED, "PDF 解析失败"
            ) from exc
