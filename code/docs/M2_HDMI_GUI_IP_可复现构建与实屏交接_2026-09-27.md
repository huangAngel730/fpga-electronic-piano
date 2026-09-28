# M2 HDMI GUI IP 可复现构建与实屏交接

日期：2026-09-27。范围：独立 `hdmi_link_probe` 的生成 IP 校验、构建及证据采集。主责 M2，自审。**本阶段已到 L5，未到 L6；本说明不授权改正式电子琴顶层或 M3 画面。**

## 一 已完成与剩余关口

- WorkBuddy 用本机 Gowin IP Generator 实际生成 DVI TX；生成文件、配置及日志由 M2 按 SHA-256 校验。该安装版为 DVI TX V3.0，已移除内部 PLL，配置没有像素频率选项；像素与五倍串行时钟来自外部。本探针继续使用 25/125 MHz，不能误填或改约束冒充 PLL 频率。
- `build_hdmi_link_probe.ps1` 增加 `-GeneratedDviIpDir`：先核验生成的 `.ipc/.v/.vo`、日志和 TLVDS 宏哈希；缺失或不同均失败，再在忽略的 vendor 副本编译 `.v`。保留默认原参考源码入口供历史复现；本次实屏应使用带 GUI 参数的入口。
- `snapshot_hdmi_link_evidence.py` 校验编译到 vendor 的 `.v` 与 GUI 生成文件一致，将 GUI 来源哈希与码流/报告哈希一起写到忽略目录的 `gui_ip_evidence.json`。原 `code/docs/evidence/hdmi_link_probe_20260927.json` 保持未改。本次冻结摘要见 `evidence/hdmi_link_probe_gui_ip_repro_20260927.json`。
- 两帧 640×480 行为接线仿真 PASS（复位、失锁、PA 关闭）；10 项报告检查器自检 PASS；篡改 IPC 会在创建构建目录前失败；完整 Gowin 综合/PnR/码流及引脚门禁 PASS；仓库 `check_repo.ps1` 全项 PASS。行为模型不能证明加密 IP 的物理 TMDS 输出。
- Gowin V1.9.11.03 Education / GW5AT-LV60PG484AC1/I0；Logic 365、Register 109、PLLA 1、OSER10 4；Setup/Hold 违例端点均 0；最差 Setup/Hold/Recovery/Removal 余量 +7.109/+0.275/+0.866/+0.284 ns。`PR1014` 参考时钟普通布线警告仍在；STA 通过不证明 PLL 实物锁定或信号质量。
- 尚未执行烧录、AOC Q27B35 信号识别/画面/复位测试、音频与 HDMI 共存；不是双模式功能完成，也不改变正式集成的 S5 门槛。

## 二 可复跑命令

在包含本次脚本改动的工作树根目录运行。官方 Sipeed 参考仓库仍固定为 `f0347d830305ef3efb921f47bb51701e569beefd`，只借用已锁定 PLL 模板和 LICENSE；GUI DVI 文件保留独立目录，勿覆盖官方参考源码。

```powershell
.\code\scripts\run_hdmi_link_probe_sim.ps1
python -m unittest discover -s code/tb/board -p test_hdmi_link_report.py -v
.\code\scripts\build_hdmi_link_probe.ps1 `
  -ReferenceRoot 'D:\Temp\Angel17\sipeed_mega60k_example_20260927' `
  -GeneratedDviIpDir 'D:\17\project_17\fpga_gowin\code\output\hdmi_ip_25mhz_staging\gui_generated_25mhz' `
  -Flow all
```

IP 来源哈希与此机器这次生成文件绑定；换机器重新生成后哈希可能变化，必须重新审核生成证据，不能把校验删除或随便改成新值。原始参考文件、生成文件和大型 `.fs` 不随本次提交入库。

当前隔离工作树：`D:\17\project_17\fpga_gowin\code\output\hdmi_ip_25mhz_branch`（detached，非功能分支）；共享 develop 的未提交修改未覆盖。集成脚本改动须由 M2 协调后进入 develop。

## 三 给 M3 的实物工作包

**待用户转发，尚未送达 M3。** 本交接是测试准备，不表示测试已安排或开始。M3 负责实物连接/观察/证据；M2 提供码流和技术判读。WorkBuddy 的 GUI 生成不代替实屏验证。

1. 先约板卡与屏幕测试时段，确认当前音频码流的准确恢复文件、提交及版本。不要直接用“最新 fs”代替已验证音频版本；若没有可确认的恢复码流，先暂停下载。
2. 用 HDMI 线连接 NEO Dock 的 DVI TX 输出与 AOC Q27B35 的 HDMI 输入，按屏幕菜单选择实际接入的 HDMI。按板级事实确认上电与 JTAG 正常；DVI RX 与 TX 不能同时使用。探针只输出视频，`pa_en=1` 关闭功放，不期待琴声。
3. 核对诊断 `.fs` SHA-256 与本次证据一致，SRAM 临时下载；本任务没有授权写 Flash。下载会替换 SRAM 中音频逻辑，测试后恢复已确认的音频码流。
4. 正常结果：屏幕识别信号，出现固定蓝灰色（RGB `20 40 80`）。诊断实际为 640×480 / 25 MHz / 约 59.524 Hz；不是屏幕原生 2K120 Hz。记录屏幕 OSD 输入信息、画面照片/视频和下载日志。
5. 用板上用户键 **EX_KEY.0**（AA13 的低有效输入，本探针作为复位）执行复位/松开检查，记录画面能否恢复。不要用 RECONFIG 替代这一检查。若不能辨认实际按键，先请 M2/用户核对丝印，不外接 3.3 V 驱动 AA13（此 Bank 为 1.5 V）。
6. 若无信号、花屏或恢复失败，保留原始现象和连接信息，交 M2 分析；不擅自改变 Bank 电压、引脚或修改 SDC 来掩盖违例。记录恢复原音频码流后的结果。

当前诊断文件（这次构建）：

```text
D:\17\project_17\fpga_gowin\code\output\hdmi_ip_25mhz_branch\code\output\hdmi_link_probe\impl\pnr\hdmi_link_probe.fs
```

SHA-256：`ce9560cbe6bf3bea38bbcb7c01ba7162c238c01cf70b828e3bd636f8369ef239`

从该隔离 worktree 根目录执行（先完成恢复文件确认与实物协调，下面仅提供命令，M2 此轮未运行）：

```powershell
Get-FileHash -LiteralPath '.\code\output\hdmi_link_probe\impl\pnr\hdmi_link_probe.fs' -Algorithm SHA256
.\code\scripts\program_electronic_piano.ps1 -Mode sram `
  -Bitstream 'code\output\hdmi_link_probe\impl\pnr\hdmi_link_probe.fs'
```

通用下载脚本最后可能打印“440 Hz”提示，那是音频设计的默认文案，不是 HDMI 探针预期，不能据此判断本探针声音异常。本轮不改通用音频下载脚本。

## 四 M3 回报格式

- 码流 SHA-256、源码/提交（若未提交须注明）、下载方式、下载日志；
- 板卡/底板和屏幕、端口/线缆、OSD 信号信息；
- 蓝灰画面：通过 / 失败 / 未测，附照片或视频；
- EX_KEY.0 复位与恢复：通过 / 失败 / 未测；
- 测试结束恢复的音频码流文件、版本和结果；
- 现象和未测项。只有实际测过且证据可核对才记录独立探针 L6；不表示音画共存或双模式验收。
