# 138K 完整音画工程物理优化结果（2026-10-05，M3）

结论：第四组 `C_reset_route1` 在完整 V0171 四声部音频＋HDMI 工程中实际综合、PnR、STA 完成，严格离线时序门禁 PASS。不是只运行小计数器，也没有删掉 HDMI 或音频。
这是精确隔离版本的工具侧 L5；Setup 仅 +0.025 ns，Hold 报告 0.000 ns，不满足 +0.5 ns 工程余量目标，不作为稳定发布或上板许可。未烧录、未实屏、未新增 L6。

## 实际对照结果

同一 Gowin V1.9.11.03 Education，GW5AST-LV138PG484AC1/I0、Device Version C；50/25/125 MHz。
系统 Setup uncertainty 1.000 ns、Hold uncertainty 0.550 ns保持，全部 SDC 与此前冻结版本逐字节一致。

| 完整工程配置 | Setup ns | Hold ns | Recovery ns | Removal ns | Setup/Hold违例端点 | 门禁 |
|---|---:|---:|---:|---:|---|---|
| 此前138K C迁移基线 | -1.356 | -0.348 | -1.411 | -0.152 | 196 / 2355 | FAIL |
| C_place2_route1 | -1.405 | -0.404 | -1.419 | -0.148 | 80 / 2611 | FAIL |
| C_place2_route2 | -1.405 | -0.404 | -1.435 | -0.148 | 81 / 2482 | FAIL |
| C_reset_location | -0.179 | -0.352 | -0.090 | -0.163 | 21 / 2296 | FAIL |
| **C_reset_route1** | **+0.025** | **0.000** | **+0.873** | **+0.008** | **0 / 0** | **PASS（余量薄）** |

四次均从 RTL `run all`，真实 CLI 退出码0，完整综合/布局/布线/STA/码流/功耗报告完成。前三次退出码0但时序FAIL，完整保留失败证据，未覆盖旧目录。

时间均为北京时间：

- C_place2_route1：15:21:57—15:25:39。
- C_place2_route2：15:26:11—15:29:25。
- C_reset_location：15:30:36—15:34:24。
- C_reset_route1：15:36:16—15:39:49。

## 有效变更：两条固定位置＋一个布线选项

相对 `reproduction_20261005/138K_C_electrical_migration`：

```text
u_visual/u_serial_reset/sync_chain_0_s0 : R49C101[1][A] -> R44C168[1][A]
u_visual/u_serial_reset/sync_chain_1_s0 : R49C101[1][B] -> R44C168[1][B]
route_option                          : 0 -> 1
place_option                          : 0，不变
correct_hold_violation                : 1，不变
```

新坐标来自此前138K实际报告中DVI编码器 `dout_6_s0/dout_0_s0` 所使用的合法 FF 资源，而非沿用60K坐标推算或删除固定约束。
第四组STA中两级复位位置分别回读为 R44C168[1][A/B]，与新CST一致。
官方本地 `IDE/data/config/rtlrouteoptions.xml` 指明 route_option1 按时序布线；布局选项2依据 `rtlplaceoptions.xml` 为时序优先，但前两组本工程中未取得收益。

RTL仅路径重定位，不改逻辑、公共接口、算法、FIFO、ready/valid、计数同拍语义或复位释放拍数。全部47项工程输入及7 ROM/2头文件，共56个物理文件均逐个核对；每组留 input_manifest.json。
SDC不改、不降低频率、不降低Hold guardband、不添加宽泛false path。引脚球位、电压、PLL位置与此前已审查的138K迁移副本相同；本轮不另行改电气设置。

注意：本轮基线已包含此前138K PLLA→PLL实验适配、三个Bank5输入电气声明适配和器件VCCX1.8V选项。它不是原60K工程直接换料号的结果；原60K、M2包、旧迁移失败记录均保持不变。

## 通过候选的报告事实

- 系统Fmax 50.062 MHz，像素37.877 MHz，串行1101.928 MHz；实际时钟仍50/25/125 MHz，Fmax不是工作频率。
- 三时钟域 Setup/Hold TNS均0，Setup/Hold违例端点均0。
- 像素Setup/Hold +13.599/+0.275 ns；串行 +7.092/+0.370 ns。
- Recovery +0.873 ns，Removal +0.008 ns；最短脉宽门禁通过。
- 7组CDC后级14条Setup/Hold路径和两类载荷存活23/50条路径均实际检查，不是仅看到约束Active。不能据此宣称未经优化的完整64/98位均存活。
- 引脚表按实际表头回读、电压/Bank/球位/差分配对检查通过；PnR选项与预先声明的精确profile一致，器件配置与138K基线一致。
- Logic19531/138240，Register8674/139095，DSP46/298，BSRAM20/340。
- PR1014 `sys_clk_d`通用布线警告仍在，不通过改脚或删约束消除。

## 功能及证据检查

25项报告验收器自检PASS，包括错误配置、资源/引脚/CDC、NaN/负余量、非法Hold修复关闭及非预声明布线选项拒收。
原冻结七组功能回归实际重新运行PASS：去抖、公共FIFO、CC64 2058事件/4134检查、MIDI UART44检查、按键计数三深度共303560检查。
三深度覆盖同拍计数、满队列pop旁路及无旁路反例拒收。回归实际DUT取自 `C_reset_location`；最终通过版本对应所有被测DUT字节SHA一致，由最终核验器确认，不冒称重新跑过完整音频/HDMI行为仿真。

`verification_receipt.json` 区分证据完整性PASS、第四组时序门禁PASS、+0.5ns工程余量FAIL、无实物验证；同时核对旧对比原始24个报告/日志哈希仍一致。
初次证据核验器预设四组均FAIL，第四组实际PASS时按预期停止并要求更新结果分类；已改为明确核对前三组FAIL、第四组精确余量PASS，未降低门禁。

## 文件与重跑入口

本目录：experiment.py、assess.py、verify_evidence.py、replay_regression.py、results.json、各profile工程及原始日志/报告、功能回归、报告自检日志与本说明。旧证据目录不写入，正式仓库不运行Git或check_repo，不提交、不推送。

本机最终核对：

```powershell
& 'C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -X utf8 E:/FPGA/GAOYUNFPGA/138K_try/optimization_20261005/assess.py --selftest
& 'C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -X utf8 E:/FPGA/GAOYUNFPGA/138K_try/optimization_20261005/assess.py
& 'C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -X utf8 E:/FPGA/GAOYUNFPGA/138K_try/optimization_20261005/verify_evidence.py
```

experiment.py 每个profile只允许一次，已存在则拒绝覆盖；回归入口也拒绝覆盖旧日志。如需重构建，应明确另建隔离目录并重定位文件路径，不在已完成工程重复 `run all`。
交付ZIP为源工程和报告证据包，排除fs/bin、体积庞大的pr/vg、工具与临时文件。构建Tcl含本机绝对路径，其他机器必须先合法重定位，核对依赖/工具再运行；验收脚本依赖此前只读证据与报告解析器，不宣称ZIP解压即独立一键复跑。

## 后续边界

M2先复核有效两条INS_LOC和route_option1，确认实际138K器件版本/板卡电气与PLL GUI配置及启动策略，再决定是否另做工程余量优化。此L5只绑定第四组精确V0171版本，不覆盖新版面板/双音色/效果器或32声部，也不沿用到后续组合。
不把Hold0.000写成+0.5ns，不能证明长期硬件稳定。稳定发布、GUI PLL检查和同版上板必须另行安排。
