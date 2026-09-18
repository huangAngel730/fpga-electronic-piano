#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整4声部合成演示 - 整合DDS+ADSR+声部管理+混音"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from dds_model import WavetableOscillator, make_wavetable, freq_to_fcw, midi_note_to_fcw, SAMPLE_RATE_HZ
from adsr import ADSREnvelope
from voice_manager import VoiceAllocator
from mixer import mix_voices
from analysis_tool import pcm_to_wav


class Voice:
    """单声部：DDS + ADSR"""
    def __init__(self, wavetable):
        self.osc = WavetableOscillator(wavetable, 0)
        self.env = ADSREnvelope()
        self.active = False

    def note_on(self, note_number):
        fcw = midi_note_to_fcw(note_number, SAMPLE_RATE_HZ)
        self.osc.set_fcw(fcw)
        self.env.note_on()
        self.active = True

    def note_off(self):
        self.env.note_off()

    def step(self) -> int:
        if not self.active and self.env.state == 'IDLE':
            return 0
        wt_sample = self.osc.step()
        envelope = self.env.step()
        return (wt_sample * envelope) >> 15


def demo_polyphony():
    """演示4声部合成：C大调和弦进行"""
    # 初始化
    sine_table = make_wavetable('sine', 1024, 32767)
    voices = [Voice(sine_table) for _ in range(4)]
    allocator = VoiceAllocator(4)

    # 和弦序列：C-Am-F-G
    chords = [
        [60, 64, 67, 72],  # C major (C E G C)
        [57, 60, 64, 69],  # A minor (A C E A)
        [53, 57, 60, 65],  # F major (F A C F)
        [55, 59, 62, 67],  # G major (G B D G)
    ]

    samples = []
    t = 0
    sample_rate = SAMPLE_RATE_HZ

    for chord in chords:
        # 按下和弦
        for note in chord:
            voice_idx = allocator.note_on(note)
            voices[voice_idx].note_on(note)

        # 持续1秒
        for _ in range(sample_rate):
            voice_samples = [v.step() << 8 for v in voices]
            mixed, _ = mix_voices(voice_samples)
            samples.append(mixed)
            t += 1

        # 释放和弦
        for note in chord:
            voice_idx = allocator.note_off(note)
            if voice_idx >= 0:
                voices[voice_idx].note_off()

        # 衰减0.5秒
        for _ in range(sample_rate // 2):
            voice_samples = [v.step() << 8 for v in voices]
            mixed, _ = mix_voices(voice_samples)
            samples.append(mixed)
            t += 1

    # 输出
    out_dir = SCRIPT_DIR / "generated" / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    pcm_to_wav(samples, out_dir / "polyphony_demo.wav")

    print(f"[完成] 4声部合成演示")
    print(f"  输出: {out_dir / 'polyphony_demo.wav'}")
    print(f"  时长: {len(samples)/sample_rate:.1f}秒")
    print(f"  和弦: C-Am-F-G")


if __name__ == "__main__":
    demo_polyphony()
