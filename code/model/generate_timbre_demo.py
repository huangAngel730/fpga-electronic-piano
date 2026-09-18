#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T027 第二种音色演示生成器"""

import sys
from pathlib import Path
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dds_model import WavetableOscillator, make_wavetable, freq_to_fcw, SAMPLE_RATE_HZ
from analysis_tool import pcm_to_wav, analyze_spectrum, plot_spectrum

# 生成两种音色对比
def generate_timbre_comparison():
    freq = 440.0
    duration = 1.0
    num_samples = int(SAMPLE_RATE_HZ * duration)
    fcw = freq_to_fcw(freq, SAMPLE_RATE_HZ)

    # 正弦波
    sine_table = make_wavetable('sine', 1024, 32767)
    osc_sine = WavetableOscillator(sine_table, fcw)
    pcm_sine = [osc_sine.step() << 8 for _ in range(num_samples)]

    # 锯齿波
    saw_table = make_wavetable('saw', 1024, 32767)
    osc_saw = WavetableOscillator(saw_table, fcw)
    pcm_saw = [osc_saw.step() << 8 for _ in range(num_samples)]

    # 输出
    out_dir = SCRIPT_DIR / "generated" / "timbre"
    out_dir.mkdir(parents=True, exist_ok=True)

    pcm_to_wav(pcm_sine, out_dir / "sine_440hz.wav")
    pcm_to_wav(pcm_saw, out_dir / "saw_440hz.wav")

    # 频谱对比
    try:
        import matplotlib.pyplot as plt
        freq_axis, mag_sine = analyze_spectrum(pcm_sine)
        _, mag_saw = analyze_spectrum(pcm_saw)

        plt.figure(figsize=(14, 6))
        plt.subplot(1, 2, 1)
        mask = freq_axis <= 3000
        plt.plot(freq_axis[mask], mag_sine[mask])
        plt.title('Sine Wave - 440Hz')
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Magnitude (dB)')
        plt.grid(True, alpha=0.3)

        plt.subplot(1, 2, 2)
        plt.plot(freq_axis[mask], mag_saw[mask])
        plt.title('Sawtooth Wave - 440Hz')
        plt.xlabel('Frequency (Hz)')
        plt.ylabel('Magnitude (dB)')
        plt.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(out_dir / "timbre_comparison.png", dpi=150)
        print(f"频谱对比图: {out_dir / 'timbre_comparison.png'}")
    except ImportError:
        pass

    print(f"[PASS] 音色对比已生成: {out_dir}")
    print("  - sine_440hz.wav: 正弦波参考")
    print("  - saw_440hz.wav: 锯齿波参考")

if __name__ == "__main__":
    generate_timbre_comparison()
