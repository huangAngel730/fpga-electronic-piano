#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T028 延迟效果器 - Python参考实现"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audio_defs import PCM_MAX, PCM_MIN, saturate_pcm24


class DelayEffect:
    """延迟效果器（Echo/Delay）"""

    def __init__(self, delay_samples: int, feedback: float = 0.5):
        self.buffer = [0] * delay_samples
        self.pos = 0
        self.delay_samples = delay_samples
        self.feedback = feedback

    def process(self, input_pcm: int, dry_gain: float = 0.7, wet_gain: float = 0.3) -> int:
        """处理单个样本"""
        # 读取延迟样本
        delayed = self.buffer[self.pos]

        # 混音
        output = int(input_pcm * dry_gain + delayed * wet_gain)
        output, _ = saturate_pcm24(output)

        # 写入新样本（含反馈）
        fb_signal = int(input_pcm + delayed * self.feedback)
        fb_signal, _ = saturate_pcm24(fb_signal)
        self.buffer[self.pos] = fb_signal

        # 移动指针
        self.pos = (self.pos + 1) % self.delay_samples

        return output


# 自检
if __name__ == "__main__":
    delay = DelayEffect(delay_samples=100, feedback=0.5)

    # 脉冲响应测试
    impulse = [8000000] + [0] * 500
    output = [delay.process(s, 0.7, 0.3) for s in impulse]

    # 检查是否有回声
    assert output[0] != 0, "直接输出应非零"
    assert output[100] != 0, "延迟100样本后应有回声"
    assert output[200] != 0, "反馈应产生第二次回声"

    print("[PASS] 延迟效果器自检完成")
