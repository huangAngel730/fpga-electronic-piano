#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一生成物manifest更新工具

扫描generated目录下所有已跟踪的生成文件，更新manifest.json的SHA-256校验和。
用于验证生成物的可重复性。
"""

import json
import hashlib
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GENERATED_DIR = SCRIPT_DIR / "generated"
MANIFEST_PATH = GENERATED_DIR / "manifest.json"


def compute_sha256(file_path: Path) -> str:
    """计算文件的SHA-256"""
    sha256 = hashlib.sha256()
    sha256.update(file_path.read_bytes())
    return sha256.hexdigest()


def scan_generated_files():
    """扫描所有生成文件并计算哈希"""
    files = {}

    # 扫描所有非manifest的文件
    for file_path in sorted(GENERATED_DIR.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.name == "manifest.json":
            continue

        # 相对路径
        rel_path = file_path.relative_to(GENERATED_DIR)
        rel_str = str(rel_path).replace("\\", "/")

        files[rel_str] = {
            "bytes": file_path.stat().st_size,
            "sha256": compute_sha256(file_path)
        }

    return files


def update_manifest():
    """更新manifest.json"""
    # 加载现有manifest
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
    else:
        manifest = {
            "generator": "code/model/wavetable_gen.py + generate_test_mode_reference.py + mixer.py",
            "generator_version": "1.0.0",
            "parameters": {}
        }

    # 扫描文件
    files = scan_generated_files()
    manifest["files"] = files

    # 从wavetable_gen.py的manifest中提取parameters
    try:
        from audio_defs import (
            SAMPLE_RATE_HZ, PCM_BITS, PHASE_BITS,
            WT_AMPLITUDE, WT_LENGTH, WT_SAMPLE_BITS
        )
        manifest["parameters"] = {
            "sample_rate_hz": SAMPLE_RATE_HZ,
            "pcm_bits": PCM_BITS,
            "phase_bits": PHASE_BITS,
            "wavetable_amplitude": WT_AMPLITUDE,
            "wavetable_length": WT_LENGTH,
            "wavetable_sample_bits": WT_SAMPLE_BITS
        }
    except ImportError:
        pass

    # 写回manifest
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding='utf-8',
        newline='\n'
    )

    print(f"[PASS] 已更新manifest: {len(files)} 个文件")
    for name in sorted(files):
        print(f"  {name}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(update_manifest())
