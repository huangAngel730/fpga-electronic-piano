#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RTL验证器自动测试

测试 rtl_verifier.py 的成功和失败场景，确保：
1. 验证通过时返回 0
2. 样本失配、长度不一致、非法hex、缺文件时返回非0
3. 削波标志验证正确工作
"""

import sys
import unittest
from pathlib import Path
import tempfile
import shutil

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from rtl_verifier import (
    load_hex_file,
    load_clipped_flags,
    compare_samples,
    verify_mixer_rtl
)


class TestLoadHexFile(unittest.TestCase):
    """测试hex文件加载"""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_load_valid_hex(self):
        """加载有效hex文件"""
        file_path = self.temp_dir / "test.txt"
        file_path.write_text("000000\n7FFFFF\n800000\nFFFFFF\n", encoding='utf-8', newline='\n')

        samples = load_hex_file(file_path)
        self.assertEqual(len(samples), 4)
        self.assertEqual(samples[0], 0)
        self.assertEqual(samples[1], 8388607)   # 最大正数
        self.assertEqual(samples[2], -8388608)  # 最小负数
        self.assertEqual(samples[3], -1)

    def test_load_with_0x_prefix(self):
        """支持0x前缀"""
        file_path = self.temp_dir / "test.txt"
        file_path.write_text("0x000000\n0x7FFFFF\n", encoding='utf-8', newline='\n')

        samples = load_hex_file(file_path)
        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[0], 0)
        self.assertEqual(samples[1], 8388607)

    def test_skip_comments_and_empty_lines(self):
        """跳过注释和空行"""
        file_path = self.temp_dir / "test.txt"
        file_path.write_text("# comment\n000000\n\n7FFFFF\n# another\n", encoding='utf-8', newline='\n')

        samples = load_hex_file(file_path)
        self.assertEqual(len(samples), 2)

    def test_invalid_hex_length(self):
        """非法hex长度"""
        file_path = self.temp_dir / "test.txt"
        file_path.write_text("00000\n", encoding='utf-8', newline='\n')  # 5位，应该是6位

        with self.assertRaises(ValueError) as ctx:
            load_hex_file(file_path)
        self.assertIn("hex长度必须为6位", str(ctx.exception))

    def test_invalid_hex_chars(self):
        """非法hex字符"""
        file_path = self.temp_dir / "test.txt"
        file_path.write_text("GGGGGG\n", encoding='utf-8', newline='\n')

        with self.assertRaises(ValueError) as ctx:
            load_hex_file(file_path)
        self.assertIn("非法hex字符", str(ctx.exception))

    def test_file_not_found(self):
        """文件不存在"""
        with self.assertRaises(FileNotFoundError):
            load_hex_file(self.temp_dir / "nonexistent.txt")

    def test_empty_file(self):
        """空文件"""
        file_path = self.temp_dir / "empty.txt"
        file_path.write_text("", encoding='utf-8', newline='\n')

        with self.assertRaises(ValueError) as ctx:
            load_hex_file(file_path)
        self.assertIn("文件为空或无有效数据", str(ctx.exception))


class TestLoadClippedFlags(unittest.TestCase):
    """测试削波标志加载"""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_load_valid_flags(self):
        """加载有效削波标志"""
        file_path = self.temp_dir / "clipped.txt"
        file_path.write_text("0\n1\n0\n1\n", encoding='utf-8', newline='\n')

        flags = load_clipped_flags(file_path)
        self.assertEqual(len(flags), 4)
        self.assertEqual(flags, [False, True, False, True])

    def test_invalid_flag_value(self):
        """非法标志值"""
        file_path = self.temp_dir / "clipped.txt"
        file_path.write_text("0\n2\n", encoding='utf-8', newline='\n')  # 2是非法值

        with self.assertRaises(ValueError) as ctx:
            load_clipped_flags(file_path)
        self.assertIn("削波标志必须为'0'或'1'", str(ctx.exception))


class TestCompareSamples(unittest.TestCase):
    """测试样本对比"""

    def test_perfect_match(self):
        """完全匹配"""
        ref = [100, 200, 300]
        rtl = [100, 200, 300]

        passed, stats = compare_samples(ref, rtl, tolerance=0)
        self.assertTrue(passed)
        self.assertEqual(stats['total_samples'], 3)
        self.assertEqual(stats['mismatches'], 0)
        self.assertEqual(stats['max_error'], 0)

    def test_length_mismatch(self):
        """长度不一致"""
        ref = [100, 200, 300]
        rtl = [100, 200]

        passed, stats = compare_samples(ref, rtl, tolerance=0)
        self.assertFalse(passed)
        self.assertEqual(stats['error'], 'length_mismatch')
        self.assertEqual(stats['ref_len'], 3)
        self.assertEqual(stats['rtl_len'], 2)

    def test_one_sample_mismatch(self):
        """一个样本失配"""
        ref = [100, 200, 300]
        rtl = [100, 201, 300]

        passed, stats = compare_samples(ref, rtl, tolerance=0)
        self.assertFalse(passed)
        self.assertEqual(stats['mismatches'], 1)
        self.assertEqual(stats['first_mismatch']['index'], 1)
        self.assertEqual(stats['first_mismatch']['error'], 1)

    def test_tolerance(self):
        """容差测试"""
        ref = [100, 200, 300]
        rtl = [100, 201, 299]

        # 容差0：失败
        passed, stats = compare_samples(ref, rtl, tolerance=0)
        self.assertFalse(passed)
        self.assertEqual(stats['mismatches'], 2)

        # 容差1：通过
        passed, stats = compare_samples(ref, rtl, tolerance=1)
        self.assertTrue(passed)
        self.assertEqual(stats['max_error'], 1)


class TestVerifyMixerRTL(unittest.TestCase):
    """测试混音器RTL验证（端到端）"""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.ref_dir = self.temp_dir / "ref"
        self.rtl_dir = self.temp_dir / "rtl"
        self.ref_dir.mkdir()
        self.rtl_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_complete_match(self):
        """PCM和削波标志完全匹配"""
        # 参考文件
        (self.ref_dir / "mixer_outputs.txt").write_text(
            "000000\n7FFFFF\n800000\n", encoding='utf-8', newline='\n'
        )
        (self.ref_dir / "mixer_clipped.txt").write_text(
            "0\n1\n1\n", encoding='utf-8', newline='\n'
        )

        # RTL文件（完全匹配）
        (self.rtl_dir / "mixer_rtl_outputs.txt").write_text(
            "000000\n7FFFFF\n800000\n", encoding='utf-8', newline='\n'
        )
        (self.rtl_dir / "mixer_rtl_clipped.txt").write_text(
            "0\n1\n1\n", encoding='utf-8', newline='\n'
        )

        result = verify_mixer_rtl(self.rtl_dir, self.ref_dir, tolerance=0)
        self.assertTrue(result)

    def test_pcm_mismatch(self):
        """PCM不匹配"""
        (self.ref_dir / "mixer_outputs.txt").write_text(
            "000000\n7FFFFF\n", encoding='utf-8', newline='\n'
        )
        (self.ref_dir / "mixer_clipped.txt").write_text(
            "0\n1\n", encoding='utf-8', newline='\n'
        )

        (self.rtl_dir / "mixer_rtl_outputs.txt").write_text(
            "000000\n7FFFFE\n", encoding='utf-8', newline='\n'  # 第二个样本不匹配
        )
        (self.rtl_dir / "mixer_rtl_clipped.txt").write_text(
            "0\n1\n", encoding='utf-8', newline='\n'
        )

        result = verify_mixer_rtl(self.rtl_dir, self.ref_dir, tolerance=0)
        self.assertFalse(result)

    def test_clipped_mismatch(self):
        """削波标志不匹配"""
        (self.ref_dir / "mixer_outputs.txt").write_text(
            "000000\n7FFFFF\n", encoding='utf-8', newline='\n'
        )
        (self.ref_dir / "mixer_clipped.txt").write_text(
            "0\n1\n", encoding='utf-8', newline='\n'
        )

        (self.rtl_dir / "mixer_rtl_outputs.txt").write_text(
            "000000\n7FFFFF\n", encoding='utf-8', newline='\n'
        )
        (self.rtl_dir / "mixer_rtl_clipped.txt").write_text(
            "0\n0\n", encoding='utf-8', newline='\n'  # 削波标志错误
        )

        result = verify_mixer_rtl(self.rtl_dir, self.ref_dir, tolerance=0)
        self.assertFalse(result)

    def test_length_mismatch(self):
        """长度不一致"""
        (self.ref_dir / "mixer_outputs.txt").write_text(
            "000000\n7FFFFF\n800000\n", encoding='utf-8', newline='\n'
        )
        (self.ref_dir / "mixer_clipped.txt").write_text(
            "0\n1\n1\n", encoding='utf-8', newline='\n'
        )

        (self.rtl_dir / "mixer_rtl_outputs.txt").write_text(
            "000000\n7FFFFF\n", encoding='utf-8', newline='\n'  # 少一个样本
        )
        (self.rtl_dir / "mixer_rtl_clipped.txt").write_text(
            "0\n1\n", encoding='utf-8', newline='\n'
        )

        result = verify_mixer_rtl(self.rtl_dir, self.ref_dir, tolerance=0)
        self.assertFalse(result)

    def test_missing_file(self):
        """缺少文件"""
        (self.ref_dir / "mixer_outputs.txt").write_text(
            "000000\n", encoding='utf-8', newline='\n'
        )
        (self.ref_dir / "mixer_clipped.txt").write_text(
            "0\n", encoding='utf-8', newline='\n'
        )
        # 不创建RTL文件

        result = verify_mixer_rtl(self.rtl_dir, self.ref_dir, tolerance=0)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
