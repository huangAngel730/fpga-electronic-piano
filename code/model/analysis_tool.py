#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T032 波形与频谱分析工具"""

import sys
from pathlib import Path
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audio_defs import SAMPLE_RATE_HZ, PCM_BITS


def pcm_to_wav(pcm_samples, output_path, sample_rate=SAMPLE_RATE_HZ, bits=16):
    """PCM转WAV文件（简化版，单声道）"""
    import wave
    import struct

    # 24bit->16bit
    if bits == 16:
        samples_16 = [s >> 8 for s in pcm_samples]
    else:
        samples_16 = pcm_samples

    with wave.open(str(output_path), 'w') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for s in samples_16:
            wav.writeframes(struct.pack('<h', max(-32768, min(32767, s))))


def analyze_spectrum(samples, sample_rate=SAMPLE_RATE_HZ):
    """频谱分析，返回频率和幅度"""
    fft = np.fft.rfft(samples)
    freq = np.fft.rfftfreq(len(samples), 1/sample_rate)
    mag_db = 20 * np.log10(np.abs(fft) + 1e-10)
    return freq, mag_db


def plot_spectrum(freq, mag_db, output_path, title="Spectrum", max_freq=2000):
    """绘制频谱图"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib未安装，跳过绘图")
        return

    plt.figure(figsize=(12, 6))
    mask = freq <= max_freq
    plt.plot(freq[mask], mag_db[mask])
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude (dB)')
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.savefig(output_path, dpi=150)
    plt.close()


if __name__ == "__main__":
    # 测试：生成440Hz正弦波
    t = np.arange(4800) / SAMPLE_RATE_HZ
    sine = np.sin(2 * np.pi * 440 * t)
    pcm = (sine * 8388352).astype(int)

    out_dir = SCRIPT_DIR / "generated" / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    pcm_to_wav(pcm, out_dir / "test_440hz.wav")
    freq, mag = analyze_spectrum(pcm)
    plot_spectrum(freq, mag, out_dir / "test_spectrum.png", "Test 440Hz")

    print(f"[PASS] 已生成测试文件: {out_dir}")
