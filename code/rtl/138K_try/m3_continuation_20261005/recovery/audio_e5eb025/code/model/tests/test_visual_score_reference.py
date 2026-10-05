"""
test_visual_score_reference.py

视觉曲谱参考模型的自动验收测试

覆盖场景：
- 单音符预告与到达
- 同音重复（区分不同音符实例）
- 和弦（多个音符同时到达）
- 休止（音符间隔）
- Note Off（持续时间）
- 速度变化（预留接口）
- 重置（清空曲谱）
- 命中判定（Hit/Miss，时间窗口）
- 一对一匹配规则
- 窗口外误按记录

验收标准：所有测试 PASS，失败返回非零退出码

作者：M1
任务：T0xx 双模式可视化 - 下落音符曲谱时间轴
日期：2026-09-27
修订：2026-09-27（按 M2 要求修正）
"""

import sys
import os
import math

# 添加 code/model 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from visual_score_reference import (
    VisualScoreReference,
    ScoreNote,
    VisualEvent,
    HitJudgement
)


def assert_close(actual, expected, tolerance, msg):
    """浮点数接近断言"""
    if abs(actual - expected) > tolerance:
        print(f"FAIL: {msg}")
        print(f"  Expected: {expected}")
        print(f"  Actual: {actual}")
        print(f"  Error: {abs(actual - expected)}")
        raise AssertionError(msg)


def assert_equal(actual, expected, msg):
    """相等断言"""
    if actual != expected:
        print(f"FAIL: {msg}")
        print(f"  Expected: {expected}")
        print(f"  Actual: {actual}")
        raise AssertionError(msg)


def test_basic_note_preview():
    """测试1：单音符预告与到达"""
    print("测试1：单音符预告与到达...", end=" ")

    model = VisualScoreReference(
        preview_time=2.0,
        screen_height=400.0,
        hit_window_ms=100.0,
        note_linger_time=0.5
    )

    # 添加一个音符：C5(72) 在 5.0 秒到达判定线，无持续时间
    model.add_note(note_id=1, note_number=72, hit_time=5.0, velocity=512)

    # 生成视觉事件
    events = model.generate_visual_events()

    # 应该有3个事件：appear, arrive, disappear
    assert_equal(len(events), 3, "应该生成3个事件")

    # 检查 appear 事件
    appear = events[0]
    assert_equal(appear.event_type, 'appear', "第一个事件应是 appear")
    assert_close(appear.time, 3.0, 0.001, "appear 时间应为 5.0 - 2.0 = 3.0")
    assert_equal(appear.note_id, 1, "note_id 应为 1")
    assert_equal(appear.note_number, 72, "note_number 应为 72")
    assert_close(appear.y_position, 400.0, 0.001, "appear 位置应在屏幕顶部")

    # 检查 arrive 事件
    arrive = events[1]
    assert_equal(arrive.event_type, 'arrive', "第二个事件应是 arrive")
    assert_close(arrive.time, 5.0, 0.001, "arrive 时间应为 5.0")
    assert_close(arrive.y_position, 0.0, 0.001, "arrive 位置应在判定线")

    # 检查 disappear 事件
    disappear = events[2]
    assert_equal(disappear.event_type, 'disappear', "第三个事件应是 disappear")
    assert_close(disappear.time, 5.5, 0.001, "disappear 时间应为 5.0 + 0.5")

    # 检查中间时刻的位置
    y_at_4s = model.get_y_position(4.0, 5.0)
    assert_close(y_at_4s, 200.0, 0.001, "4.0秒时应在中间位置 200像素")

    print("PASS")


