"""文件校验契约测试（SPEC §10.1，Step 4-RED）。

引用尚未实现的 file_validation，运行时应以 ImportError 失败。
"""

from pathlib import Path

import pytest

from enterprise_policy_rag.adapters.document.file_validation import (
    FileValidationError,
    validate_upload_file,
)
from enterprise_policy_rag.domain.errors import ErrorCode


def _write(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def test_txt_extension_rejected(tmp_path):
    f = _write(tmp_path / "a.txt", b"%PDF-1.4 fake")
    with pytest.raises(FileValidationError) as exc:
        validate_upload_file(f, max_size_mib=20)
    assert exc.value.code is ErrorCode.UNSUPPORTED_FILE_TYPE


def test_bad_magic_rejected(tmp_path):
    f = _write(tmp_path / "a.pdf", b"not a pdf content")
    with pytest.raises(FileValidationError) as exc:
        validate_upload_file(f, max_size_mib=20)
    assert exc.value.code is ErrorCode.UNSUPPORTED_FILE_TYPE


def test_wrong_mime_rejected(tmp_path):
    f = _write(tmp_path / "a.pdf", b"%PDF-1.4 abc")
    with pytest.raises(FileValidationError) as exc:
        validate_upload_file(f, max_size_mib=20, content_type="text/plain")
    assert exc.value.code is ErrorCode.UNSUPPORTED_FILE_TYPE


def test_oversize_rejected(tmp_path):
    f = _write(tmp_path / "a.pdf", b"%PDF-1.4 abc")
    with pytest.raises(FileValidationError) as exc:
        validate_upload_file(f, max_size_mib=0)
    assert exc.value.code is ErrorCode.FILE_TOO_LARGE


def test_valid_pdf_accepted(tmp_path):
    f = _write(tmp_path / "a.pdf", b"%PDF-1.4\n1 0 obj\n")
    validate_upload_file(f, max_size_mib=20)  # 不抛异常
