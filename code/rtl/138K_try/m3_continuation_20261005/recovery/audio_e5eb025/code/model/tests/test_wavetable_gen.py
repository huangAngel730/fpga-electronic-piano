# -*- coding: utf-8 -*-
"""T003 波表与 FCW 生成脚本自检。

重点验证三件事：

1. 可重复生成。同一份脚本任意次运行必须逐字节一致，否则 RTL 用的 ROM
   和 M2 手上的测试向量就没有共同基准。
2. 仓库里已提交的 ``code/model/generated/`` 与当前脚本输出一致，
   防止改了脚本却忘记重新生成。
3. 文件格式与模型一致，回读解析后能还原出模型算出的数值。
"""

import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[1]
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

import wavetable_gen  # noqa: E402
from audio_defs import (  # noqa: E402
    PCM_BITS,
    PCM_MAX,
    PCM_MIN,
    SAMPLE_RATE_HZ,
    WT_LENGTH,
    WT_SAMPLE_BITS,
    from_hex_word,
)
from dds_model import (  # noqa: E402
    WAVEFORM_NAMES,
    build_note_table,
    make_wavetable,
    render_pcm24,
)

GENERATED_DIR = MODEL_DIR / "generated"


def _report(label: str, text: str) -> None:
    print(f"    [数据] {label}: {text}")


def _parse_hex_file(data: bytes, bits: int) -> list[int]:
    text = data.decode("utf-8")
    return [from_hex_word(line, bits) for line in text.splitlines()]


class TestReproducibility(unittest.TestCase):
    """可重复生成检查，对应 T003 的验收条件。"""

    def test_two_builds_are_byte_identical(self):
        first = wavetable_gen.build_artifacts()
        second = wavetable_gen.build_artifacts()
        self.assertEqual(sorted(first), sorted(second))
        for name in first:
            with self.subTest(file=name):
                self.assertEqual(first[name], second[name])
        _report(
            "两次内存生成一致性",
            f"{len(first)} 个文件逐字节相同",
        )

    def test_two_writes_produce_identical_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            dir_a = Path(tmp) / "a"
            dir_b = Path(tmp) / "b"
            names_a = wavetable_gen.write_artifacts(dir_a)
            names_b = wavetable_gen.write_artifacts(dir_b)
            self.assertEqual(names_a, names_b)
            for name in names_a:
                with self.subTest(file=name):
                    digest_a = hashlib.sha256(
                        (dir_a / name).read_bytes()
                    ).hexdigest()
                    digest_b = hashlib.sha256(
                        (dir_b / name).read_bytes()
                    ).hexdigest()
                    self.assertEqual(digest_a, digest_b)

    def test_committed_output_matches_script(self):
        self.assertTrue(
            GENERATED_DIR.is_dir(),
            f"缺少生成目录 {GENERATED_DIR}，先运行 wavetable_gen.py",
        )
        mismatched = wavetable_gen.check_artifacts(GENERATED_DIR)
        self.assertEqual(
            mismatched,
            [],
            "仓库中的生成物与脚本输出不一致，需要重新生成并提交",
        )

    def test_check_detects_tampering(self):
        """异常场景：生成物被改动一个字节，校验必须报出来。"""
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "generated"
            shutil.copytree(GENERATED_DIR, work)
            target = work / f"wt_sine_{WT_LENGTH}x{WT_SAMPLE_BITS}.hex"
            raw = bytearray(target.read_bytes())
            raw[0] = ord("f") if raw[0] != ord("f") else ord("0")
            target.write_bytes(bytes(raw))
            mismatched = wavetable_gen.check_artifacts(work)
            self.assertEqual(len(mismatched), 1)
            self.assertIn(target.name, mismatched[0])

    def test_check_detects_missing_and_extra_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "generated"
            shutil.copytree(GENERATED_DIR, work)
            (work / "manifest.json").unlink()
            (work / "不该出现的文件.txt").write_bytes(b"x\n")
            mismatched = wavetable_gen.check_artifacts(work)
            self.assertEqual(len(mismatched), 2)


