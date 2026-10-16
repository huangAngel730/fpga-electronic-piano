# D恢复批次R01：只补四个RTL行为负例

2026-10-16；HEAD c12636c。已通过read_thread读取夜间总控最新用户原文：“允许授权 你是总控 你来给他们发消息 授权夜间任务1 2 3 4 之间的发送对话 主要是1控制2 3 4，2 3 4返回结果给1 因为对话 夜间任务1是总控”。其适用上下文是用户接受A/D恢复条件，精确范围见总控RESUME_R01/AUTHORIZATION_AND_DISPATCH.md。本轮完成/阻断直接一次回总控，不联系其他窗口或真人。

只写D docs/test与tb/input/visualizer下night_20261016/RESUME_R01。旧候选、源码、封包和77个已暂存文件只读；本窗口不Git写。本新批最多3组、每工具/组≤300s、累计实际仿真≤900s，首次全四反例通过就停止；平台拒绝或上限就封存。允许正常require_escalated运行同一工具/Job，不恢复旧消费。

复制已过正常组的同字节TB，不重复正常组；只编译一次供四个运行时变体共用。checker只迁移ROOT路径，判据不放宽；runner仅迁移路径/新批次账本、删除正常运行并加强旧封包来源核验，差异见COPY_MAP/runner.diff/checker.diff。冻结全部原RTL/C decoder/Windows Job/工具/依赖SHA、旧正常capture与当前复制源前后SHA。每工具创建前消费、双流/命令/cwd/退出/耗时保存。

启动前固定行为与指定诊断：

| mutation | RTL夹具故障 | 必须观察的检查结果 |
|---|---|---|
| 1 | epoch1 req48故意不生产PCM，其余输入不变 | 模拟器exit0且58项视觉检查结束；checker exit1/UNEXPECTED_UNDERFLOW |
| 2 | tx输入的play_left/play_right交换 | 模拟器exit0且58检查结束；checker exit1/SERIAL_PCM_LSBJ_OR_STEREO |
| 3 | 观测DIN经真实BCLK两级管线延迟一采样位 | 模拟器exit0且58检查结束；checker exit1/SERIAL_PCM_LSBJ_OR_STEREO |
| 4 | display_mode为下落时错误门控tx.valid | 模拟器exit0且58检查结束；checker exit1/SERIAL_PCM_LSBJ_OR_STEREO |

反例必须由真实RTL仿真产生新capture，不使用软件篡改capture代替；工具自身崩溃、超时、缺文件或未完成TB均不算指定故障成功。失败保留最早原件后仅在新复制源做有依据修复。旧正例188串行帧/58检查复用，不补跑。诊断PCM不是R05算法；显示帧为加速夹具；不签正式整机/STA/实屏/模拟延迟，board_release_allowed=false，命中闪光旧FAIL不修。
