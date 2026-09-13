#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对 docs/reference 完整性检查做负向测试。

思路：逐个注入一种"看起来无害"的破坏，确认 verify_reference_digests.py
会 FAIL；每次注入后都从备份还原，并进行字节级比对，确保仓库回到原状。

用法：python -X utf8 code/scripts/negtest_reference_digests.py
"""

from pathlib import Path
import hashlib
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[2]
REF = REPO / "代码" / "docs" / "reference"
VERIFIER = REPO / "代码" / "scripts" / "verify_reference_digests.py"
CHECK = REPO / "代码" / "scripts" / "check_repo.ps1"

TARGET = REF / "DOC_INDEX_外部整理稿.md"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_verifier() -> tuple[int, str]:
    """Run the verifier and return (exit code, output tail)."""
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(VERIFIER)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    tail = (proc.stdout + proc.stderr).strip().splitlines()
    return proc.returncode, " | ".join(tail[-3:])


# 每种破坏：(名称, 变换函数)
def drop_banner(text: str) -> str:
    """整块删除入库说明头——最常见的“顺手清理”。"""
    marker = "# Tang Mega 60K 硬件资料索引"
    idx = text.find(marker)
    return text[idx:] if idx > 0 else text


def rename_banner(text: str) -> str:
    """把说明头降级成普通引用块，读者不再意识到这是外部稿。"""
    return text.replace("> **【本仓库入库说明", "> 【随便一段话")


def truncate_body(text: str) -> str:
    """删掉正文尾部——说明头还在，但内容缺了。"""
    marker = "# Tang Mega 60K 硬件资料索引"
    idx = text.find(marker)
    return text[:idx] + text[idx : idx + 200] if idx > 0 else text


MUTATIONS = [
    ("banner removed entirely", drop_banner),
    ("banner wording changed", rename_banner),
    ("body truncated", truncate_body),
]


def main() -> int:
    if not TARGET.is_file():
        print(f"missing target: {TARGET}")
        return 1

    pristine = TARGET.read_bytes()
    pristine_sha = hashlib.sha256(pristine).hexdigest()
    print(f"target : {TARGET.name}")
    print(f"pristine sha256 {pristine_sha[:32]}...")
    print()

    # 基线：未注入前必须 PASS
    code, tail = run_verifier()
    print(f"[baseline] exit={code}  {tail}")
    if code != 0:
        print("baseline already failing; aborting")
        return 1
    print()

    failures = 0
    for name, mutate in MUTATIONS:
        broken = mutate(pristine.decode("utf-8"))
        TARGET.write_bytes(broken.encode("utf-8"))

        code, tail = run_verifier()
        caught = code != 0
        print(f"[{name}]")
        print(f"  verifier exit={code}  caught={caught}")
        print(f"  {tail}")
        if not caught:
            print("  *** NEGATIVE TEST FAILED: mutation was not detected ***")
            failures += 1

        # 还原并做字节级比对
        TARGET.write_bytes(pristine)
        restored = hashlib.sha256(TARGET.read_bytes()).hexdigest()
        same = restored == pristine_sha
        print(f"  restored byte-identical: {same}")
        if not same:
            print("  *** RESTORE FAILED ***")
            failures += 1
        print()

    if failures:
        print(f"NEGATIVE TESTS FAILED ({failures})")
        return 1

    print(f"All {len(MUTATIONS)} mutations were caught and the file was restored.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
