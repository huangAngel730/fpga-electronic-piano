# H：真实混音 → 单声道效果 → 原 PCM 提交验收

仅 TB 接线，不改生产 core/commit/bank/算法/顶层/工程/约束。
真实 V1/CC64/Pitch-Mod 候选银行、原 voice_gain_q15_candidate、四声部
pcm_mixer_4voice，经 G 单声道事务候选，进入原 pcm_result_hold 和
pcm_frame_buffer。效果后的 mono PCM 复制给 L/R，非独立立体声效果。

复用 F 的源身份/ROM 检查和现有 M2 ADSR patch 生成器，只读原生产与
候选源；ModelSim 直接编译真实分配器。不重复 F UART 场景或数学网格。
本轮直接驱动公共事件进入银行，输入覆盖不能称新的 DIN/UART 实测。

```powershell
python -X utf8 code/scripts/run_m3_delay_pcm_acceptance.py
python -X utf8 code/scripts/run_m3_delay_pcm_acceptance.py --check-capture <capture>
.\code\scripts\check_repo.ps1
```

DEPTH16/1024 各实际跑 50 MHz / 48 kHz 的 1041/1042/1042 周期帧，512
连续正常四声部帧无欠载；干声参考、真实 Pitch/Mod/CC64 与 4800 样本
Release 后原银行声部回收；全声部归零后仍每帧处理零 PCM，推进回声历史。
明确标记的 mixer 边界夹具另验脉冲/反馈、四路正负满幅和干湿饱和，
不冒充银行正常演奏输出。未采用新公共效果控制编号/音色策略。

独立 Python 根据实际接受的输入递推历史，逐乘积 floor>>15 再相加、
PCM24 饱和；不调用 M1 延迟模型。分别比对真实 Q15 gain/混音、E+2
raw 写地址/反馈值、效果 PCM、frame id、实际 frame_buffer 的 pending/
held 消费及欠载计数。实际输出背压保持由 G 验证；H 聚焦系统接线。
不是第二份 ADSR/V1 数学模型，波形/包络由原银行产生并记录。

取消覆盖 E+1/E+2/E+3/held 四个时点：接受后照常推进历史但丢弃输出，
每项故意少一帧且原欠载计数相符；这 4 个故意缺样与正常 512 帧分列。
脏历史在途 reset 后恢复零输出，与 cancel 不清历史严格区分。
accepted=consumed+cancelled+reset_drops，结果消费与 PCM commit 一一对应。

三个反例只在 output scratch 编译运行：错 PCM frame id（真实 RTL 断言），
缓存读地址差 1（独立反馈断言），漏 wet（独立 PCM 断言）。后两者仿真
本身可以 exit0，由 Python 判定失败；不是编译错误/timeout 当有效反例。
空/截断/未知记录 capture 三种真实 CLI 非零退出。`--positive-only`
仅供开发，full_acceptance=false，不能当最终交付。

最终实际数量/源 SHA/版本/命令与日志见
`code/output/m3_H_release_20261004/evidence.json`。范围 L2/L3，未做正式
接入、整机资源/PnR/STA/上板/端到端延迟或参数切换无爆音验收。
按本任务范围不写共享编号/状态表，由 M2 复核登记，交接待用户转发。
