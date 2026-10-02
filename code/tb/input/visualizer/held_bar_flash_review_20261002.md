# 按键时长条＋去琴键＋诊断曲谱推进＋底边命中闪光（2026-10-02）

M2可视化窗口；用户经主M2授权本批范围及追加命中通知。主M2已独立登记旧实屏反馈，本文件仅记录新版代码与验证，不重复认定旧视频；截至本轮没有取得cartoon_first_test视频。基于本地e612eae/94ca437，音频只读固定e5eb025（V1＋CC64功能083a07e）。不改正式top/pkg/CST/SDC/公共64bit事件/CDC/音频。

## 新动画语义

- 上飘条只在视频事件成功握手的非零NoteOn开条，从旧JUDGE_Y=400起点开10px初始长度。held期间上端每帧减4，条尾固定410；头到0后饱和，held身份仍保留。
- 对应source_id/channel/note_number的NoteOff（或velocity0）停止生成，两端一起上移，条尾到0才回收。条形表达物理按键时间，不随CC64音频尾音延长。
- 同身份重触发：结束旧held条并优先新空槽；满槽时原位重开并计一次覆盖。新身份满槽则丢新图形、饱和本地drop计数加1，不反压音频；被丢弃身份的NoteOff不会误停其他条。
- 帧起点输出完整工作态快照；同拍事件属于下一完整帧。低空槽分配、高槽覆盖低槽。复位/全局AllNotesOff/失步清除图形，失步提示粘滞到reset。
- 底部琴键和按键高亮绘制已删除，横向音高映射、原起始基线、纵向格线、下落判定线保持。key_down内部调试输出仍是held身份的pitch聚合，不参与底部绘制。

## 下落诊断源修正及证据边界

旧诊断使用score_seq+120作为绝对命中帧，在持续运行后可入队过期曲谱；tracker到hit_frame后距离钳0，显示就在原判定线处，随后按6帧窗口或30帧时长释放。正常约0.1～0.5秒停留与真正不释放是不同现象。

本轮用同50MHz参考的840000周期/帧计数推进诊断时间，source hit_frame=当前本地帧+120，每30帧开下一条，字段在握手等待期间保持；不跨域直接读tracker.current_frame，不更换公共CDC。复位同步启动时间差数周期、小于1帧；仅诊断时间源，不宣称最终曲谱校时接口。

365帧TB（缩小扫描几何、保持50/25MHz并匹配本地帧周期）证明：13音符接收、9次回收、1247次y下降、旧seq+120在后期过期、窗口/时长到期无长驻、字段反压稳定与PLL重置新epoch。**这不是对缺失视频现场根因的确认**。

## 新命中闪光

tracker在已有最近匹配判定成功、相同pitch、未判定槽、时间误差<=HIT_WINDOW_FRAMES且非零NoteOn时，输出1周期内部hit_pulse与note。近连续不同音高pulse均可累积，已判定同实例不重复通知；不新增公共音频消息。

下落模式才接收闪光；范围内每个pitch有独立6帧倒计时，边界发布，约100.8ms @59.524Hz。新正确命中刷新该位置，多pitch同时保持。图形贴SCREEN_HEIGHT底边：5×4亮色核心/9×8外晕，常量矩形比较、边界裁剪/消隐；与删掉的琴键无关。复位/清音/失步/离开下落模式清理pending和倒计时。普通NoteOn、错键、窗口外、已判定音符、velocity0、NoteOff、CC64不产生闪光。

内部端口变更仅为live尾坐标/held/dropcount、tracker hit通知、renderer flash位图，wrapper外部演奏/曲谱握手未改，仅新增HIT_FLASH_FRAMES参数。已有公开模块文件里的兼容参数KEYBOARD_TOP/key_down保留但不绘制琴键。本地丢弃计数只用于测试/内部调试，未加UART字段，硬件中未消费的计数可能被优化，不宣称已做可观测遥测。

## 实际行为验证

| 项目 | 最终结果 |
|---|---|
| 新live状态 | 28项PASS：held/release/长按跨屏/身份隔离/CC64/velocity0/重触发/槽满/saturation/清音/失步/reset/边界快照 |
| 真实命中→flash→RGB | 36项PASS，9个真实命中通知；早晚边界/窗口外/错键/重复/多音高/刷新6帧/熄灭/底边裁剪与消隐/模式/复位/清音/失步/velocity0 |
| 旧score模块 | 84项PASS |
| wrapper画面 | 661项PASS，底部去琴键、新长条/原score颜色和覆盖 |
| Renderer新整数几何参考 | 四参数738568 RGB对照PASS（flash输入为0；闪光像素由36项单独验证） |
| Tracker旧状态等价 | 201857状态/307680距离/1113搜索PASS；比较既有状态，不外推新增通知 |
| M2事件/控制桥联合 | 13项PASS；音频接受不受显示反压 |
| 诊断曲谱 | 3场景/365帧/13接收/9回收/1247下降，stale-legacy复现 |
| 新共存音频参考 | 14项/881249周期/845帧/799非零/75模式变化，音频PCM/I2S/PA/UART/计数逐拍与原e5eb025相同，4声部CC64/视频停钟/PLL失锁/reset，无仿真欠载 |
| 报告门禁 | 正常PASS，4种篡改负例拒绝 |
| 仓库 | check_repo全PASS，git diff --check PASS |

音画TB缩屏64×48仅缩短演示验证，保持50MHz系统、真实48kHz（1041/1042帧周期）、31250 8N1、25MHz像素/125MHzserial；最终物理构建一直使用640×480。PHY行为模型不证明TMDS/PLL物理波形。

