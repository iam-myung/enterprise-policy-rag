"""文件校验与路径白名单（SPEC §10.1）。"""

from pathlib import Path

from enterprise_policy_rag.domain.errors import ErrorCode


class FileValidationError(Exception):
    """文件/解析失败，携带安全 ErrorCode（不泄露内部细节）。"""

    def __init__(self, code: ErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_PDF_MAGIC = b"%PDF-"


def validate_upload_file(
    path: Path,
    max_size_mib: float,
    content_type: str | None = None,
) -> None:
    """校验 PDF 扩展名 / MIME / 魔数 / 大小；违反抛 FileValidationError。"""
    if content_type is not None and content_type != "application/pdf":
        raise FileValidationError(ErrorCode.UNSUPPORTED_FILE_TYPE, "非 PDF MIME 类型")
    if path.suffix.lower() != ".pdf":
        raise FileValidationError(ErrorCode.UNSUPPORTED_FILE_TYPE, "非 PDF 扩展名")
    with path.open("rb") as fh:
        head = fh.read(len(_PDF_MAGIC))
    if not head.startswith(_PDF_MAGIC):
        raise FileValidationError(ErrorCode.UNSUPPORTED_FILE_TYPE, "PDF 魔数不匹配")
    max_bytes = int(max_size_mib * 1024 * 1024)
    if path.stat().st_size > max_bytes:
        raise FileValidationError(ErrorCode.FILE_TOO_LARGE, "文件大小超限")


def resolve_within_workspace(path: Path, workspace_root: Path) -> Path:
    """Path.resolve() 后验证位于 workspace_root 下；拒绝 ..、绝对路径、越界软链接。"""
    root = workspace_root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ValueError(f"路径越界: {path}") from None
    return resolved