def test_same_note_repeat():
    """测试2：同音重复（区分音符实例）"""
    print("测试2：同音重复...", end=" ")

    model = VisualScoreReference(preview_time=2.0, screen_height=400.0, note_linger_time=0.5)

    # 添加两个相同音高的音符，不同时间
    model.add_note(note_id=1, note_number=60, hit_time=3.0)
    model.add_note(note_id=2, note_number=60, hit_time=4.0)

    events = model.generate_visual_events()

    # 应该有6个事件（每个音符3个事件）
    assert_equal(len(events), 6, "两个音符应生成6个事件")

    # 按时间顺序检查关键事件
    assert_equal(events[0].note_id, 1, "第1个事件属于音符1")
    assert_equal(events[0].event_type, 'appear', "第1个事件是 appear")
    assert_close(events[0].time, 1.0, 0.001, "音符1在1.0秒出现")

    assert_equal(events[1].note_id, 2, "第2个事件属于音符2")
    assert_equal(events[1].event_type, 'appear', "第2个事件是 appear")
    assert_close(events[1].time, 2.0, 0.001, "音符2在2.0秒出现")

    # 确认两个音符有不同的ID但相同的音高
    note_ids = [e.note_id for e in events]
    assert_equal(sorted(set(note_ids)), [1, 2], "应包含两个不同的音符ID")

    print("PASS")


def test_chord():
    """测试3：和弦（多个音符同时到达）"""
    print("测试3：和弦...", end=" ")

    model = VisualScoreReference(preview_time=2.0, screen_height=400.0)

    # C大三和弦：C(60), E(64), G(67) 同时在 5.0 秒到达
    model.add_note(note_id=1, note_number=60, hit_time=5.0)
    model.add_note(note_id=2, note_number=64, hit_time=5.0)
    model.add_note(note_id=3, note_number=67, hit_time=5.0)

    events = model.generate_visual_events()

    # 3个音符，每个3个事件 = 9个事件
    assert_equal(len(events), 9, "和弦应生成9个事件")

    # 检查所有 appear 事件时间相同
    appear_events = [e for e in events if e.event_type == 'appear']
    assert_equal(len(appear_events), 3, "应有3个 appear 事件")
    for e in appear_events:
        assert_close(e.time, 3.0, 0.001, "所有音符应同时出现")

    # 检查所有 arrive 事件时间相同
    arrive_events = [e for e in events if e.event_type == 'arrive']
    assert_equal(len(arrive_events), 3, "应有3个 arrive 事件")
    for e in arrive_events:
        assert_close(e.time, 5.0, 0.001, "所有音符应同时到达")

    # 检查音符号不同
    note_numbers = sorted([e.note_number for e in arrive_events])
    assert_equal(note_numbers, [60, 64, 67], "应包含三个不同音符")

    print("PASS")


def test_rest():
    """测试4：休止（音符间隔）"""
    print("测试4：休止...", end=" ")

    model = VisualScoreReference(preview_time=2.0, screen_height=400.0)

    # 两个音符，中间有休止
    model.add_note(note_id=1, note_number=60, hit_time=3.0)
    model.add_note(note_id=2, note_number=62, hit_time=6.0)  # 3秒间隔

    # 在 4.0 秒时查询可见音符
    visible_at_4s = model.get_notes_at_time(4.0)

    # 检查音符2的位置
    y_note2 = model.get_y_position(4.0, 6.0)
    assert_close(y_note2, 400.0, 0.001, "音符2在4.0秒时应刚出现在顶部")

    print("PASS")


def test_note_off():
    """测试5：Note Off（持续时间）"""
    print("测试5：Note Off...", end=" ")

    model = VisualScoreReference(preview_time=2.0, screen_height=400.0)

    # 添加一个有持续时间的音符
    model.add_note(note_id=1, note_number=60, hit_time=5.0, duration=2.0)

    events = model.generate_visual_events()

    # 应该有3个事件：appear, arrive, disappear
    assert_equal(len(events), 3, "有持续时间的音符应生成3个事件")

    # 检查事件类型顺序
    assert_equal(events[0].event_type, 'appear', "第1个事件应是 appear")
    assert_equal(events[1].event_type, 'arrive', "第2个事件应是 arrive")
    assert_equal(events[2].event_type, 'disappear', "第3个事件应是 disappear")

    # 检查 disappear 时间
    assert_close(events[2].time, 7.0, 0.001, "disappear 应在 5.0 + 2.0 = 7.0")

    # 检查在持续期间音符可见
    visible_at_6s = model.get_notes_at_time(6.0)
    assert_equal(len(visible_at_6s), 1, "6.0秒时音符应可见")
    assert_equal(visible_at_6s[0]['is_active'], True, "音符应处于激活状态")

    # 检查在 Note Off 后音符不可见
    visible_at_8s = model.get_notes_at_time(8.0)
    assert_equal(len(visible_at_8s), 0, "8.0秒时音符应已消失")

    print("PASS")


