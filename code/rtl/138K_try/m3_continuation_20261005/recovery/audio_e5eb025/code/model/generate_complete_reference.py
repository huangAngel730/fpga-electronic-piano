#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成包含ADSR/Velocity的带帧序号完整参考向量

供RTL逐样本对比验证完整音频链路：
- DDS相位累加和波表查表
- ADSR包络调制（含Velocity响应）
- 4声部混音和饱和限幅
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


def generate_complete_reference():
    """生成完整的音频链路参考向量"""
    print("=" * 70)
    print("生成完整音频链路参考向量（含ADSR/Velocity）")
    print("=" * 70)

    # 初始化
    sine_table = make_wavetable('sine', 1024, WT_AMPLITUDE)
    oscillators = [WavetableOscillator(table=sine_table, fcw=0) for _ in range(4)]
    envelopes = [PianoADSREnvelope() for _ in range(4)]

    # 测试序列：C大调和弦演奏
    # 0ms: C4(60) velocity=768
    # 5ms: E4(64) velocity=640
    # 10ms: G4(67) velocity=512
    # 100ms: E4 Note Off
    # 200ms: C4 Note Off
    # 300ms: G4 Note Off
    events = [
        (0, 'note_on', 0, 60, 768),
        (240, 'note_on', 1, 64, 640),
        (480, 'note_on', 2, 67, 512),
        (4800, 'note_off', 1, 64, 0),
        (9600, 'note_off', 0, 60, 0),
        (14400, 'note_off', 2, 67, 0),
    ]

    num_samples = 19200  # 400ms

    output_dir = SCRIPT_DIR / "generated" / "complete_reference"
    output_dir.mkdir(parents=True, exist_ok=True)

    full_file = output_dir / "audio_chain_full.txt"
    compact_file = output_dir / "audio_chain_compact.txt"

    # 关键帧
    key_frames = [0, 1, 240, 480, 2400, 4800, 9600, 14400, 19199]

    with full_file.open('w', encoding='utf-8', newline='\n') as f_full, \
         compact_file.open('w', encoding='utf-8', newline='\n') as f_compact:

        # 文件头
        f_full.write("# 完整音频链路参考向量（含ADSR/Velocity）\n")
        f_full.write("# 事件序列: C4(vel=768) +5ms E4(640) +5ms G4(512)\n")
        f_full.write("# 格式: frame pcm_hex pcm_dec phase0 phase1 phase2 phase3 ")
        f_full.write("wt0 wt1 wt2 wt3 env0 env1 env2 env3 ")
        f_full.write("voice0 voice1 voice2 voice3 clipped\n")
        f_full.write("#\n")

        f_compact.write("# 精简参考向量（关键帧）\n")
        f_compact.write("# frame pcm_hex pcm_dec env0 env1 env2 env3\n")
        f_compact.write("#\n")

        event_idx = 0
        for frame_idx in range(num_samples):
            # 处理事件
            while event_idx < len(events) and events[event_idx][0] == frame_idx:
                _, event_type, slot, note, velocity = events[event_idx]

                if event_type == 'note_on':
                    fcw = midi_note_to_fcw(note)
                    oscillators[slot].set_fcw(fcw)
                    envelopes[slot].note_on(velocity)
                else:
                    envelopes[slot].note_off()

                event_idx += 1

            # 生成4个声部
            phases = []
            wt_samples = []
            env_levels = []
            voices = []

            for slot in range(4):
                # DDS
                phase = oscillators[slot].phase
                wt_sample = oscillators[slot].step()

                # ADSR
                env_level = envelopes[slot].step()

                # 应用包络
                modulated = apply_envelope(wt_sample, env_level)
                # 左移8位到24位PCM
                voice_pcm = modulated << 8

                phases.append(phase)
                wt_samples.append(wt_sample)
                env_levels.append(env_level)
                voices.append(voice_pcm)

            # 混音
            mixed_pcm, clipped = mix_voices(voices)

            # 转为无符号hex
            if mixed_pcm < 0:
                pcm_unsigned = (1 << PCM_BITS) + mixed_pcm
            else:
                pcm_unsigned = mixed_pcm

            # 完整文件
            f_full.write(f"{frame_idx:6d} {pcm_unsigned:06x} {mixed_pcm:8d} ")
            f_full.write(f"{phases[0]:08x} {phases[1]:08x} {phases[2]:08x} {phases[3]:08x} ")
            f_full.write(f"{wt_samples[0]:6d} {wt_samples[1]:6d} {wt_samples[2]:6d} {wt_samples[3]:6d} ")
            f_full.write(f"{env_levels[0]:5d} {env_levels[1]:5d} {env_levels[2]:5d} {env_levels[3]:5d} ")
            f_full.write(f"{voices[0]:8d} {voices[1]:8d} {voices[2]:8d} {voices[3]:8d} ")
            f_full.write(f"{int(clipped)}\n")

            # 精简文件（关键帧）
            if frame_idx in key_frames:
                f_compact.write(f"{frame_idx:6d} {pcm_unsigned:06x} {mixed_pcm:8d} ")
                f_compact.write(f"{env_levels[0]:5d} {env_levels[1]:5d} {env_levels[2]:5d} {env_levels[3]:5d}\n")

    print(f"已生成完整向量: {full_file}")
    print(f"已生成精简向量: {compact_file}")
    print(f"总帧数: {num_samples}")
    print(f"关键帧数: {len(key_frames)}")
    print()

    print("=" * 70)
    print("RTL验证指导")
    print("=" * 70)
    print("逐样本对比项目:")
    print("1. DDS相位累加: phase[n+1] = phase[n] + FCW")
    print("2. 波表查表: wt_sample = table[phase[31:22]]")
    print("3. ADSR包络: env_level的Attack/Decay/Sustain/Release状态")
    print("4. Velocity响应: 不同velocity的包络峰值")
    print("5. 包络调制: voice = (wt_sample * env_level) >> 15 << 8")
    print("6. 混音累加: pcm = voice0 + voice1 + voice2 + voice3")
    print("7. 饱和限幅: 超出[-8388608,8388607]时削波")
    print()
    print("关键验证点:")
    print(f"  帧0: 初始状态，所有包络IDLE")
    print(f"  帧240: E4触发，包络1 Attack开始")
    print(f"  帧480: G4触发，包络2 Attack开始")
    print(f"  帧4800: E4释放，包络1 Release开始")
    print(f"  帧9600: C4释放，包络0 Release开始")
    print(f"  帧14400: G4释放，包络2 Release开始")

    return 0


if __name__ == "__main__":
    sys.exit(generate_complete_reference())
