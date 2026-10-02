# V0148反馈定点修复：严格到线帧与即时衰减闪光（2026-10-02）

本窗口M2局部候选，基于61903f0（已由主M2发布70d0a9b/f6a6f5f/V0148）。用户明确“不用看视频”，本轮没有查找/抽帧/观看视频，不等待视频；依据明确新语义、M3文字反馈和实际源码。已实屏通过的上飘屏底长条/held/松键状态文件逐字保持；条形运动/曲谱诊断源/已冻结音频不返工。主M2登记实物反馈，本轮不改主任务板/当前状态/编号。

## 错误机制与本轮合同

旧tracker以abs_error<=6允许提前/离屏晚按；旧hit_flash通知写pending，等下一frame_start才visible；旧RGB色彩6帧恒定。这与新“到线帧收到对应NoteOn立刻闪并衰减”语义不一致，不能写成已确认的芯片或电气故障。

新wrapper明确STRICT_CONTACT=1，tracker默认0仍保留旧合同。新严格leaf先筛：slot_used、未judged、pitch相同、hit_frame==effective_frame；同boundary以effective_frame=current_frame+1，其他周期以current_frame。采样后NBA发布的曲谱几何也用这个current_frame，已用同边界TB核对前沿到48/480，不以系统域诊断计数代替可见帧判定。

筛出到线eligible槽之后才比较/低槽优先；未来/过去同pitch不参与。仅下落模式、非零Velocity NoteOn成立才会置judged/hit并通知。提前1帧/1周期、晚1帧、错音、NoteOff、CC64、提前按住的held和velocity0不命中，不缓存提前NoteOn、不污染judged；只有实际到线重新收到新的NoteOn才可触发。

STRICT_CONTACT下miss在到线帧之后生效；运动/几何和图形回收规则仍保持V0148，不因严格判定重写。时长条保持贴底时，后续帧不重复到线。active重复score_note_id在输入握手后丢弃重复实例，不增加槽/重新武装；同ID在旧实例回收或整曲reset后允许再用，不声称无限历史ID去重。同pitch同时间不同ID仍每个实例最多一次，两个新的NoteOn可以依次判中不同实例。

准入时间是**视频域真正收到的事件**时刻。现64bit消息没有物理按键时间戳，不倒推出MIDI串行接收/CDC之前的按下时刻；协议链路时延仍存在。本次不修改公共消息或缓存桥契约。

## 闪光路径与扫描边界

hit_pulse/note为tracker注册输出；flash下个pixel_clk直接置count，去掉pending帧缓存。成功NoteOn采样→active和通知→active在定向测试最大均1个25MHz像素时钟（40ns），满足<=2cycle内部目标。并非宣称物理按键到画面40ns，未包括MIDI/CDC/像素扫描。

默认4个常量强度阶段，49个可显示pitch各一有限计数，无额外乘除、无粒子：

| 阶段 | 核心RGB | 光晕RGB |
|---|---|---|
| 初始强亮 | FFFF E0（白黄） | 80E8FF |
| 下一帧 | FFD060 | 4080B0 |
| 暗橙 | B06820 | 204060 |
| 微光 | 503010 | 102030 |
| 结束 | 不绘制闪光 | 不绘制闪光 |

激活到下一frame_start先保持强亮，然后每帧递减，约3～4帧跨度（50.4～67.2ms@59.524Hz，首阶段可能不足一帧）。实际同frame_start通知优先于递减，不丢初始峰值。连续新实例命中刷新，多pitch可在连续像素时钟接收且独立衰减。局部底边flash颜色允许中帧变化，条形状态和位置仍原帧快照。

屏幕若已扫描过底边，该帧过去的像素不能重画。真实25MHz缩屏扫描TB在输出寄存器采样点记录RGB：扫描前通知该帧底部可见白黄；扫描后通知寄存器立即active但下一次底边扫描才见第二阶段，延迟有界为一完整扫描周期。不能把它叫额外帧缓存，也不能保证每次看到全亮第一阶段。全640×480实际一帧约16.8ms；本模块不插入新RGB流水周期或更改同步线。

退出下落、清音、失步、reset清除count/level；闪光范围/底边裁剪与去琴键维持。内部新增2bit/pitch强度位图和match_enabled入口，未改wrapper外部事件/曲谱握手。默认HIT_FLASH_FRAMES改4；有效CSTSDC/时钟/复位/音频、公共桥和64bit事件都不变。

## 实际验证