def test_reset():
    """测试6：重置（清空曲谱）"""
    print("测试6：重置...", end=" ")

    model = VisualScoreReference()

    # 添加一些音符
    model.add_note(note_id=1, note_number=60, hit_time=3.0)
    model.add_note(note_id=2, note_number=62, hit_time=4.0)
    model.add_tempo_change(2.0, 120.0)

    # 检查曲谱不为空
    assert_equal(len(model.notes), 2, "应有2个音符")
    assert_equal(len(model.tempo_changes), 1, "应有1个速度变化")

    # 重置
    model.clear()

    # 检查曲谱为空
    assert_equal(len(model.notes), 0, "重置后应无音符")
    assert_equal(len(model.tempo_changes), 0, "重置后应无速度变化")

    events = model.generate_visual_events()
    assert_equal(len(events), 0, "重置后应无视觉事件")

    print("PASS")


def test_hit_judgement_perfect():
    """测试7：命中判定 - 完美命中"""
    print("测试7：命中判定 - 完美命中...", end=" ")

    model = VisualScoreReference(hit_window_ms=100.0)

    # 添加音符在 5.0 秒
    model.add_note(note_id=1, note_number=60, hit_time=5.0)

    # 完美命中（误差 0ms）
    judgement = model.judge_hit(note_id=1, actual_time=5.0)

    assert_equal(judgement.is_hit, True, "应判定为命中")
    assert_close(judgement.time_error, 0.0, 0.001, "时间误差应为 0ms")
    assert_equal(judgement.note_number, 60, "音符号应为 60")

    print("PASS")


def test_hit_judgement_early():
    """测试8：命中判定 - 提前命中"""
    print("测试8：命中判定 - 提前命中...", end=" ")

    model = VisualScoreReference(hit_window_ms=100.0)
    model.add_note(note_id=1, note_number=60, hit_time=5.0)

    # 提前 50ms（在窗口内）
    judgement = model.judge_hit(note_id=1, actual_time=4.95)

    assert_equal(judgement.is_hit, True, "50ms 误差应命中")
    assert_close(judgement.time_error, -50.0, 0.1, "时间误差应为 -50ms")

    print("PASS")


def test_hit_judgement_late():
    """测试9：命中判定 - 延迟命中"""
    print("测试9：命中判定 - 延迟命中...", end=" ")

    model = VisualScoreReference(hit_window_ms=100.0)
    model.add_note(note_id=1, note_number=60, hit_time=5.0)

    # 延迟 80ms（在窗口内）
    judgement = model.judge_hit(note_id=1, actual_time=5.08)

    assert_equal(judgement.is_hit, True, "80ms 误差应命中")
    assert_close(judgement.time_error, 80.0, 0.1, "时间误差应为 +80ms")

    print("PASS")


def test_hit_judgement_miss():
    """测试10：命中判定 - 未命中"""
    print("测试10：命中判定 - 未命中...", end=" ")

    model = VisualScoreReference(hit_window_ms=100.0)
    model.add_note(note_id=1, note_number=60, hit_time=5.0)

    # 延迟 150ms（超出窗口）
    judgement = model.judge_hit(note_id=1, actual_time=5.15)

    assert_equal(judgement.is_hit, False, "150ms 误差应未命中")
    assert_close(judgement.time_error, 150.0, 0.1, "时间误差应为 +150ms")

    print("PASS")


