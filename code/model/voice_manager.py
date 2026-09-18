#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""声部管理器 - Python参考实现（T010）"""

from typing import Optional, List, Tuple


class VoiceAllocator:
    """4声部分配器（最旧声部偷取策略）"""

    def __init__(self, num_voices: int = 4):
        self.num_voices = num_voices
        self.voices = [None] * num_voices  # None=空闲, int=音符号
        self.timestamps = [0] * num_voices
        self.time = 0

    def note_on(self, note_number: int) -> int:
        """分配声部给新音符，返回声部索引"""
        self.time += 1

        # 1. 同音重复：先释放旧的
        for i, v in enumerate(self.voices):
            if v == note_number:
                self.voices[i] = None

        # 2. 查找空闲声部
        for i, v in enumerate(self.voices):
            if v is None:
                self.voices[i] = note_number
                self.timestamps[i] = self.time
                return i

        # 3. 无空闲，偷取最旧的
        oldest = min(range(self.num_voices), key=lambda i: self.timestamps[i])
        self.voices[oldest] = note_number
        self.timestamps[oldest] = self.time
        return oldest

    def note_off(self, note_number: int) -> int:
        """释放指定音符的声部，返回声部索引（-1表示未找到）"""
        for i, v in enumerate(self.voices):
            if v == note_number:
                self.voices[i] = None
                return i
        return -1

    def all_notes_off(self):
        """释放所有声部"""
        self.voices = [None] * self.num_voices

    def get_active_count(self) -> int:
        """返回活跃声部数"""
        return sum(1 for v in self.voices if v is not None)

    def get_voices(self) -> List[Optional[int]]:
        """返回当前声部状态"""
        return self.voices[:]


# 自检
if __name__ == "__main__":
    alloc = VoiceAllocator(4)

    # 测试1：顺序分配
    assert alloc.note_on(60) == 0  # C4 → voice 0
    assert alloc.note_on(64) == 1  # E4 → voice 1
    assert alloc.note_on(67) == 2  # G4 → voice 2
    assert alloc.get_active_count() == 3

    # 测试2：偷取
    alloc.note_on(72)  # voice 3
    assert alloc.get_active_count() == 4
    alloc.note_on(76)  # 偷取voice 0（最旧的60）
    assert alloc.voices[0] == 76

    # 测试3：释放
    alloc.note_off(64)
    assert alloc.get_active_count() == 3

    # 测试4：同音重复
    alloc.note_on(67)  # 重新触发G4
    assert alloc.get_active_count() == 3

    # 测试5：All Notes Off
    alloc.all_notes_off()
    assert alloc.get_active_count() == 0

    print("[PASS] 声部管理器自检完成")
