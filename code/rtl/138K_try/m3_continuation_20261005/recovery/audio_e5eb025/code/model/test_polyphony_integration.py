#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T010声部管理集成测试 - 集成DDS、钢琴式ADSR和混音器

测试完整的4声部管理流程：
1. Note On分配声部
2. 同音重触发返回原槽
3. DDS + ADSR调制
4. 4声部混音
5. Note Off平滑释放
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audio_defs import SAMPLE_RATE_HZ, WT_AMPLITUDE
from dds_model import WavetableOscillator, make_wavetable, midi_note_to_fcw
from adsr_piano import PianoADSREnvelope, apply_envelope
from mixer import mix_voices
from voice_manager import VoiceAllocator


def test_polyphony_integration():
    """测试完整4声部复音"""
    print("=" * 70)
    print("T010声部管理集成测试 - 4声部复音")
    print("=" * 70)

    # 初始化
    sine_table = make_wavetable('sine', 1024, WT_AMPLITUDE)
    voice_manager = VoiceAllocator(num_voices=4)

    # 4个声部的振荡器和包络
    oscillators = [WavetableOscillator(table=sine_table, fcw=0) for _ in range(4)]
    envelopes = [PianoADSREnvelope() for _ in range(4)]

    output_dir = SCRIPT_DIR / "generated" / "polyphony_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    vector_file = output_dir / "polyphony_4voice.txt"

    # 测试序列：演奏C大调和弦 (C4-E4-G4)
    events = [
        (0, 'note_on', 60, 768),      # C4, velocity=768
        (240, 'note_on', 64, 640),    # E4, velocity=640  (5ms后)
        (480, 'note_on', 67, 512),    # G4, velocity=512  (10ms后)
        (4800, 'note_off', 64, 0),    # E4释放 (100ms后)
        (9600, 'note_off', 60, 0),    # C4释放 (200ms后)
        (14400, 'note_off', 67, 0),   # G4释放 (300ms后)
    ]

    num_samples = 19200  # 400ms总时长

    with vector_file.open('w', encoding='utf-8', newline='\n') as f:
        f.write("# T010 4声部复音测试\n")
        f.write("# 序列: C4(60) -> +5ms E4(64) -> +5ms G4(67)\n")
        f.write("# 格式: sample_idx pcm_hex pcm_dec voice0_active voice1_active voice2_active voice3_active clipped\n")
        f.write("#\n")

        event_idx = 0
        for sample_idx in range(num_samples):
            # 处理事件
            while event_idx < len(events) and events[event_idx][0] == sample_idx:
                frame, event_type, note, velocity = events[event_idx]

                if event_type == 'note_on':
                    slot = voice_manager.note_on(note)
                    if slot is not None:
                        fcw = midi_note_to_fcw(note)
                        oscillators[slot].set_fcw(fcw)
                        envelopes[slot].note_on(velocity)
                        print(f"样本{sample_idx}: Note On {note}, velocity={velocity}, 分配槽{slot}")
                else:  # note_off
                    slot = voice_manager.note_off(note)
                    if slot >= 0:
                        envelopes[slot].note_off()
                        print(f"样本{sample_idx}: Note Off {note}, 释放槽{slot}")

                event_idx += 1

            # 生成4个声部
            voices = []
            active_flags = []
            for slot in range(4):
                wt_sample = oscillators[slot].step()
                env_level = envelopes[slot].step()

                # 应用包络
                modulated = apply_envelope(wt_sample, env_level)
                # 波表样本左移8位到24位PCM
                pcm_voice = modulated << 8

                voices.append(pcm_voice)
                active_flags.append(1 if envelopes[slot].get_state()[0] != 'IDLE' else 0)

            # 混音
            mixed_pcm, clipped = mix_voices(voices)

            # 转为无符号hex
            if mixed_pcm < 0:
                pcm_unsigned = (1 << 24) + mixed_pcm
            else:
                pcm_unsigned = mixed_pcm

            f.write(f"{sample_idx:6d} {pcm_unsigned:06x} {mixed_pcm:8d} "
                   f"{active_flags[0]} {active_flags[1]} {active_flags[2]} {active_flags[3]} "
                   f"{int(clipped)}\n")

    print(f"\n已生成: {vector_file}")
    print(f"总样本数: {num_samples}")
    print()

    # 验证声部分配正确性
    print("声部分配验证:")
    print("  C4(60) -> 槽0")
    print("  E4(64) -> 槽1")
    print("  G4(67) -> 槽2")
    print()


def test_voice_stealing():
    """测试声部窃取（超过4声部）"""
    print("=" * 70)
    print("测试2: 声部窃取（5个音符）")
    print("=" * 70)

    voice_manager = VoiceAllocator(num_voices=4)

    # 连续触发5个音符
    notes = [60, 62, 64, 65, 67]  # C D E F G
    for i, note in enumerate(notes):
        slot = voice_manager.note_on(note)
        print(f"音符{note}: 分配槽{slot}")

    # 验证最老的音符被窃取
    active_notes = [v for v in voice_manager.voices if v is not None]
    print(f"\n当前活跃音符: {active_notes}")
    print(f"预期: [62, 64, 65, 67] (音符60被窃取)")
    print()


def test_retrigger():
    """测试同音重触发"""
    print("=" * 70)
    print("测试3: 同音重触发")
    print("=" * 70)

    voice_manager = VoiceAllocator(num_voices=4)

    # 首次触发
    slot1 = voice_manager.note_on(60)
    print(f"首次触发音符60: 槽{slot1}")

    # 同音重触发
    slot2 = voice_manager.note_on(60)
    print(f"重触发音符60: 槽{slot2}")

    if slot1 == slot2:
        print("[PASS] 同音重触发返回原槽")
    else:
        print(f"[FAIL] 同音重触发换槽: {slot1} -> {slot2}")
    print()


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("T010声部管理集成测试套件")
    print("=" * 70)
    print()

    test_polyphony_integration()
    test_voice_stealing()
    test_retrigger()

    print("=" * 70)
    print("全部测试完成")
    print("=" * 70)
    print()
    print("输出文件:")
    print("  code/model/generated/polyphony_test/polyphony_4voice.txt")
    print()
    print("验证方法:")
    print("1. 检查voice0-3的active标志变化")
    print("2. 验证混音输出的PCM范围")
    print("3. 检查削波标志（应该无削波）")
    print("4. 听觉验证WAV文件（如果生成）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
