# 10/17双滑块独立候选：DONE（限定离线包）

本轮独占三处pro_parallel_20261016的隔离候选、自动验证、自审及原件封存已齐套。未提交、未推送、不改Git index/门禁/编号/共享状态；交夜间总控统一收口，M2最终限定复核。此DONE只对应用户单独授权的离线候选，不是Pro DUT、正式整机、实屏或硬件通过；board_release_allowed=false。

## 实现与输入

只读复制旧dual_slider_candidate.sv（SHA a8116d04f7fa70ba4500c4819e3ffb939fcc7096acef9bb7f87004e1e648868f），新module dual_slider_pro_parallel默认640×480、八槽/Y_WIDTH10、preview120、BASE_NOTE36/NOTE_COUNT49，将硬编码FIFO8改为参数EVENT_FIFO_DEPTH32。新增诊断display_event_enable暂停目的ready/fire及公开queue/事件/score观察口；正式生产拟系1，接线交M2。旧视觉、CDC、音频模块本体均未改；逐行差异见CANDIDATE.diff。

开工/预检基线ca4859abc28e3a5f7fdd0250e9f2cd43de39a8c0，实际验证前总控快进b6f289110a0b7341f1f9234c945bcb8d31d95aff。M1旧R05五目录已经发布并恢复，本包不使用/重跑其数学黄金。新增M2双滑块接入合同已读并冻结SHA，规定默认几何/FIFO32、mode同沿语义、score98位和共同复位；它引用138K C旧输入，不能转为Pro的PLL/CST/网表事实。formal_geometry_successor本体未到，Pro新source/ROM/top/trace以及正式mode/score生产者与帧epoch映射仍PENDING。

## 实际执行

Python 3.12.4（C:/Users/songdongkuan/miniconda3/python.exe），Icarus/VVP 14.0 devel（E:/FPGA/GAOYUNFPGA/138K/tools/icarus_oss_copy/bin）；版本双流、EXE/DLL/已知Python依赖、机器、环境和完整SHA见PREFLIGHT_01及ROUND_01/before.json。预检三命令exit0，未消费验证轮。每个子进程由Windows Job先attach挂起子进程再resume，单步和整轮受240秒以及北京时间05:21全局截止共同约束。

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/run.py --output code/docs/test/m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016/ROUND_01
```

正常require_escalated审批通过，runner exit0。只消费**1/6轮**，共6个工具调用（1编译、1正例、4反例），总100.282秒，无超时/失败，源/输入/工具前后SHA同。成功即停，未使用剩余5轮。编译exit0；正例VVP exit0；四个变异VVP均exit1，首REJECT逐一符合预定目标，不能把工具崩溃充当反例。

编译输出中有Icarus对既有always_*常量选择的全敏感提示及旧package缺timescale提示；未因此修改正式模块或放宽判据，实际编译/仿真结论以退出及断言为准。

## 正例与拒收事实

- 正例487项CHECK全部通过，原日志82条EVENT/10条SCORE身份与顺序逐条比较。最后共同reset把计数清零，故最终摘要events=0/scores=0不代表未发刺激。
- 上飘默认八槽：按下长条增长，松键首次发布旧end480、下一snapshot end476，随后完整退出。八槽有效与手算位置在公开日志中保留；未重跑旧99项。
- 下落八槽以**相同hit/duration、不同note/id**刺激，覆盖preview120的140个逐帧整数几何与第141帧退休。第9score只进在途邮箱、第10score源端valid/98bit载荷背压保持，槽退休后恢复且10条全部按序投递；不是八个独立时间安排的曲谱黄金。
- FIFO32与独立mailbox合计33条容量；暂停目的消费时queue32/high32/drop0，第34条故意overflow只drop1，drain顺序正确、队列归空；desync fail-closed直到共同reset清除。音频不依赖显示ready，真实tick/buffer/tx+诊断PCM在显示暂停期间仍提交、欠载0。
- 模式ready/valid、帧边界切换、同帧两toggle抵消、mode_pulse与frame_start同沿保留旧模式/下一帧提交，以及在途事件/mode/score共同reset后无幽灵投递均通过。
- 三个完整800×525/25MHz raster脉冲，两个精确420000像素周期间隔；共921600活动像素（3×640×480），16.8ms/帧即59.5238Hz夹具，消隐黑通过。此前长运动窗是加速frame_start，不冒称HDMI实屏。RGB仅明确核消隐黑，未签色彩像素/屏幕。
- 音频在最后reset生命期实际2424帧；各reset生命期累计有效帧间隔中833拍1855次、834拍924次，独立sample_tick同样只允许833/834；意外audio_underrun0。仅帧/commit/欠载检查，**本轮没有PCM→串行逐样本黄金比较**、R05合成算法或模拟≤10ms结论。

| 真实TB注入 | 退出码 | 唯一首拒收 |
|---|---:|---|
| 源mode脉冲错接像素域，25ns脉冲落在像素沿间 | 1 | MODE_CDC_DELIVERY |
| 丢弃accepted事件输入 | 1 | EVENT_LOSS |
| display_mode切换被固定 | 1 | MODE_SWITCH_STALL |
| 显示暂停错误门控音频calc_ready | 1 | AUDIO_DISPLAY_BACKPRESSURE |

原stdout/stderr、实际argv/cwd/机器/起止/退出/输出SHA、消费标记、冻结执行源和源模块本体在ROUND_01；每个反例是真实新VVP运行，不是篡改正常log。

## 自审与封存核验

主窗口和自有只读子智能体核源码、FIFO33/34、score握手/退槽、mode同沿边界、reset日历、三raster脉冲、四首诊断、全部调用/双流SHA和预算，无具体交付阻断。启动前静态修了runner全局deadline须传给wait预算的缺陷，尚未启动验证不计轮；无执行失败原件可隐瞒。未启用审核员制度。

只读verify_recorded_geometry.py对本轮已有公开packed坐标解包审计，不重跑RTL：140帧×8槽均符合相同时间输入的整数几何；八上飘top[462,470×7]/end480，释放后八end476；82/10/487计数一致，输入log前后SHA未变。软件审计exit0，原命令/双流/源与输入SHA见geometry_audit.*及RECORDED_GEOMETRY_AUDIT.json；本审计只核原件，不另增RTL轮或虚构新刺激。

最终原件入口DELIVERY.json，封包含新RTL/TB/runner、自检与全部执行日志/收据、输入原件、版本/工具依赖SHA及差异表。新ModelSim/Gowin/综合/PnR/STA/码流/下载/设备调用全部0，无N32/菜单/频谱/额外模式。命中闪光旧FAIL继续保留，固定0未修也未验。

## M2接手所需最少事项

INTEGRATION_DIFF.md逐项列正式accepted事件复制点、mode生产者、score生产者/帧零点/epoch、Pro实际时钟和共同复位、唯一扫描/RGB寄存/TMDS、七个静态数据控制异步首级及64/98bit bundled路径的待匹配对象。M2须先固定新Pro同版source/ROM/top/trace与正式mode/score字段，再按基础四声/双音色出口准入安排新复制工程/完整CDC与STA/精确码流；M3后续实屏原始记录另需板卡与许可。本夜不代做。总控负责统一收口与发布，真人M2交接仍待用户转发；直接发总控只表示消息送达，不等于M2签收。
