# V1＋CC64＋完整可视化独立共存候选（2026-10-01）

M2可视化窗口，复用94ca437（依赖2d874f1），音频固定e5eb025（功能083a07e）。本轮仅新建board显示伴随模块、生成/仿真/门禁脚本及专用TB。正式electronic_piano_top、audio_defs_pkg、CST、接口规范、音频算法、已有renderer/tracker/wrapper没有改动。主集成M2负责D025复核与统一发布；M3仍负责实物取证，新的真实M3私发分工未确认。

## 独立候选机制

生成器逐字核验音频GPRJ全部输入到固定Git提交，ROM与头文件也核对Git字节。输出目录的top副本仅改模块名、加TMDS诊断端口并复制音频已接受事件到显示伴随模块；移除这些明确增量后与正式top文本等价。音频不接视频ready、PLL lock或视频reset，显示故障不会反压或复位音频。

显示沿用event/control bridge、25MHz像素/125MHz串行PLL、两级复位和640×480扫描（总800×525，约59.5238Hz），8live+8score槽。显示公共复位断言源为**外部sys_rst_n与PLL lock**，各域分别同步释放。音频50MHz保持原时钟不确定度Setup1ns/Hold0.5ns和三I2S输出max5ns/min0ns，不改控制端口、实际ROM或冻结音频参数。

诊断自动每5秒请求一次上飘/下落切换；模式仍在帧边界生效。下落使用简单合成曲谱序列，经原score握手传递。它不是正式菜单/真实曲谱文件，也未实现Program Change或面板模式键。演奏副本包括实际MIDI消息，但原画面只显示键事件，没有增加延音尾迹/踏板提示。UART继续原音频七字段，不把视频状态冒充已有字段。

## 真实已执行验证

1. 初版诊断误把音频已同步释放的rst_sync_n接到视频：系统50.450MHz、像素25.866MHz，但2个Recovery违例−4.169ns，门禁明确FAIL，未烧录。修正仅生成top的显示复位连接为原外部sys_rst_n，在新目录重建；失败原报告保留。
2. 初版默认640×480仿真：2481249系统周期/2381真实音频帧/2335非零帧，真实50MHz、48kHz和31250 8N1；14项检查PASS，2次模式切换、894969有效像素。PCM/I2S/PA/UART/计数逐系统周期与未加显示的音频参考一致。显示停钟、PLL失锁和恢复场景无音频欠载。此组对应修正前复位连接，不能冒称最终连接完整画面复验。
3. 最终复位连接补测：TB仅将扫描几何缩到64×48和模式周期缩短，音频/MIDI/像素/串行频率均保持真实；881249系统周期/845音频帧/799非零帧，14项PASS，75次模式变化、234674有效像素。四音和弦、CC64保持、视频停钟/PLL失锁不影响音频、复位恢复后没有旧显示事件重放。帧间隔严格1041/1042系统周期。模型PHY仅用于行为接线，不是物理PLL/TMDS。
4. 最终实际Gowin始终用完整640×480，没有TB缩屏参数。全链门禁（原音频约束+原视频CDC）PASS，10音频引脚和4对TMDS/Bank一致；8BSRAM保留，实际u_latency65寄存器保留。
5. 门禁正常报告通过，篡改Setup端点、删除I2S输出约束、删除event载荷最大延迟、移除周期寄存器4种独立负例均拒绝。check_repo全PASS、Python编译和git diff --check通过。

## 最终独立共存Gowin结果

Gowin V1.9.11.03 Education / GW5AT-LV60PG484AC1/I0，run all完成。

| 指标 | 最终共存候选 |
|---|---:|
| Logic | 12960/59904 |
| Register | 5001/60780 |
| DSP | 28/118 |
| BSRAM | 8/118 |
| 50MHz系统实际Fmax | 50.543MHz |
| 25MHz像素实际Fmax | 27.361MHz |
| 125MHz串行实际Fmax | 1122.018MHz（不是提高输出频率） |
| 最差导出Setup/Hold | +0.215/+0.002ns |
| Recovery/Removal最小 | +1.076/+0.093ns |
| 全局Setup/Hold端点及所有时钟TNS | 0/0，全部0 |
| 存活event/score载荷 | 17/19路径，10ns界限PASS |

