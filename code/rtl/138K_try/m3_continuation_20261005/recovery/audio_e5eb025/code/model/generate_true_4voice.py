#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成真正的4声部同时活跃测试向量

确保有足够长的时间段，4个声部都处于激活状态且有非零输出。
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audio_defs import SAMPLE_RATE_HZ, PCM_BITS, WT_AMPLITUDE
from dds_model import WavetableOscillator, make_wavetable, midi_note_to_fcw
from adsr_piano import PianoADSREnvelope, apply_envelope
from mixer import mix_voices


def generate_true_4voice_test():
    """生成4声部真正同时活跃的测试向量"""
    print("=" * 70)
    print("生成4声部同时活跃测试向量")
    print("=" * 70)

    # 初始化
    sine_table = make_wavetable('sine', 1024, WT_AMPLITUDE)
    oscillators = [WavetableOscillator(table=sine_table, fcw=0) for _ in range(4)]
    envelopes = [PianoADSREnvelope() for _ in range(4)]

    output_dir = SCRIPT_DIR / "generated" / "polyphony_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 新的测试序列：4个音符快速连续触发，确保有重叠期
    # 0ms: C4(60) velocity=1023
    # 2.5ms (120样本): E4(64) velocity=896
    # 5ms (240样本): G4(67) velocity=768
    # 7.5ms (360样本): C5(72) velocity=640
    # 100ms后开始逐个释放
    events = [
        (0, 'note_on', 0, 60, 1023),
        (120, 'note_on', 1, 64, 896),
        (240, 'note_on', 2, 67, 768),
        (360, 'note_on', 3, 72, 640),
        (4800, 'note_off', 1, 64, 0),
        (9600, 'note_off', 2, 67, 0),
        (14400, 'note_off', 0, 60, 0),
        (19200, 'note_off', 3, 72, 0),
    ]

    num_samples = 24000  # 500ms

    vector_file = output_dir / "polyphony_4voice_true.txt"

    with vector_file.open('w', encoding='utf-8', newline='\n') as f:
        f.write("# 真正的4声部同时活跃测试向量\n")
        f.write("# 事件: C4(1023) +2.5ms E4(896) +2.5ms G4(768) +2.5ms C5(640)\n")
        f.write("# 从帧360开始，4声部同时活跃至帧4800\n")
        f.write("# 格式: frame pcm_hex pcm_dec voice0_active voice1_active voice2_active voice3_active clipped\n")
        f.write("#\n")

        event_idx = 0
        four_voice_count = 0

        for frame_idx in range(num_samples):
            # 处理事件
            while event_idx < len(events) and events[event_idx][0] == frame_idx:
                _, event_type, slot, note, velocity = events[event_idx]

                if event_type == 'note_on':
                    fcw = midi_note_to_fcw(note)
                    oscillators[slot].set_fcw(fcw)
                    envelopes[slot].note_on(velocity)
                    print(f"帧{frame_idx}: Note On 音符{note}, velocity={velocity}, 槽{slot}")
                else:
                    envelopes[slot].note_off()
                    print(f"帧{frame_idx}: Note Off 音符{note}, 槽{slot}")

                event_idx += 1

            # 生成4个声部
            voices = []
            active_flags = []
            for slot in range(4):
                wt_sample = oscillators[slot].step()
                env_level = envelopes[slot].step()

                # 应用包络
                modulated = apply_envelope(wt_sample, env_level)
                voice_pcm = modulated << 8

                voices.append(voice_pcm)
                is_active = 1 if envelopes[slot].get_state()[0] != 'IDLE' else 0
                active_flags.append(is_active)

            # 统计4声部同时活跃
            if sum(active_flags) == 4:
                four_voice_count += 1

            # 混音
            mixed_pcm, clipped = mix_voices(voices)

            # 转为无符号hex
            if mixed_pcm < 0:
                pcm_unsigned = (1 << PCM_BITS) + mixed_pcm
            else:
                pcm_unsigned = mixed_pcm

            f.write(f"{frame_idx:6d} {pcm_unsigned:06x} {mixed_pcm:8d} "
                   f"{active_flags[0]} {active_flags[1]} {active_flags[2]} {active_flags[3]} "
                   f"{int(clipped)}\n")

    print(f"\n已生成: {vector_file}")
    print(f"总帧数: {num_samples}")
    print(f"4声部同时活跃帧数: {four_voice_count}")
    print(f"4声部活跃比例: {four_voice_count/num_samples*100:.1f}%")

    if four_voice_count > 0:
        print(f"4声部活跃区间: 约帧360到帧4800")
        print("\n[PASS] 生成了真正的4声部同时活跃向量")
        return 0
    else:
        print("\n[FAIL] 未生成4声部同时活跃的帧")
        return 1


if __name__ == "__main__":
    sys.exit(generate_true_4voice_test())
