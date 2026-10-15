# D 双滑块最小隔离候选 — 新修复回归通过，待M2限定签收

> **2026-10-16 新授权修复结果：**用户直接允许修改并解决D问题后，以独立修复批次完成两组回归。
> 当前wrapper修复已编译/仿真，最终TB99个检查通过、四个指定负例均退出1且命中诊断。
> 已补精确RGB、运动期间音频cadence、在途CDC复位清除；工具/原依赖SHA保持一致。
> 最新交付见 `REPAIR_REPORT_20261016.txt`、`HANDOFF_REPAIR_TO_M2.txt`、`delivery_repair_20261016/`。
> 原夜间两组已消费及下文PARTIAL状态为历史原件，不恢复旧额度，不改写旧失败。
> 当前仅隔离模块L2；真实音频链、正式138K集成/STA/实屏及命中闪光不由此签收。总控统一发布。

> **2026-10-16 最新状态：**夜间恢复后审批已放行，发生两组实际工具尝试；第一组版本环境失败，
> 第二组编译0、正例VVP1(t=0参数断言)，0正例PASS、0负例运行。已停止第三组。
> 当前wrapper只做了静态参数修复，修后未编译/未仿真。
> 最新事实以 `NIGHT_FINAL_REPORT.md` / `NIGHT_RUN_RECEIPT.json` 为准。
> 下文及 `RECEIPT.json` / `STATIC_IDENTITIES.json` 是首个L0准备快照；
> `delivery_r01`原包和两次旧拒绝均保留，不能把其中“0工具”历史描述当当前总计。

本目录为 2026-10-15 四包授权中的 D。首个L0快照时，候选实现及测试入口已经编写，**未编译、未仿真**；
不声称模块 L2、整机音画共存、138K 时序或实屏通过。总控统一发布，本窗口无 Git 写入。

## 文件及真实复用

- 新 RTL：`code/rtl/input/m3_dual_slider_138k_candidate_20261015/dual_slider_candidate.sv`。
- 新 TB：`code/tb/input/visualizer/m3_dual_slider_138k_candidate_20261015/tb_dual_slider.sv`。
- 本目录 `run_candidate.py`：新独占目录、90 秒/工具、300 秒总工具预算、私有 Windows Job 进程树，
  原件 stage SHA核同、输入及 Icarus bin/lib/ivl 完整前后身份、argv/cwd/显式环境/双流/退出码。
- `AUTHORITY_AND_FAILURE_HISTORY.md`：两次平台审批拒绝、直接用户授权读取来源、工具零启动事实。

新 RTL 实例化旧的 `visual_event_bridge` / `visual_control_bridge` / `visual_mailbox_cdc` / `reset_sync`、
`visual_live_state`、`visual_score_tracker`、`visual_scene_renderer`；不是仅新模型自我回环。
旧源、公共包、旧约束、正式 top 均只读，现有字段仍来自唯一 `audio_defs_pkg`。

## 接口、假设与 CDC 提案

`sys_clk` 入口接**音频已接受事件的副本**（`accepted_valid/data`），没有视觉 ready 反馈给音频。
source/channel/note 原样送旧 live 状态，旧槽中保留三个字段；不是单个 key_down 位代替多来源身份。
key_down 只是多个 held 实例按 pitch OR 的显示快照。重复同身份继续沿用旧重触发/有限槽规则。
`ALL_NOTES_OFF` 仍是原视觉**全局**清空，不能声称支持新的 source-local panic 语义。

mode/score 入口是 sys_clk 域 valid/ready；生产者必须保持命令到握手，只发一个请求。
不要直接接异域短脉冲。可靠 mailbox 先跨域，mode_request 在像素域翻转，frame_start 才提交显示模式；
若 mode 命令与 frame_start 同沿，提交延后一帧。切换不重设绝对曲谱时间，不改 duration 合同。
score_hit_frame 与 duration_frames 由同源外部曲谱产生者提供，必须按最终实际刷新率量化；
本候选不从 sys 域直接读取异域 current_frame，也没有内置新曲谱时基算法。

共同 rst_n 异步拉低，各域同步释放；PLL unlock 必须清两边，禁止单边独立复位。
事件显示队列溢出按旧桥 drop/desync 粘滞告警直到共享复位；不反压音频。
物理接入仍需 M2 核 bundled-data payload 路径上界及 req/ack 同步器定向 STA，
本包不生成/修改 SDC，不声称亚稳态或 CDC 物理收敛。

默认几何640x480、8槽、preview120帧；TB小几何128x64、4槽、preview8仅为加速验证夹具。
上飘从屏底开始，held尾固定、头每帧上移4；release两端移到0回收。
下落用旧 BOTTOM_EXIT_GEOMETRY / STRICT_CONTACT，绝对帧进度和 duration 不重新定义。
**原命中闪光 FAIL 首轮暂缓**：新候选未接 flash 模块，renderer flash 输入固定0；
这表示最小候选禁用该功能，不是修复、不是该项 PASS，也没有删除旧失败原件。

## 待获准执行的验证

TB 使用40MHz系统域/25MHz像素域独立时钟，独立整数几何预期：
复位、按住长条、松键上移及回收、键盘/MIDI同音多来源、同源不同channel、零力度、
短源脉冲可靠跨域、整帧切换/切回、下落逐帧位置与退出、实际renderer非背景像素和消隐。
独立48k调度夹具检查833/834系统拍与显示同时运行；**不是 synth/PCM/I2S 真链**。
四个 TB 注入反例分别为缺切换、原始错域脉冲、冻结下落帧时间、音频夹具欠载；
要求非零退出且指定 REJECT，无 PASS 混收。没有执行，不报任何测试数量 PASS。
真实音画共存须后续基础 R05 同版签收与实际 capture，本包不自动接 A、不抢其他目录。

命令（当前禁止自动重试，仅供审批通过后的新输出使用）：

```powershell
& 'C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -I -S -B -X utf8 code/docs/test/m3_dual_slider_138k_candidate_20261015/run_candidate.py --output code/docs/test/m3_dual_slider_138k_candidate_20261015/run_02
```

runner拒绝已有目录；失败编译产生的任何 vvp 不运行。首次动态执行前应另冻结当前源码与工具SHA。
因平台授权审批阻断，L0 候选准备可交，D 模块验证与整体完成条件尚未满足；board_release_allowed=false。

## 手工静态自审结论

新模块全部状态只在像素域一个 always_ff 中驱动；跨域均复用旧握手桥。
输出几何来自被实例化模块公开端口，候选不读旧模块内部层级；仅 TB fault injection 使用层级 force。
下落冻结反例 force `u_falling.current_frame` 而非 input frame_start，避免输入端口 net alias
连带冻结全局frame_start，导致不相关的上飘断言先失败。此改法只静态核对，尚无工具证据。
所有原视觉/公共源保持原字节；SHA 清单及封包索引在本目录交付原件。
