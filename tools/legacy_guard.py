#!/usr/bin/env python3
"""旧 CASE 只读防线（SPEC §1.1）。

提供两个入口：
  1) 基线校验（verify）：重新计算 5 个旧 CASE 目录每个文件的相对路径 / 大小 / SHA-256，
     与 tools/legacy_manifest.json 比对，任何新增 / 删除 / 大小变化 / 内容变化都以非零退出阻断。
  2) 新源码运行时引用检查（check-refs）：扫描 src/ 下所有 .py，检查是否存在
     sys.path 操作、旧目录名字面量、动态加载、越界相对导入或指向旧 CASE 的软链接。

用法：
  python tools/legacy_guard.py gen          # 生成 / 更新基线 manifest
  python tools/legacy_guard.py verify       # 基线校验（零漂移）
  python tools/legacy_guard.py check-refs   # 新源码运行时引用检查
  python tools/legacy_guard.py all          # verify + check-refs（CI 入口）

退出码：0=通过；1=漂移/违规；2=配置错误；3=旧 CASE 缺失（无法执行 hash 校验）。
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

# 旧 CASE 只读参考目录（相对项目根，SPEC §1.1）
LEGACY_DIRS: list[str] = [
    "06_基座_RAG-企业知识库-实战版",
    "07_可吸收_CASE1-知识库处理场景",
    "08_可吸收_ragas-demo",
    "09_可吸收_CASE-切片策略",
    "10_可吸收_CASE-ChatPDF-Faiss",
]

MANIFEST_FILENAME = "legacy_manifest.json"
# 新源码根（相对仓库根；Python 包名仍为 enterprise_policy_rag）
SRC_ROOT = Path("src") / "enterprise_policy_rag"

_CHUNK_SIZE = 1024 * 1024

# 越界相对导入：4 个点及以上（最深合法相对导入为 3 点，到达 enterprise_policy_rag 包根）
_REL_IMPORT_OVERFLOW = re.compile(r"\bfrom\s+(\.{4,})")
# 动态加载手段
_DYNAMIC_LOAD_TOKENS = ("importlib", "__import__", "imp.load_source", "runpy.run_path")


def project_root() -> Path:
    """仓库根目录（旧 CASE、.docs 与应用代码同级）。

    legacy_guard.py 位于 <repo>/tools/，向上两级即仓库根。
    """
    return Path(__file__).resolve().parent.parent


def engine_root() -> Path:
    """应用工程根目录（含 src/、pyproject.toml）；上提后与仓库根相同。"""
    return Path(__file__).resolve().parent.parent


def manifest_path() -> Path:
    return Path(__file__).resolve().parent / MANIFEST_FILENAME


def _reconfigure_stdout() -> None:
    """确保中文输出在 Windows 控制台不因编码报错。"""
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def scan_legacy_files(root: Path) -> dict[str, dict[str, int | str]]:
    """扫描 5 个旧 CASE 目录，返回 {相对路径(as_posix): {"size": int, "sha256": str}}。"""
    files: dict[str, dict[str, int | str]] = {}
    for rel_dir in LEGACY_DIRS:
        base = root / rel_dir
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*")):
            if f.is_file():
                rel = f.relative_to(root).as_posix()
                files[rel] = {"size": f.stat().st_size, "sha256": sha256_file(f)}
    return files


def _load_manifest(mpath: Path) -> dict:
    if not mpath.exists():
        raise FileNotFoundError(str(mpath))
    return json.loads(mpath.read_text(encoding="utf-8"))


def cmd_gen(root: Path, mpath: Path) -> int:
    files = scan_legacy_files(root)
    if not files:
        print("ERROR: 未在旧 CASE 目录中发现任何文件。", file=sys.stderr)
        return 3
    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "description": (
            "旧 CASE 只读基线（SPEC §1.1）。"
            "记录每个旧文件相对项目根的路径/大小/SHA-256。"
        ),
        "legacy_directories": LEGACY_DIRS,
        "file_count": len(files),
        "files": [
            {"path": p, "size": meta["size"], "sha256": meta["sha256"]}
            for p, meta in sorted(files.items())
        ],
    }
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: 已生成基线 manifest：{mpath.name}")
    print(f"记录文件数：{len(files)}")
    return 0


def cmd_verify(root: Path, mpath: Path) -> int:
    try:
        manifest = _load_manifest(mpath)
    except FileNotFoundError:
        print(f"ERROR: manifest 不存在：{mpath}", file=sys.stderr)
        return 2

    # 旧 CASE 目录缺失时，不能误判为「通过 hash 检查」（SPEC §1.1 第 7 条）。
    missing_dirs = [d for d in LEGACY_DIRS if not (root / d).is_dir()]
    if missing_dirs:
        print("ERROR: 旧 CASE 目录缺失，无法执行 hash 基线校验：", file=sys.stderr)
        for d in missing_dirs:
            print(f"  - {d}", file=sys.stderr)
        print("提示：CI 环境无旧 CASE 时只执行 check-refs，不视为 hash 检查通过。", file=sys.stderr)
        return 3

    expected: dict[str, dict] = {e["path"]: e for e in manifest.get("files", [])}
    actual = scan_legacy_files(root)

    problems: list[str] = []
    for p in expected:
        if p not in actual:
            problems.append(f"DELETED: {p}")
    for p in actual:
        if p not in expected:
            problems.append(f"ADDED: {p}")
    for p in actual.keys() & expected.keys():
        a_size, e_size = actual[p]["size"], expected[p]["size"]
        a_sha, e_sha = actual[p]["sha256"], expected[p]["sha256"]
        if a_size != e_size:
            problems.append(f"SIZE_CHANGED: {p} (manifest={e_size}, actual={a_size})")
        if a_sha != e_sha:
            problems.append(f"HASH_CHANGED: {p}")

    if problems:
        print("FAIL: 旧 CASE 基线漂移，已阻断。差异如下：", file=sys.stderr)
        for pr in problems:
            print(f"  - {pr}", file=sys.stderr)
        return 1

    print(f"OK: 旧 CASE 基线零漂移（{len(actual)} 个文件 hash 一致）。")
    return 0


def cmd_check_refs(eng_root: Path) -> int:
    src_root = eng_root / SRC_ROOT
    if not src_root.is_dir():
        print(f"ERROR: 源码目录不存在：{src_root}", file=sys.stderr)
        return 2

    problems: list[str] = []
    py_files = sorted(src_root.rglob("*.py"))
    if not py_files:
        print("WARN: src/ 下未发现 .py 文件。", file=sys.stderr)

    for pf in py_files:
        rel = pf.relative_to(eng_root).as_posix()
        text = pf.read_text(encoding="utf-8", errors="replace")

        for d in LEGACY_DIRS:
            if d in text:
                problems.append(f"{rel}: 出现旧 CASE 目录名 '{d}'")

        # sys.path 操作：仅当同文件也出现旧 CASE 目录名时判违规（指向旧 CASE 的注入）。
        # 合法的 src 布局 sys.path（如 Alembic env.py 确保 src 在 sys.path）放行。
        if "sys.path" in text and any(d in text for d in LEGACY_DIRS):
            problems.append(f"{rel}: sys.path 操作疑似指向旧 CASE")

        for token in _DYNAMIC_LOAD_TOKENS:
            if token in text:
                problems.append(f"{rel}: 出现动态加载 '{token}'")

        if _REL_IMPORT_OVERFLOW.search(text):
            problems.append(f"{rel}: 出现越界相对导入（4 个点及以上）")

    # 软链接指向旧 CASE（Windows 下较少见，Linux CI 可能）
    for f in src_root.rglob("*"):
        try:
            if f.is_symlink():
                target = f.resolve()
                if any(d in target.as_posix() for d in LEGACY_DIRS):
                    problems.append(f"{f.relative_to(eng_root).as_posix()}: 软链接指向旧 CASE")
        except OSError:
            pass

    if problems:
        print("FAIL: 新源码存在指向旧 CASE 的运行时引用，已阻断：", file=sys.stderr)
        for pr in problems:
            print(f"  - {pr}", file=sys.stderr)
        return 1

    print(f"OK: 新源码无旧 CASE 运行时引用（检查 {len(py_files)} 个 .py 文件）。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="旧 CASE 只读防线（SPEC §1.1）")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("gen", help="生成 / 更新基线 manifest")
    sub.add_parser("verify", help="基线校验（零漂移）")
    sub.add_parser("check-refs", help="新源码运行时引用检查")
    sub.add_parser("all", help="verify + check-refs（CI 入口）")
    return parser


def main(argv: list[str] | None = None) -> int:
    _reconfigure_stdout()
    args = build_parser().parse_args(argv)
    root = project_root()
    eng_root = engine_root()
    mpath = manifest_path()

    if args.command == "gen":
        return cmd_gen(root, mpath)
    if args.command == "verify":
        return cmd_verify(root, mpath)
    if args.command == "check-refs":
        return cmd_check_refs(eng_root)
    if args.command == "all":
        rc_verify = cmd_verify(root, mpath)
        rc_refs = cmd_check_refs(eng_root)
        return rc_verify or rc_refs
    return 2


if __name__ == "__main__":
    sys.exit(main())
