# 屏底起点＋下落连续退出与长音条形候选（2026-10-02）

用户在本窗口明确要求起始位置为屏幕底部，并授权执行下落方案。基于7bd3068；这是新的行为改动，不重跑原码流、不说此前“屏底退出方案”已反复试过。没有取得原cartoon_first_test视频，不认定现场异常根因。音频只读固定e5eb025的083a07e V1+CC64。

## 实现

wrapper上飘JUDGE_Y参数来源从旧400改为SCREEN_HEIGHT-10，即初始区间[470,480)，实际条尾480。保持source/channel/pitch隔离、held尾固定、松键两端同速上移、8槽策略及CC64独立。

下落renderer改消费tracker新的内部slot_top_y/slot_end_y区间，逐像素按[top,end)裁剪。前沿在hit_frame到达排他底边480，判定线仅在下落模式的y479绘制，旧y400无停留线。默认480/120=4px/帧：短音hit时[468,480)，hit+1为[472,480)，hit+2为[476,480)，hit+3为[480,480)离屏。位置不固定、不等待窗口结束才消失。

长音尾部按hit_frame+duration到达底边，默认30帧生成120px长条；hit时[360,480)，hit+10为[400,480)，hit+30为[480,480)。长度至少12px，duration0或过短使用最小短条。超过屏高的长音上端裁0，但时长不缩短。32位时间比较保留；hit+duration/回收时刻用额外1位加法，溢出饱和到最大时间而不回卷为过期。当前帧计数仍原规则，未定义跨32位回绕的整首歌曲连续播放。

图形消失和判定回收分开：wrapper明确启用BOTTOM_EXIT_GEOMETRY模式，slot保留到hit+max(duration,判定窗口,短条离屏时间)，严格超过才回收。短duration1不能使晚判窗口提前结束；短条已看不见时hit+6仍可判中并触发底边闪光。长音和短音运动不因hit/miss改变，判定只影响颜色/闪光。

tracker原slot_y接口保留作兼容参考，旧retirement模式仍是默认0，wrapper明确新模式1。legacy等价TB仅证明未改旧模式距离/最近匹配；新mode的退出/保留语义由专用TB证明，不能冒称所有新行为与旧版相同。新增端口只在可视化内部；wrapper公共演奏/曲谱握手、64bit事件、桥CDC、音频和正式接口组无变。

## 新测试结果

- tb_bottom_exit_motion：34项状态/像素检查、88000独立64位整数几何对照PASS。默认实际640x480；上飘初始470/480、松键/长按回收、短音连续退出、旧400处背景、long30/long200、最小12px、duration1晚判、窗口6边界、时间加法溢出饱和、失步/reset。
- renderer四参数参考：738568 RGB比较PASS。oracle已改为明确top/end区间和屏底线；既有flash像素由36项真实tracker→flash→RGB测试另验。
- live28、score84、wrapper661、hit_flash36全部PASS；原tracker旧模式201857状态/307680距离/1113搜索PASS。
- 事件/控制桥联合13项PASS；365帧诊断曲谱13接收/9回收/1247前沿下降、旧时间过期算术复现、reset/握手字段稳定PASS。
- 最新音画隔离TB：14项、881249周期、845音频帧、799非零帧、75模式变化PASS；真实50MHz/48kHz/31250MIDI及25/125MHz，音频逐周期与原顶层一致，视频停钟/PLL失锁和复位无仿真欠载。该TB缩屏64x48，仅行为快测；PnR始终完整640x480。
- 仓库check_repo全PASS，git diff --check PASS；新checker反例和原4种报告篡改测试均通过。

## 报告检查器的精确修正

首次新版report gate报“event_bridge Hold缺失/负”。实际Hold_Slack_Table1中ack_meta→ack_sync为+0.002ns，在全局Hold_Slack_Table8又出现一次相同的物理端点对。旧检查器合并所有表要求总共1条，因重复展示2条误拒绝。

check_visual_full_path_report.py现按SDC_Report中每种分析的活动report_timing顺序定位其专用编号表，仍要求该专用表精确起止端点、1条路径且非负；不得拿全局表补专用表缺失。没有放宽/删除时钟、复位、载荷或false_path约束。

