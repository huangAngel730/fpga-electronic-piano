#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T052 复音数自证测试模式参考生成器

生成测试模式下的参考输出，用于：
1. 计算各测试频率的FCW
2. 生成4路混音的参考PCM输出
3. 生成参考频谱图
4. 输出WAV文件供人耳/工具验证

对应任务：T052 复音数自证测试模式（P0优先级）
主负责人：M1
"""

import sys
from pathlib import Path
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audio_defs import SAMPLE_RATE_HZ, PCM_BITS, PCM_MAX, PCM_MIN
from dds_model import freq_to_fcw, fcw_to_freq, WavetableOscillator, make_wavetable, render_pcm24
from mixer import mix_voices

# 测试模式参数
TEST_FREQUENCIES = [200, 400, 600, 800]  # Hz，4复音示例
DURATION_SECONDS = 2.0  # 生成2秒音频


def calculate_test_fcws():
    """计算所有测试频率的FCW"""
    print("=" * 70)
    print("T052 测试模式 FCW 计算结果")
    print("=" * 70)
    print(f"采样率: {SAMPLE_RATE_HZ} Hz")
    print(f"复音数: {len(TEST_FREQUENCIES)}")
    print()

    results = []
    for i, freq in enumerate(TEST_FREQUENCIES):
        fcw = freq_to_fcw(freq, SAMPLE_RATE_HZ)
        actual_freq = fcw_to_freq(fcw, SAMPLE_RATE_HZ)
        error_hz = actual_freq - freq
        error_ppm = (error_hz / freq) * 1e6

        result = {
            'voice': i,
            'target_freq': freq,
            'fcw': fcw,
            'actual_freq': actual_freq,
            'error_hz': error_hz,
            'error_ppm': error_ppm
        }
        results.append(result)

        print(f"声部{i}: {freq:4} Hz")
        print(f"  FCW (hex) : 0x{fcw:08x}")
        print(f"  FCW (dec) : {fcw:10}")
        print(f"  实际频率  : {actual_freq:.6f} Hz")
        print(f"  误差      : {error_hz:+.6f} Hz ({error_ppm:+.3f} ppm)")
        print()

    return results


def generate_mixed_pcm(fcw_results, duration_sec):
    """生成4路混音的PCM输出"""
    print("=" * 70)
    print("生成混音PCM")
    print("=" * 70)

    num_samples = int(SAMPLE_RATE_HZ * duration_sec)
    print(f"样本数: {num_samples} ({duration_sec} 秒)")
    print()

    # 创建振荡器（使用8192幅度波表）
    sine_table = make_wavetable('sine', 1024, 8192)
    oscillators = []
    for result in fcw_results:
        osc = WavetableOscillator(table=sine_table, fcw=result['fcw'])
        oscillators.append(osc)

    # 生成混音样本
    mixed_samples = []
    for _ in range(num_samples):
        # 4路DDS输出（16位波表样本）
        voices = [osc.step() << 8 for osc in oscillators]
        # 使用混音器（26位累加+饱和限幅）
        mixed, clipped = mix_voices(voices)
        mixed_samples.append(mixed)

    # 统计
    max_val = max(mixed_samples)
    min_val = min(mixed_samples)
    print(f"PCM范围: [{min_val}, {max_val}]")
    print(f"理论最大: [{PCM_MIN}, {PCM_MAX}]")

    headroom_db = 20 * np.log10(PCM_MAX / max(abs(max_val), abs(min_val)))
    print(f"余量: {headroom_db:.2f} dB")
    print()

    return mixed_samples


def save_hex_output(samples, output_path):
    """保存为hex格式（供RTL对比）"""
    lines = []
    for sample in samples:
        # 24位有符号转为无符号表示
        if sample < 0:
            unsigned = (1 << PCM_BITS) + sample
        else:
            unsigned = sample
        lines.append(f"{unsigned:06x}")

    output_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"已保存hex文件: {output_path} ({len(lines)} 行)")


def save_wav_output(samples, output_path):
    """保存为WAV文件（供音频工具分析）"""
    try:
        import wave
        import struct
    except ImportError:
        print("警告: 无法导入wave模块，跳过WAV生成")
        return

    # 转换为16位PCM（大多数工具支持更好）
    samples_16bit = [int(s / 256) for s in samples]  # 24bit -> 16bit

    with wave.open(str(output_path), 'w') as wav_file:
        wav_file.setnchannels(1)  # 单声道
        wav_file.setsampwidth(2)  # 16位
        wav_file.setframerate(SAMPLE_RATE_HZ)

        # 写入样本
        for sample in samples_16bit:
            wav_file.writeframes(struct.pack('<h', sample))

    print(f"已保存WAV文件: {output_path}")


def generate_spectrum_plot(samples, fcw_results, output_path):
    """生成频谱图"""
    try:
        import matplotlib
        matplotlib.use('Agg')  # 非交互后端
        import matplotlib.pyplot as plt
    except ImportError:
        print("警告: 无法导入matplotlib，跳过频谱图生成")
        return

    # FFT分析
    fft_result = np.fft.rfft(samples)
    fft_freq = np.fft.rfftfreq(len(samples), 1/SAMPLE_RATE_HZ)
    fft_mag_db = 20 * np.log10(np.abs(fft_result) + 1e-10)

    # 绘图
    plt.figure(figsize=(14, 8))

    # 频谱图
    plt.subplot(2, 1, 1)
    mask = fft_freq <= 1000  # 只显示0-1000Hz
    plt.plot(fft_freq[mask], fft_mag_db[mask], linewidth=0.5)
    plt.xlabel('Frequency (Hz)')
    plt.ylabel('Magnitude (dB)')
    plt.title(f'T052 Test Mode Spectrum - {len(fcw_results)} Voices')
    plt.grid(True, alpha=0.3)

    # 标记目标频率
    for result in fcw_results:
        freq = result['actual_freq']
        plt.axvline(freq, color='r', linestyle='--', alpha=0.7, linewidth=1)
        plt.text(freq, plt.ylim()[1] - 10, f"{freq:.1f}Hz",
                 rotation=90, va='top', ha='right', fontsize=8)

    # 时域波形（前100ms）
    plt.subplot(2, 1, 2)
    display_samples = int(0.1 * SAMPLE_RATE_HZ)  # 100ms
    time_axis = np.arange(display_samples) / SAMPLE_RATE_HZ * 1000  # 转为毫秒
    plt.plot(time_axis, samples[:display_samples])
    plt.xlabel('Time (ms)')
    plt.ylabel('Amplitude')
    plt.title('Mixed Waveform (first 100ms)')
    plt.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"已保存频谱图: {output_path}")


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("T052 复音数自证测试模式 - 参考生成器")
    print("=" * 70)
    print()

    # 输出目录
    output_dir = SCRIPT_DIR / "generated" / "test_mode"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 步骤1: 计算FCW
    fcw_results = calculate_test_fcws()

    # 步骤2: 生成混音PCM
    mixed_samples = generate_mixed_pcm(fcw_results, DURATION_SECONDS)

    # 步骤3: 保存输出
    print("=" * 70)
    print("保存输出文件")
    print("=" * 70)

    # Hex格式（供RTL对比）
    hex_path = output_dir / "test_mode_4voice_48k.hex"
    save_hex_output(mixed_samples, hex_path)

    # WAV格式（供音频工具）
    wav_path = output_dir / "test_mode_4voice_48k.wav"
    save_wav_output(mixed_samples, wav_path)

    # 频谱图
    spectrum_path = output_dir / "test_mode_spectrum_4voice.png"
    generate_spectrum_plot(mixed_samples, fcw_results, spectrum_path)

    # 步骤4: 生成SystemVerilog参数
    print()
    print("=" * 70)
    print("SystemVerilog 参数（供M2使用）")
    print("=" * 70)
    print()
    print("// T052 测试模式频率控制字")
    for result in fcw_results:
        voice = result['voice']
        fcw = result['fcw']
        freq = result['target_freq']
        print(f"parameter logic [31:0] TEST_FCW_{voice} = 32'h{fcw:08x};  "
              f"// {freq} Hz (实际 {result['actual_freq']:.3f} Hz)")

    print()
    print("=" * 70)
    print("完成！")
    print("=" * 70)
    print()
    print(f"输出目录: {output_dir}")
    print(f"  - {hex_path.name}")
    print(f"  - {wav_path.name}")
    print(f"  - {spectrum_path.name}")
    print()
    print("下一步: 查看频谱图，确认4个峰清晰可见，然后将FCW参数提供给M2")

    return 0


if __name__ == "__main__":
    sys.exit(main())
