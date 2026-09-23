"""文档解析 Port（SPEC §5）。"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ParsedPageDTO:
    """规范页文本 DTO（页码从 1 开始）。"""

    page_number: int
    source_text: str
    source_text_sha256: str


@dataclass(frozen=True)
class ParsedDocumentDTO:
    """解析结果 DTO：文档 ID + 有序页列表。"""

    document_id: str
    pages: tuple[ParsedPageDTO, ...]


class DocumentParserPort(Protocol):
    """文档解析 Port（SPEC §5）：上传文件快照 → ParsedDocumentDTO。"""

    def parse(self, file_path: Path, document_id: str) -> ParsedDocumentDTO: ...