| 测试 | 本版结果 |
|---|---|
| 新严格到线wrapper TB | 49检查、13真实通知，提前2/1帧、边界前1cycle、到线boundary/中帧、晚1帧；held无缓存、wrong/zero/off/CC不污染，合法后来NoteOn成立；近同pitch、duplicate ID/实例、低槽优先、多pitch连续cycle、mode入/出边界 |
| 通知延迟与衰减 | 真实25MHz，event_to_active_max=1/notice_to_active_max=1cycle；强亮→黄→暗橙→微光→灭、重启、清理、bottom裁剪/de |
| 实际扫描TB | 12检查PASS；scan前/后、sameframe_start采样沿、输出时钟采样、强亮/下一帧衰减、禁止回画过去像素 |
| 既有live/legacy score/wrapper | 28/84/661 PASS；live源文件逐字未改 |
| 底边运动 | 34项+88000整数oracle PASS；只把旧late-hit断言改为新strict拒收，不改运动oracle |
| Renderer参考 | 四参数738568 RGB PASS（flash0）；新调色板由严格/扫描测试独立验证 |
| Legacy tracker等价 | 201857状态/307680距离/1113搜索PASS，仅STRICT_CONTACT=0，不当作新判定语义等价证明 |
| 事件/控制桥联合 | 13项PASS |
| 诊断时间/释放 | 3场景、365帧、13recv/9retired/1247下降PASS，诊断源未改 |
| 最新音画隔离 | 14项/881249cycles/845frames/799非零/75mode，真实50MHz/48kHz/31250MIDI/25pixel/125serial，无仿真欠载、逐周期原音频一致；TB缩屏64×48，PnR始终640×480 |
| 新报告负例 | 4种当前报告篡改拒绝；专用重复表回归及5负例在原bottom_exit报告上PASS（新报告没有该重复样本，不能假称在新报告复现过） |

用户“不看视频”已遵守。上述初版TB两次失败是长音覆盖像素预期、扫描TB未跨采样沿/未等disable同步沿的问题，修正后明确通过，不把失败删成“首次全通过”。无新实物结论。

## 新Gowin独立共存报告

Gowin V1.9.11.03 Education / GW5AT-LV60PG484AC1/I0，8live+8score，完整640×480（800×525）及实际50/25/125MHz；audio只读e5eb025/083a07e V1+CC64。

| 指标 | 严格即时闪光候选 |
|---|---:|
| Logic/Register | 15611/59904；5853/60780 |
| DSP/BSRAM | 24/118；8/118 |
| sys Fmax（目标50） | 50.015MHz |
| pixel Fmax（目标25） | 32.556MHz |
| serial Fmax（实际125不变） | 1122.018MHz |
| 最小导出Setup/Hold | +0.006/+0.001ns |
| pixel最差Setup | +9.284ns |
| Recovery/Removal | +0.868/+0.651ns |
| 全局Setup/Hold端点/TNS | 0/0，各clock TNS0 |
| 存活CDCevent/score | 22/50，原10ns/精准first-stage例外/后级非空门禁PASS |

系统最差：u_i2s_tx/bclk_acc_1_s0/Q→u_visual/u_event_bridge/queue[18].velocity_8_s1/CE，Setup+.006ns。像素最差：u_visual/u_scan/pixel_x_7_s0/Q→u_visual/u_scene/u_score_tracker/miss_mem_7_s1/CE，+9.284ns。未擅自改公共桥/音频缩时序，system余量极小须主M2明确评估。25MHz相对V0148改善是strict资格精简比较链，不是放宽时钟。PR1014保留，不保证板级稳定性。

全局STA、复位Recovery/Removal、10audio脚/4对TMDS、65latency寄存器、8audioBSRAM门禁通过。22/50是优化后存活字段，不外推完整64/98bit物理覆盖。L5为独立tool-side候选，生产top和整机L6仍不通过这份报告自动验收。

## 复现与交付

源码只改4个可视化内部文件：visual_score_tracker.sv、visual_hit_flash.sv、m3_visualizer.sv、visual_scene_renderer.sv。脚本只更新run_m3_visualizer_sim.ps1增加扫描TB源/入口。既有live、score源/桥/有效约束和正式audio源码不改，旧成功.fs不覆盖。

```powershell
.\code\scripts\run_m3_visualizer_sim.ps1
.\code\tb\input\visualizer\run_renderer_geometry_equiv.ps1
.\code\tb\input\visualizer\run_tracker_timing_equiv.ps1
.\code\tb\input\visualizer\run_diagnostic_score_progress.ps1
.\code\scripts\run_visual_path_integration_sim.ps1
python -X utf8 code/scripts/prepare_audio_visual_probe.py --output code/output/strict_contact_audio_visual_20261002 --vendor code/output/hdmi_link_probe/vendor
D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe code/output/strict_contact_audio_visual_20261002/run_build.tcl
python -X utf8 code/scripts/check_audio_visual_probe.py code/output/strict_contact_audio_visual_20261002
python -X utf8 code/scripts/run_audio_visual_probe_sim.py --prepared code/output/strict_contact_audio_visual_20261002 --small-raster
python -X utf8 code/tb/board/verify_audio_visual_report.py code/output/strict_contact_audio_visual_20261002
python -X utf8 code/tb/board/verify_visual_direct_report.py code/output/bottom_exit_audio_visual_20261002
.\code\scripts\check_repo.ps1
```

新.fs SHA256 `729fe910a08578db20991326945973d4d310a70ba6d498d9ca8786aaa24a30df`；原始STA HTML SHA256 `61f1fdcec4a5f4b799e42b956b591968f8d91a4d316da78d4d92d4b335563508`。
所有45输入/38audioGit依赖、原报告/行为logs hash在output/strict_contact_audio_visual_20261002/evidence.json及inputs/gate.json；旧报告保留。尚未烧录，候选需要主M2D025复核与同版实屏动作安排；纯音频回退083a07e/5944a031…f841c1按既有M2核验版本，不自动更换V3音色。

主M2独立登记本轮，不抢验证编号/不覆写其任务板，交付消息由用户转发确认真实成员送达。本窗口仅本地提交；新版实物未验，不声称本次flash实物失败已确认修复或整机音画PASS。
