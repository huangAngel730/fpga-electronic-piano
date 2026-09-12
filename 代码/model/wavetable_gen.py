# -*- coding: utf-8 -*-
"""波表、FCW 表与固定 PCM 测试向量生成脚本（T003）。

生成结果全部落在 ``代码/model/generated/``，供以下三方直接使用：

- M1 的 RTL（T004 起）用 ``$readmemh`` 读波表 ROM 与 FCW 表；
- M2 的 I2S 发送器自检 TB（T005）用固定 24 位 PCM 向量做逐样本比较；
- 竞赛报告引用 ``fcw_midi_48k.csv`` 中的频率误差数据。

设计要求：可重复执行，任意次运行结果逐字节一致。因此生成内容里
不写日期、路径、随机数和字典无序结构。

用法（在仓库根目录执行）：

.. code-block:: powershell

    python -X utf8 代码/model/wavetable_gen.py                 # 生成到默认目录
    python -X utf8 代码/model/wavetable_gen.py --check         # 只校验不写盘
    python -X utf8 代码/model/wavetable_gen.py --outdir 某目录  # 生成到指定目录

``--check`` 用于确认仓库里已提交的生成结果与当前脚本一致，
不一致时返回退出码 1，并列出差异文件。
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audio_defs import (  # noqa: E402
    GAIN_Q15_ONE,
    PCM_BITS,
    PCM_MAX,
    PCM_MIN,
    PHASE_BITS,
    SAMPLE_RATE_HZ,
    WT_AMPLITUDE,
    WT_LENGTH,
    WT_SAMPLE_BITS,
    to_hex_word,
)
from dds_model import (  # noqa: E402
    WAVEFORM_NAMES,
    build_note_table,
    make_wavetable,
    midi_note_name,
    render_pcm24,
)

# --------------------------------------------------------------------------
# 生成参数。改动这里必须同步更新
# 代码/docs/test/DDS参考模型与波表格式说明.md，并通知 M2。
# --------------------------------------------------------------------------

#: 生成器版本号。任何会改变输出内容的修改都要递增，便于追溯已发出的向量。
GENERATOR_VERSION = "1.0.0"

DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "generated"

#: 交付给 M2 的参考音频参数。
REFERENCE_FREQ_HZ = 440.0
REFERENCE_WAVEFORM = "sine"
REFERENCE_SAMPLE_COUNT = 4800  # 100 ms，约 44 个周期，足够做频率复核
REFERENCE_LEFT_GAIN_Q15 = GAIN_Q15_ONE  # 0 dB，满幅，用于检查符号位与 MSB
REFERENCE_RIGHT_GAIN_Q15 = GAIN_Q15_ONE // 2  # 精确 -6.0206 dB，用于区分左右声道

#: 边界测试向量。覆盖 0、正负 1、正负满幅、半满幅、交替位型和只有低位有效的值。
#: 目的是让 M2 的 I2S TB 能查出符号扩展错误、MSB first 反了、
#: 24 位有效数据与 8 位填充零错位这三类高频问题。
CORNER_LEFT_VALUES = (
    0,
    1,
    -1,
    PCM_MAX,
    PCM_MIN,
    PCM_MAX - 1,
    PCM_MIN + 1,
    1 << (PCM_BITS - 2),  # 0x400000，正半满幅
    -(1 << (PCM_BITS - 2)),  # 0xc00000，负半满幅
    0x555555,
    0xAAAAAA - (1 << PCM_BITS),  # 0xaaaaaa 的有符号值 -5592406
    0x0000FF,  # 只有最低 8 位有效，检查槽位填充是否吃掉有效位
    0x00FF00,
    -(1 << 16),  # 0xff0000
)


def _text_file(lines: list[str]) -> bytes:
    """把若干行拼成 LF 结尾的 UTF-8 字节串。

    统一用字节写盘，避免 Windows 上被换行符转换破坏可重复性，
    也与仓库 ``.gitattributes`` 的 LF 规则一致。
    """
    return ("\n".join(lines) + "\n").encode("utf-8")


def _hex_lines(values: list[int], bits: int) -> list[str]:
    return [to_hex_word(value, bits) for value in values]


def build_artifacts() -> dict[str, bytes]:
    """在内存中构造全部生成物，返回 {相对文件名: 字节内容}。

    先构造再写盘，是为了让 ``--check`` 能在不碰磁盘的前提下做比对。
    """
    artifacts: dict[str, bytes] = {}

    # 一 波表 ROM
    for name in WAVEFORM_NAMES:
        table = make_wavetable(name, WT_LENGTH, WT_AMPLITUDE)
        filename = f"wt_{name}_{WT_LENGTH}x{WT_SAMPLE_BITS}.hex"
        artifacts[filename] = _text_file(_hex_lines(table, WT_SAMPLE_BITS))

    # 二 MIDI 音符 FCW 表
    notes = build_note_table(SAMPLE_RATE_HZ)
    artifacts[f"fcw_midi_{SAMPLE_RATE_HZ // 1000}k.hex"] = _text_file(
        [f"{report.fcw:08x}" for report in notes]
    )
    csv_lines = ["note,name,ideal_hz,fcw_dec,fcw_hex,actual_hz,error_hz,error_cent"]
    for report in notes:
        csv_lines.append(
            ",".join(
                (
                    str(report.note),
                    midi_note_name(report.note),
                    f"{report.ideal_hz:.6f}",
                    str(report.fcw),
                    f"{report.fcw:08x}",
                    f"{report.actual_hz:.6f}",
                    f"{report.error_hz:+.9f}",
                    f"{report.error_cent:+.6f}",
                )
            )
        )
    artifacts[f"fcw_midi_{SAMPLE_RATE_HZ // 1000}k.csv"] = _text_file(csv_lines)

    # 三 440 Hz 参考 PCM，交付给 M2 做 I2S 逐样本比较
    left = render_pcm24(
        REFERENCE_WAVEFORM,
        REFERENCE_FREQ_HZ,
        REFERENCE_SAMPLE_COUNT,
        gain_q15=REFERENCE_LEFT_GAIN_Q15,
    )
    right = render_pcm24(
        REFERENCE_WAVEFORM,
        REFERENCE_FREQ_HZ,
        REFERENCE_SAMPLE_COUNT,
        gain_q15=REFERENCE_RIGHT_GAIN_Q15,
    )
    artifacts["pcm_ref_440hz_sine_left.hex"] = _text_file(
        _hex_lines(left.pcm, PCM_BITS)
    )
    artifacts["pcm_ref_440hz_sine_right.hex"] = _text_file(
        _hex_lines(right.pcm, PCM_BITS)
    )

    # 四 边界测试向量。右声道整体错开一位，任何左右互换都会立刻暴露。
    corner_left = list(CORNER_LEFT_VALUES)
    corner_right = corner_left[1:] + corner_left[:1]
    artifacts["pcm_corner_left.hex"] = _text_file(
        _hex_lines(corner_left, PCM_BITS)
    )
    artifacts["pcm_corner_right.hex"] = _text_file(
        _hex_lines(corner_right, PCM_BITS)
    )

    # 五 参数与校验清单
    manifest = {
        "generator": "代码/model/wavetable_gen.py",
        "generator_version": GENERATOR_VERSION,
        "parameters": {
            "sample_rate_hz": SAMPLE_RATE_HZ,
            "phase_bits": PHASE_BITS,
            "wavetable_length": WT_LENGTH,
            "wavetable_sample_bits": WT_SAMPLE_BITS,
            "wavetable_amplitude": WT_AMPLITUDE,
            "pcm_bits": PCM_BITS,
            "reference_waveform": REFERENCE_WAVEFORM,
            "reference_freq_hz": REFERENCE_FREQ_HZ,
            "reference_sample_count": REFERENCE_SAMPLE_COUNT,
            "reference_left_gain_q15": REFERENCE_LEFT_GAIN_Q15,
            "reference_right_gain_q15": REFERENCE_RIGHT_GAIN_Q15,
            "reference_fcw": left.fcw,
            "reference_actual_freq_hz": left.actual_freq_hz,
            "reference_left_clip_count": left.clip_count,
            "reference_right_clip_count": right.clip_count,
        },
        "files": {
            name: {
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "lines": data.count(b"\n"),
            }
            for name, data in sorted(artifacts.items())
        },
    }
    artifacts["manifest.json"] = _text_file(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).split(
            "\n"
        )
    )
    return artifacts


def write_artifacts(output_dir: Path) -> list[str]:
    """生成并写盘，返回按字典序排列的文件名列表。"""
    artifacts = build_artifacts()
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in sorted(artifacts):
        (output_dir / name).write_bytes(artifacts[name])
    return sorted(artifacts)


def check_artifacts(output_dir: Path) -> list[str]:
    """比对磁盘内容与当前脚本的输出，返回不一致的文件名列表。"""
    artifacts = build_artifacts()
    mismatched = []
    for name in sorted(artifacts):
        path = output_dir / name
        if not path.is_file():
            mismatched.append(f"{name}（缺失）")
        elif path.read_bytes() != artifacts[name]:
            mismatched.append(f"{name}（内容不一致）")
    extra = sorted(
        item.name
        for item in output_dir.glob("*")
        if item.is_file() and item.name not in artifacts
    )
    mismatched.extend(f"{name}（多余文件）" for name in extra)
    return mismatched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="生成波表、MIDI FCW 表与固定 24 位 PCM 测试向量"
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"输出目录，默认 {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="只校验已有输出是否与脚本一致，不写盘；不一致返回退出码 1",
    )
    args = parser.parse_args(argv)

    if args.check:
        if not args.outdir.is_dir():
            print(f"[FAIL] 目录不存在：{args.outdir}")
            return 1
        mismatched = check_artifacts(args.outdir)
        if mismatched:
            print(f"[FAIL] 与脚本输出不一致，共 {len(mismatched)} 项：")
            for name in mismatched:
                print(f"       {name}")
            print("       执行不带 --check 的同一条命令即可重新生成")
            return 1
        print(f"[PASS] {args.outdir} 下全部生成物与脚本输出一致")
        return 0

    names = write_artifacts(args.outdir)
    print(f"生成器版本 {GENERATOR_VERSION}，输出目录 {args.outdir}")
    for name in names:
        size = (args.outdir / name).stat().st_size
        print(f"  {name}  {size} 字节")
    print(f"[PASS] 共生成 {len(names)} 个文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