def test_performance_judgement():
    """测试11：演奏判定 - 多音符匹配"""
    print("测试11：演奏判定 - 多音符匹配...", end=" ")

    model = VisualScoreReference(hit_window_ms=100.0)

    # 曲谱：3个音符
    model.add_note(note_id=1, note_number=60, hit_time=3.0)
    model.add_note(note_id=2, note_number=64, hit_time=3.0)  # 和弦
    model.add_note(note_id=3, note_number=67, hit_time=4.0)

    # 模拟演奏：(note_number, time)
    performance = [
        (60, 2.98),   # 提前 20ms
        (64, 3.05),   # 延迟 50ms
        (67, 4.12),   # 延迟 120ms，超出窗口
    ]

    result = model.judge_performance(performance, song_start_time=0.0)
    judgements = result['judgements']
    extra_presses = result['extra_presses']

    # 检查结果
    assert_equal(len(judgements), 3, "应有3个判定结果")

    # 音符1：命中
    assert_equal(judgements[0].note_id, 1, "第1个判定对应音符1")
    assert_equal(judgements[0].is_hit, True, "音符1应命中")
    assert_close(judgements[0].time_error, -20.0, 1.0, "音符1提前20ms")

    # 音符2：命中
    assert_equal(judgements[1].note_id, 2, "第2个判定对应音符2")
    assert_equal(judgements[1].is_hit, True, "音符2应命中")
    assert_close(judgements[1].time_error, 50.0, 1.0, "音符2延迟50ms")

    # 音符3：未命中（超出窗口）
    assert_equal(judgements[2].note_id, 3, "第3个判定对应音符3")
    assert_equal(judgements[2].is_hit, False, "音符3应未命中")
    assert_equal(math.isnan(judgements[2].actual_time), True, "音符3无有效按键时间")

    # 窗口外的按键被记录为误按
    assert_equal(len(extra_presses), 1, "应有1个误按（窗口外的67）")
    assert_equal(extra_presses[0], (67, 4.12), "67在4.12秒的按键超出窗口")

    print("PASS")


def test_performance_miss_note():
    """测试12：演奏判定 - 漏按音符"""
    print("测试12：演奏判定 - 漏按音符...", end=" ")

    model = VisualScoreReference(hit_window_ms=100.0)

    # 曲谱：2个音符
    model.add_note(note_id=1, note_number=60, hit_time=3.0)
    model.add_note(note_id=2, note_number=62, hit_time=4.0)

    # 演奏：只按了第1个
    performance = [(60, 3.0)]

    result = model.judge_performance(performance, song_start_time=0.0)
    judgements = result['judgements']
    extra_presses = result['extra_presses']

    # 应该有2个判定，第2个为 Miss
    assert_equal(len(judgements), 2, "应有2个判定结果")
    assert_equal(judgements[0].is_hit, True, "音符1应命中")
    assert_equal(judgements[1].is_hit, False, "音符2应未命中（漏按）")
    assert_equal(math.isnan(judgements[1].actual_time), True, "漏按音符的实际时间应为 NaN")
    assert_equal(len(extra_presses), 0, "应无误按")

    print("PASS")


def test_extra_presses():
    """测试13：窗口外误按"""
    print("测试13：窗口外误按...", end=" ")

    model = VisualScoreReference(hit_window_ms=100.0)

    # 曲谱：1个音符
    model.add_note(note_id=1, note_number=60, hit_time=3.0)

    # 演奏：正确按键 + 2个误按
    performance = [
        (60, 3.0),   # 正确
        (62, 3.5),   # 误按：不在曲谱中
        (64, 5.0),   # 误按：不在曲谱中
    ]

    result = model.judge_performance(performance, song_start_time=0.0)
    judgements = result['judgements']
    extra_presses = result['extra_presses']

    # 检查判定结果
    assert_equal(len(judgements), 1, "应有1个曲谱音符判定")
    assert_equal(judgements[0].is_hit, True, "音符1应命中")

    # 检查误按
    assert_equal(len(extra_presses), 2, "应有2个误按")
    assert_equal(extra_presses[0], (62, 3.5), "第1个误按")
    assert_equal(extra_presses[1], (64, 5.0), "第2个误按")

    print("PASS")