新增基于实际报告的反例：专用表删除（全局正路径仍在）、负余量、错端点、专用表内重复、专用命令失效5种都拒绝；同路径跨专用/全局展示正常接受。原全局Setup、音频输出延迟、payload最大延迟、计数器寄存器缺失4种反例仍拒绝。注入parser行只是标注的测试，不能当物理报告证据。

## 实际新Gowin结果

Gowin V1.9.11.03 Education / GW5AT-LV60PG484AC1/I0；原50MHz系统、25MHz像素、125MHz串行，8live+8score，全640×480/800×525；原有效CST/SDC和measured串行复位FF位置保持。

| 指标 | 屏底连续退出候选 |
|---|---:|
| Logic/Register | 16299/59904；5808/60780 |
| DSP/BSRAM | 24/118；8/118 |
| sys实际Fmax | 50.137MHz（目标50） |
| pixel实际Fmax | 25.242MHz（目标25） |
| serial实际Fmax | 1296.595MHz（不是更改实际输出频率） |
| 最小导出Setup/Hold | +0.055/+0.001ns |
| Recovery/Removal最小 | +1.087/+0.443ns |
| Setup/Hold端点与各clock TNS | 0/0、全部0 |
| event/score存活载荷 | 22/37路径，原10ns界限与后级门禁通过 |

24DSP说明本版整除位移路径消除了旧几何宽乘除，不是降低声部/停用音色。原音频8BSRAM/u_latency65FF、10音频脚和4对TMDS门禁保持。PR1014保留；余量仍小，不能声明板级长期稳定。未修改正式top/pkg/CST/接口/音频/公共桥。原报告第一次被旧脚本误拒绝有完整输出留存，正式判定是修正检查器后的同一实际报告，无需为更改报告检查逻辑重做PnR。

## 复现与哈希

工作树根目录：

```powershell
.\code\scripts\run_m3_visualizer_sim.ps1
.\code\tb\input\visualizer\run_renderer_geometry_equiv.ps1
.\code\tb\input\visualizer\run_tracker_timing_equiv.ps1
.\code\tb\input\visualizer\run_diagnostic_score_progress.ps1
.\code\scripts\run_visual_path_integration_sim.ps1
python -X utf8 code/scripts/prepare_audio_visual_probe.py --output code/output/bottom_exit_audio_visual_20261002 --vendor code/output/hdmi_link_probe/vendor
D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe code/output/bottom_exit_audio_visual_20261002/run_build.tcl
python -X utf8 code/scripts/check_audio_visual_probe.py code/output/bottom_exit_audio_visual_20261002
python -X utf8 code/tb/board/verify_visual_direct_report.py code/output/bottom_exit_audio_visual_20261002
python -X utf8 code/tb/board/verify_audio_visual_report.py code/output/bottom_exit_audio_visual_20261002
python -X utf8 code/scripts/run_audio_visual_probe_sim.py --prepared code/output/bottom_exit_audio_visual_20261002 --small-raster
.\code\scripts\check_repo.ps1
```

.fs SHA256 `1053cb5df2c55d5d50167b7952cbe8feb2f7dd08eb918cc4f388277135858e34`。
STA HTML SHA256 `7fc277bd19dcbaeeb17285a10be10d17ffe7e70b6523a41f645cd0a515fd85f2`。
原始output/bottom_exit_audio_visual_20261002/impl/pnr完整保留；该目录inputs/evidence/gate.json含45实际输入及38音频依赖、报告和行为日志SHA。候选.fs/manifest单独运输，待主M2独立复核再安排M3，不自行推送/烧录。

## 同版实屏动作（尚未执行）

确认码流哈希后SRAM临时测试并备好原V1+CC64音频回退，不写Flash。上飘初始从最底边，长按头部跨屏仍保持、松键条尾离屏；切下落模式，短音到达底边后连续退出，不再固定在400处；长条头先到线、尾按时长继续下降。正确击中底边闪光，错键不闪。至少持续20秒录制下落新音符进入/退出、四声部/踏板/复位恢复画面和声音。

模式输入仍自动诊断5秒请求、实际帧边界切换；曲谱还是diagnostic，不是SD卡/MIDI曲谱/真实歌曲。原视频未取得，不认定现场异常根因或本版实测已成功。本轮L2＋独立L5，正式top/整机/L6待。
