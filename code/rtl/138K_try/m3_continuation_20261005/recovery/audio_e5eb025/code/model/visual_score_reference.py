"""
visual_score_reference.py

下落音符曲谱时间轴的离线参考模型

功能：
- 定义钢琴滑块游戏式下落音符的时间轴模型
- 计算音符预告、到达判定线、命中/未命中的预期值
- 支持同音重复、和弦、休止、Note Off、速度变化和重置

约束：
- 本模型只负责视觉预告逻辑，不触发音频
- 音频由 FPGA 根据真实演奏事件实时合成
- 模型优先保存时间，像素坐标由参数计算

作者：M1
任务：T0xx 双模式可视化 - 下落音符曲谱时间轴
日期：2026-09-27
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum
import copy


class EventType(Enum):
    """音符事件类型"""
    NOTE_ON = 0
    NOTE_OFF = 1
    TEMPO_CHANGE = 2
    RESET = 3


@dataclass
class ScoreNote:
    """
    曲谱音符定义

    Attributes:
        note_id: 音符唯一标识（用于区分同音重复）
        note_number: MIDI 音符号 (0-127)
        hit_time: 预定演奏时刻（秒），音符应到达判定线的时间
        duration: 音符持续时间（秒），None 表示只有 Note On 无 Note Off
        velocity: 力度 (0-1023)，10位线性强度
    """
    note_id: int
    note_number: int
    hit_time: float
    duration: Optional[float] = None
    velocity: int = 512  # 默认中等力度


@dataclass
class TempoChange:
    """
    速度变化事件

    Attributes:
        time: 发生时刻（秒）
        bpm: 新的速度（拍/分钟）
    """
    time: float
    bpm: float


@dataclass
class VisualEvent:
    """
    视觉事件（预告、到达、消失）

    Attributes:
        event_type: 事件类型字符串 ('appear', 'arrive', 'disappear')
        time: 事件发生时刻（秒）
        note_id: 关联的音符ID
        note_number: MIDI 音符号
        y_position: 相对于判定线的位置（像素），判定线为0，向上为正
    """
    event_type: str
    time: float
    note_id: int
    note_number: int
    y_position: float


@dataclass
class HitJudgement:
    """
    命中判定结果

    Attributes:
        note_id: 音符ID
        note_number: MIDI 音符号
        expected_time: 预期命中时间（秒）
        actual_time: 实际按键时间（秒）
        time_error: 时间误差（毫秒），正值表示晚了
        is_hit: 是否命中（在时间窗口内）
    """
    note_id: int
    note_number: int
    expected_time: float
    actual_time: float
    time_error: float
    is_hit: bool


class VisualScoreReference:
    """
    视觉曲谱参考模型

    提供离线计算的可重复预期值，用于验收视觉系统实现
    """

    def __init__(
        self,
        preview_time: float = 2.0,
        screen_height: float = 400.0,
        hit_window_ms: float = 100.0,
        note_linger_time: float = 0.5
    ):
        """
        初始化参考模型

        Args:
            preview_time: 音符提前出现时间（秒），样例值 2.0
            screen_height: 从屏幕顶部到判定线的距离（像素），样例值 400.0
            hit_window_ms: 命中判定时间窗口（毫秒），样例值 ±100ms
            note_linger_time: duration=None 的音符在判定线停留时间（秒），默认 0.5
        """
        self.preview_time = preview_time
        self.screen_height = screen_height
        self.hit_window_ms = hit_window_ms
        self.note_linger_time = note_linger_time

        # 计算下落速度（像素/秒）
        self.fall_speed = screen_height / preview_time

        # 曲谱数据
        self.notes: List[ScoreNote] = []
        self.tempo_changes: List[TempoChange] = []

    def add_note(
        self,
        note_id: int,
        note_number: int,
        hit_time: float,
        duration: Optional[float] = None,
        velocity: int = 512
    ):
        """
        添加音符到曲谱

        Args:
            note_id: 音符唯一标识
            note_number: MIDI 音符号
            hit_time: 预定到达判定线的时间（秒）
            duration: 持续时间（秒），None 表示无 Note Off
            velocity: 力度 (0-1023)
        """
        note = ScoreNote(
            note_id=note_id,
            note_number=note_number,
            hit_time=hit_time,
            duration=duration,
            velocity=velocity
        )
        self.notes.append(note)

    def add_tempo_change(self, time: float, bpm: float):
        """
        添加速度变化事件

        Args:
            time: 发生时刻（秒）
            bpm: 新的速度（拍/分钟）
        """
        tempo = TempoChange(time=time, bpm=bpm)
        self.tempo_changes.append(tempo)

    def get_y_position(self, current_time: float, hit_time: float) -> float:
        """
        计算音符在当前时刻的 Y 坐标

        Args:
            current_time: 当前时刻（秒）
            hit_time: 音符预定到达时间（秒）

        Returns:
            相对于判定线的位置（像素），判定线为0，向上为正
        """
        time_until_hit = hit_time - current_time
        y_position = time_until_hit * self.fall_speed
        return y_position

    def generate_visual_events(self) -> List[VisualEvent]:
        """
        生成所有视觉事件（预告、到达、消失）

        消失规则：
        - 有 duration: 在 hit_time + duration 时消失
        - 无 duration (None): 在 hit_time + note_linger_time 时消失

        Returns:
            按时间排序的视觉事件列表
        """
        events = []

        for note in self.notes:
            # 预告事件：音符出现在屏幕顶部
            appear_time = note.hit_time - self.preview_time
            events.append(VisualEvent(
                event_type='appear',
                time=appear_time,
                note_id=note.note_id,
                note_number=note.note_number,
                y_position=self.screen_height
            ))

            # 到达事件：音符到达判定线
            events.append(VisualEvent(
                event_type='arrive',
                time=note.hit_time,
                note_id=note.note_id,
                note_number=note.note_number,
                y_position=0.0
            ))

            # 消失事件
            if note.duration is not None:
                # 有持续时间：在 Note Off 时消失
                disappear_time = note.hit_time + note.duration
            else:
                # 无持续时间：在判定线停留 note_linger_time 后消失
                disappear_time = note.hit_time + self.note_linger_time

            events.append(VisualEvent(
                event_type='disappear',
                time=disappear_time,
                note_id=note.note_id,
                note_number=note.note_number,
                y_position=0.0  # 已经在判定线上
            ))

        # 按时间、note_id、事件类型排序，确保顺序稳定
        events.sort(key=lambda e: (e.time, e.note_id, e.event_type))

        return events

    def judge_hit(
        self,
        note_id: int,
        actual_time: float
    ) -> Optional[HitJudgement]:
        """
        判定单个音符的命中情况

        Args:
            note_id: 要判定的音符ID
            actual_time: 实际按键时间（秒）

        Returns:
            命中判定结果，如果音符ID不存在则返回 None
        """
        # 查找音符
        note = None
        for n in self.notes:
            if n.note_id == note_id:
                note = n
                break

        if note is None:
            return None

        # 计算时间误差（毫秒）
        time_error_ms = (actual_time - note.hit_time) * 1000.0

        # 判定是否在窗口内
        is_hit = abs(time_error_ms) <= self.hit_window_ms

        return HitJudgement(
            note_id=note.note_id,
            note_number=note.note_number,
            expected_time=note.hit_time,
            actual_time=actual_time,
            time_error=time_error_ms,
            is_hit=is_hit
        )

    def judge_performance(
        self,
        performance_events: List[Tuple[int, float]],
        song_start_time: float = 0.0
    ) -> Dict:
        """
        判定一组演奏事件

        一对一匹配规则：
        - 一次真实 Note On 最多命中一个曲谱音符
        - 同一曲谱音符不能被重复命中
        - 窗口内最接近的匹配优先
        - 未按音符在 hit_time + hit_window 后转为 Miss
        - 窗口外误按记录为 extra_press

        Args:
            performance_events: 演奏事件列表，每项为 (note_number, time)
            song_start_time: 曲目起点时间（秒），用于统一 hit_time 与真实按键时间基准

        Returns:
            字典包含：
            - judgements: 所有曲谱音符的判定结果列表
            - extra_presses: 窗口外的误按列表，每项为 (note_number, time)
        """
        judgements = []
        used_events = set()
        extra_presses = []

        # 为每个曲谱音符找最接近的演奏事件
        for note in self.notes:
            best_match = None
            best_error = float('inf')
            best_idx = None

            # 计算该音符的绝对判定时间
            absolute_hit_time = song_start_time + note.hit_time
            window_sec = self.hit_window_ms / 1000.0

            for idx, (perf_note, perf_time) in enumerate(performance_events):
                # 只匹配相同音高且未被使用的事件
                if perf_note != note.note_number or idx in used_events:
                    continue

                error = abs(perf_time - absolute_hit_time)

                # 只考虑在时间窗口内的事件
                if error <= window_sec and error < best_error:
                    best_error = error
                    best_match = perf_time
                    best_idx = idx

            if best_match is not None:
                used_events.add(best_idx)
                # 使用相对时间计算判定
                judgement = HitJudgement(
                    note_id=note.note_id,
                    note_number=note.note_number,
                    expected_time=absolute_hit_time,
                    actual_time=best_match,
                    time_error=(best_match - absolute_hit_time) * 1000.0,
                    is_hit=True
                )
            else:
                # 未找到匹配的演奏事件，记为 Miss
                judgement = HitJudgement(
                    note_id=note.note_id,
                    note_number=note.note_number,
                    expected_time=absolute_hit_time,
                    actual_time=float('nan'),
                    time_error=float('inf'),
                    is_hit=False
                )

            judgements.append(judgement)

        # 记录未被匹配的演奏事件为误按
        for idx, (perf_note, perf_time) in enumerate(performance_events):
            if idx not in used_events:
                extra_presses.append((perf_note, perf_time))

        return {
            'judgements': judgements,
            'extra_presses': extra_presses
        }

    def get_notes_at_time(self, time: float) -> List[Dict]:
        """
        获取某时刻所有可见音符的状态

        可见性规则：
        - 在预告时间前不可见
        - 有 duration: 在 hit_time + duration 后不可见
        - 无 duration: 在 hit_time + note_linger_time 后不可见

        Args:
            time: 查询时刻（秒）

        Returns:
            可见音符列表，每项包含 note_id, note_number, y_position, is_active
        """
        visible_notes = []

        for note in self.notes:
            # 音符在预告时间前不可见
            if time < note.hit_time - self.preview_time:
                continue

            # 计算消失时间
            if note.duration is not None:
                disappear_time = note.hit_time + note.duration
            else:
                disappear_time = note.hit_time + self.note_linger_time

            # 消失后不可见
            if time > disappear_time:
                continue

            # 计算位置
            y_pos = self.get_y_position(time, note.hit_time)

            # 判断是否还在激活状态（到达判定线后且未消失）
            is_active = (time >= note.hit_time and time <= disappear_time)

            visible_notes.append({
                'note_id': note.note_id,
                'note_number': note.note_number,
                'y_position': y_pos,
                'is_active': is_active,
                'velocity': note.velocity
            })

        return visible_notes

    def clear(self):
        """清空所有曲谱数据（重置）"""
        self.notes.clear()
        self.tempo_changes.clear()