def test_same_note_one_to_one():
    """测试14：同音重复一对一匹配"""
    print("测试14：同音重复一对一匹配...", end=" ")

    model = VisualScoreReference(hit_window_ms=100.0)

    # 曲谱：同音3次
    model.add_note(note_id=1, note_number=60, hit_time=3.0)
    model.add_note(note_id=2, note_number=60, hit_time=4.0)
    model.add_note(note_id=3, note_number=60, hit_time=5.0)

    # 演奏：只按了2次
    performance = [
        (60, 3.02),  # 对应音符1
        (60, 4.05),  # 对应音符2
    ]

    result = model.judge_performance(performance, song_start_time=0.0)
    judgements = result['judgements']

    # 检查一对一匹配
    assert_equal(len(judgements), 3, "应有3个判定结果")
    assert_equal(judgements[0].is_hit, True, "音符1应命中")
    assert_equal(judgements[1].is_hit, True, "音符2应命中")
    assert_equal(judgements[2].is_hit, False, "音符3应未命中（漏按）")

    # 确认每个演奏事件只匹配一个音符
    hit_count = sum(1 for j in judgements if j.is_hit)
    assert_equal(hit_count, 2, "应有2个命中，对应2次按键")

    print("PASS")


def test_configurable_window():
    """测试15：可配置时间窗口"""
    print("测试15：可配置时间窗口...", end=" ")

    # 窗口 50ms
    model_50 = VisualScoreReference(hit_window_ms=50.0)
    model_50.add_note(note_id=1, note_number=60, hit_time=5.0)

    # 60ms 误差
    judgement_50 = model_50.judge_hit(note_id=1, actual_time=5.06)
    assert_equal(judgement_50.is_hit, False, "60ms误差在50ms窗口外")

    # 窗口 100ms
    model_100 = VisualScoreReference(hit_window_ms=100.0)
    model_100.add_note(note_id=1, note_number=60, hit_time=5.0)

    judgement_100 = model_100.judge_hit(note_id=1, actual_time=5.06)
    assert_equal(judgement_100.is_hit, True, "60ms误差在100ms窗口内")

    print("PASS")


def test_configurable_preview():
    """测试16：可配置预告时间"""
    print("测试16：可配置预告时间...", end=" ")

    # 预告时间 1.0 秒
    model = VisualScoreReference(preview_time=1.0, screen_height=400.0)
    model.add_note(note_id=1, note_number=60, hit_time=5.0)

    events = model.generate_visual_events()

    # appear 应在 4.0 秒
    assert_close(events[0].time, 4.0, 0.001, "预告1.0秒，应在4.0秒出现")

    # 下落速度应为 400 px/s
    assert_close(model.fall_speed, 400.0, 0.001, "下落速度应为 400 px/s")

    print("PASS")


def test_note_without_duration():
    """测试17：无持续时间音符的移除"""
    print("测试17：无持续时间音符的移除...", end=" ")

    model = VisualScoreReference(preview_time=2.0, screen_height=400.0, note_linger_time=0.5)

    # 添加无持续时间的音符
    model.add_note(note_id=1, note_number=60, hit_time=5.0, duration=None)

    events = model.generate_visual_events()

    # 应该有3个事件：appear, arrive, disappear
    assert_equal(len(events), 3, "无持续时间的音符也应生成3个事件")
    assert_equal(events[2].event_type, 'disappear', "第3个事件应是 disappear")
    assert_close(events[2].time, 5.5, 0.001, "应在 hit_time + note_linger_time 消失")

    # 检查可见性
    visible_at_5_3 = model.get_notes_at_time(5.3)
    assert_equal(len(visible_at_5_3), 1, "5.3秒时音符应可见")

    visible_at_5_6 = model.get_notes_at_time(5.6)
    assert_equal(len(visible_at_5_6), 0, "5.6秒时音符应已消失")

    print("PASS")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("视觉曲谱参考模型自动验收测试")
    print("=" * 60)
    print()

    try:
        test_basic_note_preview()
        test_same_note_repeat()
        test_chord()
        test_rest()
        test_note_off()
        test_reset()
        test_hit_judgement_perfect()
        test_hit_judgement_early()
        test_hit_judgement_late()
        test_hit_judgement_miss()
        test_performance_judgement()
        test_performance_miss_note()
        test_extra_presses()
        test_same_note_one_to_one()
        test_configurable_window()
        test_configurable_preview()
        test_note_without_duration()

        print()
        print("=" * 60)
        print("ALL TESTS PASSED (17/17)")
        print("=" * 60)
        return 0
    except Exception as e:
        print()
        print("=" * 60)
        print(f"TESTS FAILED: {e}")
        print("=" * 60)
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