class TestFileFormats(unittest.TestCase):
    """文件格式与模型数值一致性。"""

    @classmethod
    def setUpClass(cls):
        cls.artifacts = wavetable_gen.build_artifacts()

    def test_wavetable_files(self):
        for name in WAVEFORM_NAMES:
            filename = f"wt_{name}_{WT_LENGTH}x{WT_SAMPLE_BITS}.hex"
            with self.subTest(file=filename):
                data = self.artifacts[filename]
                lines = data.decode("utf-8").splitlines()
                self.assertEqual(len(lines), WT_LENGTH)
                for line in lines:
                    self.assertEqual(len(line), WT_SAMPLE_BITS // 4)
                    self.assertEqual(line, line.lower())
                self.assertEqual(
                    _parse_hex_file(data, WT_SAMPLE_BITS), make_wavetable(name)
                )

    def test_fcw_hex_and_csv_agree_with_model(self):
        reports = build_note_table()
        hex_name = f"fcw_midi_{SAMPLE_RATE_HZ // 1000}k.hex"
        lines = self.artifacts[hex_name].decode("utf-8").splitlines()
        self.assertEqual(len(lines), 128)
        for report, line in zip(reports, lines):
            with self.subTest(note=report.note):
                self.assertEqual(len(line), 8)
                self.assertEqual(int(line, 16), report.fcw)

        csv_name = f"fcw_midi_{SAMPLE_RATE_HZ // 1000}k.csv"
        csv_lines = self.artifacts[csv_name].decode("utf-8").splitlines()
        self.assertEqual(len(csv_lines), 129)  # 表头 + 128 行
        self.assertTrue(csv_lines[0].startswith("note,name,ideal_hz,"))
        for report, line in zip(reports, csv_lines[1:]):
            fields = line.split(",")
            with self.subTest(note=report.note):
                self.assertEqual(int(fields[0]), report.note)
                self.assertEqual(int(fields[3]), report.fcw)
                self.assertAlmostEqual(
                    float(fields[2]), report.ideal_hz, places=5
                )

    def test_reference_pcm_matches_model(self):
        left = _parse_hex_file(
            self.artifacts["pcm_ref_440hz_sine_left.hex"], PCM_BITS
        )
        right = _parse_hex_file(
            self.artifacts["pcm_ref_440hz_sine_right.hex"], PCM_BITS
        )
        expected = render_pcm24(
            wavetable_gen.REFERENCE_WAVEFORM,
            wavetable_gen.REFERENCE_FREQ_HZ,
            wavetable_gen.REFERENCE_SAMPLE_COUNT,
            gain_q15=wavetable_gen.REFERENCE_LEFT_GAIN_Q15,
        )
        self.assertEqual(len(left), wavetable_gen.REFERENCE_SAMPLE_COUNT)
        self.assertEqual(len(right), wavetable_gen.REFERENCE_SAMPLE_COUNT)
        self.assertEqual(left, expected.pcm)
        # 右声道固定为左声道的一半，精确可整除，用于识别左右声道接反
        for index, (l_value, r_value) in enumerate(zip(left, right)):
            with self.subTest(index=index):
                self.assertEqual(r_value * 2, l_value)
        self.assertTrue(all(PCM_MIN <= v <= PCM_MAX for v in left))
        _report(
            "440 Hz 参考 PCM",
            f"{len(left)} 样本，左声道范围 [{min(left)}, {max(left)}]，"
            f"右声道范围 [{min(right)}, {max(right)}]，削波 "
            f"{expected.clip_count} 次",
        )

    def test_corner_vectors_cover_boundaries(self):
        left = _parse_hex_file(self.artifacts["pcm_corner_left.hex"], PCM_BITS)
        right = _parse_hex_file(
            self.artifacts["pcm_corner_right.hex"], PCM_BITS
        )
        self.assertEqual(left, list(wavetable_gen.CORNER_LEFT_VALUES))
        self.assertEqual(right, left[1:] + left[:1])
        for required in (0, 1, -1, PCM_MAX, PCM_MIN):
            with self.subTest(value=required):
                self.assertIn(required, left)
        self.assertTrue(all(PCM_MIN <= v <= PCM_MAX for v in left))
        _report(
            "边界测试向量",
            f"{len(left)} 组，含 0、正负 1、正负满幅、半满幅与 0x555555/0xaaaaaa 交替位型",
        )

    def test_manifest_hashes_match_artifacts(self):
        import json

        manifest = json.loads(
            self.artifacts["manifest.json"].decode("utf-8")
        )
        self.assertEqual(
            manifest["generator_version"], wavetable_gen.GENERATOR_VERSION
        )
        self.assertEqual(
            manifest["parameters"]["sample_rate_hz"], SAMPLE_RATE_HZ
        )
        listed = set(manifest["files"])
        produced = set(self.artifacts) - {"manifest.json"}
        self.assertEqual(listed, produced)
        for name, info in manifest["files"].items():
            with self.subTest(file=name):
                self.assertEqual(
                    info["sha256"],
                    hashlib.sha256(self.artifacts[name]).hexdigest(),
                )
                self.assertEqual(info["bytes"], len(self.artifacts[name]))

    def test_all_files_use_lf_line_endings(self):
        """仓库统一 LF，生成物也必须是 LF，否则在别人机器上会整文件 diff。"""
        for name, data in self.artifacts.items():
            with self.subTest(file=name):
                self.assertNotIn(b"\r", data)
                self.assertTrue(data.endswith(b"\n"))


class TestCommandLine(unittest.TestCase):
    """命令行行为，保证文档里写的命令真的能用。"""

    def test_check_mode_returns_zero_on_match(self):
        self.assertEqual(
            wavetable_gen.main(["--check", "--outdir", str(GENERATED_DIR)]), 0
        )

    def test_check_mode_returns_one_on_missing_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "不存在"
            self.assertEqual(
                wavetable_gen.main(["--check", "--outdir", str(missing)]), 1
            )

    def test_generate_then_check_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            self.assertEqual(wavetable_gen.main(["--outdir", str(out)]), 0)
            self.assertEqual(
                wavetable_gen.main(["--check", "--outdir", str(out)]), 0
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
