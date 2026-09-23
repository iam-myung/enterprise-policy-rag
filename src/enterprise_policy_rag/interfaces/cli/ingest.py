"""制度导入 CLI 纯逻辑（SPEC §8.3）。

只定义命令逻辑；装配由 composition（Composition Root）完成，本模块不 import
composition。成功退出码 0，业务失败 2，Provider/系统失败 3。
"""

import argparse
import json
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any


def run(container: Any, argv: Sequence[str] | None = None) -> int:
    """给定已装配的 container，执行 PDF 导入。"""
    parser = argparse.ArgumentParser(description="导入企业制度 PDF")
    parser.add_argument("--file", required=True, help="PDF 文件路径")
    parser.add_argument("--title", required=True, help="制度名称")
    parser.add_argument("--version", required=True, help="制度版本")
    parser.add_argument("--scope", default="全体员工", help="适用范围")
    parser.add_argument("--source-kind", default="PUBLIC_SAMPLE", help="来源类型")
    parser.add_argument("--workspace", default="workspace", help="工作区根目录")
    args = parser.parse_args(argv)

    workspace_root = Path(args.workspace)
    uploads = workspace_root / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)

    src = Path(args.file)
    target = uploads / src.name
    shutil.copy(src, target)

    result = container.ingest(
        target, args.title, args.version, args.scope, args.source_kind
    )

    if result.success and result.data is not None:
        print(json.dumps(result.data, ensure_ascii=False, default=str, indent=2))
        return 0

    error = result.error
    print(
        json.dumps(
            {
                "success": False,
                "error": error.code.value if error else "INTERNAL_ERROR",
            },
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
    return 2
