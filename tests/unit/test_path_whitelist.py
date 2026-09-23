"""路径白名单契约测试（SPEC §10.1，Step 4-RED）。

引用尚未实现的 resolve_within_workspace，运行时应以 ImportError 失败。
"""

import os

import pytest

from enterprise_policy_rag.adapters.document.file_validation import (
    resolve_within_workspace,
)


def test_relative_path_resolved_within_workspace(tmp_path):
    result = resolve_within_workspace(tmp_path / "uploads" / "a.pdf", tmp_path)
    assert result.is_absolute()
    assert str(result).startswith(str(tmp_path.resolve()))


def test_dotdot_traversal_rejected(tmp_path):
    with pytest.raises(ValueError):
        resolve_within_workspace(tmp_path / ".." / "secret.txt", tmp_path)


def test_absolute_outside_rejected(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    with pytest.raises(ValueError):
        resolve_within_workspace(outside, tmp_path)


@pytest.mark.skipif(os.name == "nt", reason="软链接在 Windows 需管理员权限")
def test_symlink_outside_rejected(tmp_path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("x")
    link = tmp_path / "link.pdf"
    link.symlink_to(outside)
    with pytest.raises(ValueError):
        resolve_within_workspace(link, tmp_path)