## 本版实际Gowin PnR/STA

最终工程code/output/held_flash_audio_visual_20261002；Gowin V1.9.11.03 Education / GW5AT-LV60PG484AC1/I0，run all综合/PnR/码流完成，8实时+8曲谱槽、原50/25/125MHz有效约束/复位位置/引脚电压保持。

| 指标 | 含全部新效果的最终候选 |
|---|---:|
| Logic/Register | 15172/59904；5808/60780 |
| DSP/BSRAM | 28/118；8/118 |
| sys实际Fmax（目标50） | 50.076MHz |
| pixel实际Fmax（目标25） | 25.200MHz |
| serial实际Fmax（目标125） | 1296.595MHz（非输出频率） |
| 最小导出Setup/Hold | +0.031 / 0.000ns（报告精度） |
| pixel最差Setup | +0.318ns |
| Recovery/Removal最小 | +1.074/+0.521ns |
| 全局Setup/Hold违例及所有clock TNS | 0/0，全部0 |
| 存活event/score载荷 | 22/37路径，10ns界限通过 |

最差系统路径u_i2s_tx/bclk_acc_3_s0/Q→u_button_event_converter/overflow_count_31_s0/D，+0.031ns；最差像素路径u_visual/u_scan/pixel_x_3_s0/Q→u_visual/u_scene/u_score_tracker/hit_note_number_4_s1/CE，+0.318ns。完整像素/system报告已导出，不猜根因。全局门禁和精准CDC/后级/10音频引脚+TMDS门禁通过，音频8BSRAM与u_latency65FF保留，PR1014保留。

**余量非常小**。0.000ns是报告的四舍五入读数，不宣称正保持余量或板级稳定。只能交主M2复核，不自行下载；通过工具门禁不等于板级长期可靠。

首个“长条但无flash”候选另在held_bars_audio_visual_20261002通过过STA，不作为最终码流，不沿用其Removal+.006ns或其他余量冒充本最终版。

## 写集与复现

源码：visual_live_state.sv、visual_scene_renderer.sv、m3_visualizer.sv、visual_score_tracker.sv内部通知、新visual_hit_flash.sv；audio_visual_display_probe.sv仅诊断曲谱时间推进。
测试：3个现有visualizer TB更新（live/wrapper/geometry）、新增hit_flash_feedback和diagnostic_score_progress及runner；board联合TB预期/小画面时钟比设置更新。
构建/运行：prepare_audio_visual_probe.py、run_m3_visualizer_sim.ps1、run_visual_path_integration_sim.ps1、两个独立visual build脚本仅追加flash源依赖。有效CST/SDC、公共桥、音频、正式top/规范不改。

```powershell
.\code\scripts\run_m3_visualizer_sim.ps1
.\code\tb\input\visualizer\run_renderer_geometry_equiv.ps1
.\code\tb\input\visualizer\run_tracker_timing_equiv.ps1
.\code\tb\input\visualizer\run_diagnostic_score_progress.ps1
.\code\scripts\run_visual_path_integration_sim.ps1
python -X utf8 code/scripts/prepare_audio_visual_probe.py --output code/output/held_flash_audio_visual_20261002 --vendor code/output/hdmi_link_probe/vendor
D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe code/output/held_flash_audio_visual_20261002/run_build.tcl
python -X utf8 code/scripts/check_audio_visual_probe.py code/output/held_flash_audio_visual_20261002
python -X utf8 code/scripts/run_audio_visual_probe_sim.py --prepared code/output/held_flash_audio_visual_20261002 --small-raster
.\code\scripts\check_repo.ps1
```

实际新版.fs SHA256 `5fba680d005a7eb6cf1da1a49e722719abb88a80d757c08a081fc118e8117a55`。
候选运输目录code/output/held_flash_delivery_20261002/，含audio_visual_held_bars_hit_flash_20261002.fs、manifest.json；纯音频回退不在此包，由主M2核对083a07e的5944a031…f841c1版本提供。
详细输入/报告/测试哈希在code/output/held_flash_audio_visual_20261002/evidence.json及inputs.json/gate.json。原始PnR仍留同目录impl/pnr，旧失败/旧候选未覆盖。全部45输入及38音频Git依赖核验匹配。主M2先做D025复核、统一发布和同版实物安排。本窗口不抢V号、不自行烧录。

## 实屏核对建议（未执行）

1. 先主M2复核并协调M3核hash/SRAM下载，备好同版V1音频回退，不写Flash。
2. AOC显示640×480，默认上飘。按住一个音符≥3秒，确认条头到屏顶仍延伸，松键后条尾上移直至消失；快速重触发和多键不应改变音频。
3. 琴键区应消失。每约5秒自动模式请求在帧边界生效（不是新MIDI按键模式）；下落为诊断曲谱，不是实际歌曲。持续运行超过6秒，录制完整前后画面，确认有新音符继续下降并在判定线按窗口/时长释放。
4. 仅正确命中对应曲谱且在窗口内，屏幕底边该音高位置有约0.1秒闪光；错键/普通自由演奏/松键/踏板不应闪。至少两音高近同时判中检查。
5. 复位/PLL显示恢复、4声部/CC64音频共存仍需同版记录，不能从旧6ade4c或固定色照片外推新版PASS。保存视频/声音、版本、hash、测试时间；异常交主M2协调本窗口定点修复。

本轮等级：L2各项行为＋独立候选L5工具侧。新动画/闪光实物尚未验证，原“下落卡住”缺视频，不作现场根因或已彻底修复声明；T034/S5/L6不据此关闭。