最差系统路径u_i2s_tx/bclk_acc_3_s0/Q→u_button_event_converter/overflow_count_31_s0/D，Setup+.215ns；最差像素路径video复位同步末级→tracker miss CE，Setup+3.452ns；串行两级同步路径Setup+7.109ns。原报告精确端点和后级路径非空；不把17/19外推全64/98位覆盖。PR1014仍在，系统/保持/移除余量小，L5不替代上板稳定性。

## 文件与复现

新增源码：`code/rtl/board/audio_visual_display_probe.sv`。
生成器：`code/scripts/prepare_audio_visual_probe.py`；仿真：`run_audio_visual_probe_sim.py`；门禁：`check_audio_visual_probe.py`。TB：`code/tb/board/tb_audio_visual_coexistence.sv`、`audio_visual_phy_model.sv`、`verify_audio_visual_report.py`。

工作树根目录执行：

```powershell
python -X utf8 code/scripts/prepare_audio_visual_probe.py --output code/output/audio_visual_v1_external_reset_20261001 --vendor code/output/hdmi_link_probe/vendor
D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe code/output/audio_visual_v1_external_reset_20261001/run_build.tcl
python -X utf8 code/scripts/check_audio_visual_probe.py code/output/audio_visual_v1_external_reset_20261001
python -X utf8 code/scripts/run_audio_visual_probe_sim.py --prepared code/output/audio_visual_v1_external_reset_20261001 --small-raster
python -X utf8 code/tb/board/verify_audio_visual_report.py code/output/audio_visual_v1_external_reset_20261001
```

生成器固定音频Git提交，不读取旧54774f1或pop_repair顶层；Git提交对象必须本机可用。只写output生成副本，路径头/ROM绝对化有明确哈希，不改算法。供应IP副本需匹配PLL ededfd3e…、GUI DVI b378c6a4…原核验哈希；缺失/改变拒绝。ROM放入复核包，不能省略ROM以获得虚假资源收益。

最终.fs：本工作树`code/output/audio_visual_v1_external_reset_20261001/impl/pnr/audio_visual_coexistence_top.fs`。
SHA256 `6ade4c759906fecfb3fb8f13d56d40d434916e40cd77f6c445e87bdd16652a56`。

全部输入/报告/ROM哈希：同输出目录`inputs.json`、`gate.json`、`evidence.json`。报告源码包：`code/output/audio_visual_v1_review_final_20261001.zip`，SHA256 `4a0e3d9b1735d084aaaa1413ebdeddf6fc205223b923489a31f8abb6603b3f50`，344688字节，无.fs。旧失败报告留在`code/output/audio_visual_v1_20261001/`，不作为可测码流。

## 实屏准备（必须先主M2独立复核再协调M3）

这份是独立候选L5，不是正式主工程/整机S5或L6。未自动下载。正式接口组加入HDMI还需要先给用户可转发群通知并确认已发，不用此诊断生成副本绕过正式通知。

1. 主M2先核对上述FS哈希、输入版本、门禁和当前板上音频恢复版本；协调M3测试时段。明确该码流将替换当前SRAM，不能写Flash。
2. 核对板卡/NEO HDMI TX和AOC Q27B35 HDMI输入。保持640×480/约59.524Hz输出，不按屏幕2K/120Hz标称改时钟。电源按现有板级事实，先低音量，MIDI继续已确认的隔离3.3V/R17路径，不改IO/Bank。
3. 选择HDMI实际输入，先确认识别信号、固定琴键画面；真实按键/MIDI触发上飘和琴声。诊断每5秒请求模式切换，在帧边界出现；下落合成序列不是完整歌曲，不以此评演奏命中算法。
4. 用相同四键和CC64操作检查声音；记录是否出现停声/欠载现象（UART本轮不安排暂停的T025/T026补验）。测试复位及显示重新锁定，观察两种画面恢复；不在带电未知状态乱拔线、不修改电压配置。
5. 保存下载日志、码流/hash、屏幕OSD信号、短画面/声音视频、测试时间、实际操作与故障描述。无信号/花屏/音频异常交M2定点排查，不自行改约束。
6. 测试结束与M2确认恢复最新音频码流和对应哈希。只有实屏及音频共存证据齐全才标L6；蓝灰探针与此候选分别记录，不能互相替代。

以上是步骤准备，不表示已经通知真实M3、已经安排或完成实测。
