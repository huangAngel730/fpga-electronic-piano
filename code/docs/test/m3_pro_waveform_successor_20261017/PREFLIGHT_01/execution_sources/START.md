# E2 固定左波形：10/17 第二任务

责任窗口：夜间任务4。授权：第二任务单与 task2_coordinator/NIGHT_PLAN_20261017_TASK2.md；仅本后继 RTL、TB、docs 三目录。E1、旧源码、旧证据、正式工程只读。共享 Git、编号、门禁和发布归夜间任务1。

目标：只读联接现有观察桥与固定左波形，40MHz 音频观察域→25MHz 像素域。历史真实 A 捕获5849包逐包恢复833/834音频拍相对节奏；另列 synthetic 的符号边界、左右不对称、窗口替换和显示阻塞。独立黄金先按 signed24 求每四点 min/max，再右移16位；固定 x64..575/y64..319、2048点、两拍输出。正常例与实际 RTL 强制坏例核序号、帧锁存、复位、显示不反压音频。

计划最多六轮固定源/输入实现验证；每轮 Python≤90s，编译+仿真总≤600s，成功即停。首失败原件永久保留，不同修复才可消费下一轮。单进程 Job Object 拥有子树，超时只终止自有进程。准备/预检不执行旧专项。本窗04:51北京时间收口，整夜05:21硬截止（UTC20:51/21:21）。

缺件：新 Pro 源码/ROM/top/trace、商用许可与板卡/仪器未收到。历史 RTL A 重放不等于 Pro 实屏或板测。总任务 PARTIAL；board_release_allowed=false。CDC 仿真不替代 bundled-data 物理约束及完整 STA。正式接入决定归 M2。

负例首拒收预定义：1左右错接→PIXEL_REFERENCE；2非帧边界发布→WINDOW_FRAME_TEAR；3丢第1000号样本→SAMPLE_SEQ_GAP；4显示复位未传入 renderer→RESET_TRACE_STALE；5显示队列满阻止音频采纳→AUDIO_DISPLAY_BACKPRESSURE。强制点只在 TB，生产候选无故障开关。
