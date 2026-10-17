# R7-A public_capture_tb 开工

本轮task-day2，基线4fd3366e42fd2356e56eb96eee70b6771afd4bb1，时间盒18:55–22:55北京。主责仅三根下pro_basis_r07_20261017/public_capture_tb；旧R06/driver/产品、M1/M2、正式工程和共享状态只读，总控统一Git。本窗口不fetch/同步或写index。

实现整机公开采集TB＋passive observer＋输出schema及纯软件合成检查。已确认M2有38个静态obs出口；19项M1语义等仍缺，必须null＋原因，不能说全部出口不存在。只复用R6-2 driver及其最终RUN_02输入，绝不重跑旧生成/自检；其event_ready输出不能接DUT输出，整机ready背压暂不支持，driver辅助log不作接受账本。

所有采样在实际obs_core_clk posedge PRE_NBA；独立记录外部reset、本地reset和PLL变更原件，再以RESET_EDGES绑定epoch；保留原行/cycle/time、FRAME F、真实A、result、commit、全部TX扩展及真实finish/END/MONITOR_END。61字段对象保持原schema，扩展/缺项理由/来源在版本化外层。不生成FRAME_PLAN，不读取私有wave/env/phase。

R7-A唯一初组≤90s；仅新具体缺陷一次≤60s增量，先静态自审及冻结RUN_SPEC/输入/源/工具SHA再执行，保留所有失败和原双流。HDL编译/仿真、EDA、设备新执行0，TB始终NOT_RUN。当前实物UNKNOWN；软件准备完成不等于G0–G3或真实Pro通过，board_release_allowed=false。
