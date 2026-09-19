#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""性能基准测试 - 测量Python模型实时性能"""

import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from dds_model import WavetableOscillator, make_wavetable, freq_to_fcw, SAMPLE_RATE_HZ
from adsr import ADSREnvelope
from mixer import mix_voices


def benchmark_dds(iterations=100000):
    """DDS性能测试"""
    sine_table = make_wavetable('sine', 1024, 32767)
    fcw = freq_to_fcw(440.0, SAMPLE_RATE_HZ)
    osc = WavetableOscillator(sine_table, fcw)

    start = time.perf_counter()
    for _ in range(iterations):
        osc.step()
    elapsed = time.perf_counter() - start

    samples_per_sec = iterations / elapsed
    realtime_factor = samples_per_sec / SAMPLE_RATE_HZ

    return {
        'name': 'DDS',
        'samples': iterations,
        'time': elapsed,
        'rate': samples_per_sec,
        'realtime': realtime_factor
    }


def benchmark_adsr(iterations=100000):
    """ADSR性能测试"""
    env = ADSREnvelope()
    env.note_on()

    start = time.perf_counter()
    for _ in range(iterations):
        env.step()
    elapsed = time.perf_counter() - start

    return {
        'name': 'ADSR',
        'samples': iterations,
        'time': elapsed,
        'rate': iterations / elapsed,
        'realtime': (iterations / elapsed) / SAMPLE_RATE_HZ
    }


def benchmark_voice(iterations=100000):
    """单声部（DDS+ADSR）性能测试"""
    sine_table = make_wavetable('sine', 1024, 32767)
    fcw = freq_to_fcw(440.0, SAMPLE_RATE_HZ)
    osc = WavetableOscillator(sine_table, fcw)
    env = ADSREnvelope()
    env.note_on()

    start = time.perf_counter()
    for _ in range(iterations):
        wt = osc.step()
        e = env.step()
        result = (wt * e) >> 15
    elapsed = time.perf_counter() - start

    return {
        'name': 'Voice (DDS+ADSR)',
        'samples': iterations,
        'time': elapsed,
        'rate': iterations / elapsed,
        'realtime': (iterations / elapsed) / SAMPLE_RATE_HZ
    }


def benchmark_mixer_4voice(iterations=10000):
    """4声部混音性能测试"""
    import random

    start = time.perf_counter()
    for _ in range(iterations):
        voices = [random.randint(-8388608, 8388607) for _ in range(4)]
        mix_voices(voices)
    elapsed = time.perf_counter() - start

    return {
        'name': 'Mixer (4-voice)',
        'samples': iterations,
        'time': elapsed,
        'rate': iterations / elapsed,
        'realtime': (iterations / elapsed) / SAMPLE_RATE_HZ
    }


def run_benchmarks():
    """运行全部基准测试"""
    print("=" * 70)
    print("Python模型性能基准测试")
    print("=" * 70)
    print()

    tests = [
        benchmark_dds,
        benchmark_adsr,
        benchmark_voice,
        benchmark_mixer_4voice,
    ]

    results = []
    for test in tests:
        print(f"运行 {test.__name__}...", end=" ")
        result = test()
        results.append(result)
        print("完成")

    print()
    print("=" * 70)
    print("测试结果")
    print("=" * 70)
    print(f"{'模块':<20} {'采样率':<15} {'实时倍率':<10}")
    print("-" * 70)

    for r in results:
        print(f"{r['name']:<20} {r['rate']/1e6:>8.2f} M/s   {r['realtime']:>8.1f}x")

    print()
    print("说明：实时倍率 > 1.0 表示快于实时（可用于实时合成）")
    print(f"目标采样率：{SAMPLE_RATE_HZ/1000} kHz")


if __name__ == "__main__":
    run_benchmarks()
