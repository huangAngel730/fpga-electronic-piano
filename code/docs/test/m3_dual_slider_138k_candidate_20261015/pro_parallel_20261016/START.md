# M3双滑块：10/17新夜间独立候选（最长5小时）

基线ca4859abc28e3a5f7fdd0250e9f2cd43de39a8c0；总T0北京时间2026-10-17 00:21，最迟05:21结束。用户包M3_并行拓展双滑块窗口_2026-10-16.md为本轮精确任务，按总控NIGHT_PLAN_20261017.md执行。新包独占三处rtl/input、tb/input/visualizer、docs/test的m3_dual_slider_138k_candidate_20261015/pro_parallel_20261016；旧D及所有原件只读，不Git写、不跑门禁/编号/状态。

目标：640×480、八槽、preview120、FIFO32队列的双滑块隔离候选，自动核运动/退出、mode/score握手、满空/溢出、复位与视频节奏，四反例必须首差异命中。只复用既有视觉/CDC源，不重跑旧99/4。formal_geometry_successor_20261016本体未找到，正式Pro source/ROM/top/trace、M1新黄金同样缺件；只签本模块夹具，board_release_allowed=false，不签Pro DUT或实屏。

工具仅本机现有Python/Icarus，先预检版本/EXE及已知依赖SHA/原始双流，再启动固定源。最多6轮新代码—定向验证：每轮Python软件≤90秒、Icarus编译+仿真累计≤240秒，5小时总限优先。首次失败原件留存，仅确认的新候选/TB/runner缺陷可在剩余轮数修复；成功即停、不凑轮数。ModelSim/Gowin/综合/PnR/STA/码流/下载/设备次数均0，不安装工具、不N32。

候选增加FIFO_DEPTH=32及display_event_enable诊断消费使能，公开队列水位/高水位、目的握手事件与score载荷等观察端口；生产接入应将诊断使能系1，正式mode来源/score字段/复位与40→25时钟由M2固定后另签。显示消费暂停只门控目的ready/fire，不门控音频；音频并行使用已存在sample_tick_gen/pcm_frame_buffer/i2s_tx和诊断PCM生产者，非Pro合成算法。源事件无需显示ready，容量为32排队+1在途，第34条溢出需记录drop/desync。

正例：八槽上飘增长/松键两帧后位移/退出；八条默认preview120下落整数几何及退休；第9score在途/第10source背压保持与后续恢复；模式握手和帧边界、同帧双切换抵消；FIFO33容量和一次刻意溢出/共同复位恢复；显示阻塞时真实音频buffer继续提交且欠载0；最后完整800×525/25MHz raster三帧、640×480活动区、两个16.8ms间隔（59.5238Hz夹具），此前运动帧为加速夹具。命中闪光历史FAIL保持不修。

四个新RTL反例预定首诊断：错域mode脉冲→MODE_CDC_DELIVERY；丢accepted事件→EVENT_LOSS；模式切换卡住→MODE_SWITCH_STALL；显示回压错误门控audio calc_ready→AUDIO_DISPLAY_BACKPRESSURE。均为TB故障注入，不修改原正式模块。工具崩溃/通用timeout不能充当反例通过。

默认自审由本窗口及自有只读子智能体完成，不启用审核员制度。最终仅一份完整回执发夜间总控01a14050-cd98-7c41-8004-5d3e25765167，由其汇总发布/M2复核；送达不等于签收。剩余正式接线/STA/实屏事项列差异表，无可行动工作提前结束。
