# M3 等待 M2 期间的五项准备交付

2026-10-05；全部新增脚本、工作副本、工具输出在 `E:/FPGA/GAOYUNFPGA/138K_try`。原正式仓库保持只读；没有提交号、推送、正式文档更新或烧录。以下是已经实际执行的结果，不是完整 V0171 复现结果。

## 1. 工具链验证：三个独立小工程完成 PnR

Gowin 实际报告版本：**V1.9.11.03 Education**。8 位计数器工具探针，单一 50 MHz 时钟、同步复位、自动引脚，没有视频 PLL、DVI、DSP 或 BSRAM 功能。三个工程均实际完成综合、布局布线、STA 和码流生成，CLI exit 0。

| 工具探针目标 | Device ID / PN | Setup / Hold 最差余量 | Logic / Register |
|---|---|---|---|
| 60K B | gw5at60b-002 / GW5AT-LV60PG484AC1/I0 | 16.905 / 0.033 ns | 8 / 8 |
| 138K B | gw5ast138b-011 / GW5AST-LV138PG484AC1/I0 | 16.618 / 0.030 ns | 8 / 8 |
| 138K C | gw5ast138c-007 / GW5AST-LV138PG484AC1/I0 | 16.618 / 0.030 ns | 8 / 8 |

Setup/Hold TNS 与违例端点均为 0。Recovery/Removal 没有异步复位路径，记 **N/A**，不能写为完整设计通过。小工程探针对应实际完成布局布线/时序阶段，但不能推广为完整 V0171、IP 组合或硬件通过，也不能用这些余量判定更换 138K 是否改善整机时序。**生成的 tool_probe.fs 不得用于上板。**

证据：`toolchain_results.json`、各目标 `toolchain/*/impl/pnr` 原始报告和 `build*.log`；探针自检 `tool_probe_sim.log` PASS。

保留了失败过程：60K 首次 STA 因 uncertainty 的 Gowin 方言语法失败，原始 `build.log` / `build_attempt1_sdc_syntax.log` 保留；只修正本探针 SDC 后 `build_attempt2.log` exit 0。探针 Setup uncertainty 为 0.500 ns、Hold 为 0.550 ns；这不是替换完整冻结 SDC 的依据。

## 2. 冻结输入路径搬迁：完成，未改设计逻辑

- 55 个物理文件（46/47 项工程输入，加 7 个 ROM、2 个头文件）重新核对旧 SHA 并复制到 `relocated_bundle`。
- 仅替换 20 处 ROM/include 路径字面量；非路径内容相同，所有可见数据引用指向隔离副本。
- 原证明包保留不动；CST、SDC、ROM、头文件逐字节不变。冻结 SDC 保持 50/25/125 MHz、sys Setup uncertainty 1.000 ns、Hold uncertainty 0.550 ns。
- `relocation_manifest.json` 保存每个原/新 SHA 和替换位置；它不是 M2 原 V0171 最终 manifest。
- 未生成完整 V0171 可运行 GPRJ；仍缺原 `DVI_TX_Top.v` 和原运行元数据。

## 3. 138K 适配差异核对：静态清单完成，正式迁移未做

详见 `138K_compatibility_review.md`。按 PDF 技能核对本地原理图全部 7 页渲染；编码异常的提取文字未作为电气依据，未上传资料。

主要发现：138K 原理图 AA13/AB13/Y12 在 Bank5，供电 3.3 V，与冻结 60K 的 LVCMOS15/1.5 V 声明不同。已记录风险，**没有生成最终 138K CST、改引脚或改电压声明**。目标底板接线/上拉、实物 B/C、视频 PLL/DVI 物理兼容和复位固定坐标映射仍须核实。不能直接复制参考 CST 或删除固定位置约束取得通过。

## 4. STA 结果收集器：20 项自检 PASS

`collect_sta_results.py` 读取真实 HTML/文本报告并保留工具/器件元数据、时钟、最差路径、TNS、违例端点和资源；实际三探针报告收集通过。仅复用了字节可追溯的 HTML 解析器，不复用旧的 Hold 0.500 ns / BSRAM 8 验收阈值。

`test_collect_sta_results.py` 的 20 项正/负例全部 PASS，包括负 Hold、跨时钟负路径、NaN、Recovery 缺失、Removal 负值、时钟缺失/重复/频率错误、TNS/资源/元数据缺失、旧 uncertainty、约束失效和宽泛时序切断。测试夹具不是实物报告。

收集器仍不是完整引脚/CDC/IP/硬件验收门禁；完整工程到件后要结合原运行选项和全部有效约束、例外端点、脉宽等项目继续验收，不允许据当前 JSON 将 V0171 标为通过。

## 5. 冻结模块功能回归：7 组全部 PASS

工具：隔离副本 **Icarus Verilog 14.0 (devel), s20260301-474-g5591c2dde-dirty**。原仓库仅用于读取/复制 8 个现有 testbench/对照文件，未执行原仓库脚本；DUT 取冻结路径副本，没有改逻辑，没有重写 testbench。

| 用例 | 实际结果 |
|---|---|
| debouncer | 全部检查 PASS |
| public_fifo | 11 检查 PASS；覆盖满队列旁路 |
| midi_cc64 | 2058 事件 / 4134 检查 PASS；16 通道、128 值 |
| midi_uart | 44 检查 PASS；UART 至事件链路 |
| counter_d3_l2 | 100620 检查 / 20114 拍 PASS |
| counter_d4_l4 | 100770 检查 / 20144 拍 PASS |
| counter_d32_l4 | 102170 检查 / 20424 拍 PASS |

三种计数器参数均逐拍等价，并由负例证明取消公共 FIFO 满队列旁路会被拒绝；包括饱和/进位边界、复位和随机压力。这里是模块自检仿真阶段，不是整机音画仿真或实屏 L6。所有 compile/run exit 0，详细命令、文件 SHA、结果和日志 SHA 在 `frozen_regression_results.json`。

Icarus 首次探针编译遇到 Windows DLL 解析失败（-1073741701），首次日志保留；用工具副本 bin 放到子进程 PATH 首位后成功。未修改系统 PATH、驱动、ACL 或安装工具。

## 可重复执行命令

在本目录执行；已有运行日志保留。重新运行结果收集/回归会覆盖本目录相应结果，须先保存需要保留的旧证据。不要在正式仓库运行这些准备脚本。

```powershell
$prepPython = 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $prepPython .\test_collect_sta_results.py
& $prepPython .\collect_sta_results.py
& $prepPython .\run_frozen_regression.py
& $prepPython .\verify_preparation.py
```

三种工具探针的原命令为各自目录执行隔离版 `E:/FPGA/GAOYUNFPGA/138K_try/tools/gowin_1_9_11_03/IDE/bin/gw_sh.exe run.tcl`；只允许用于这些工具探针，不能冒充冻结项目运行。

`verification_receipt.json` 为收口重新核对后的证据完整性回执，检查 55 原件 + 55 搬迁文件、24 个工具报告/产物 SHA、7 组回归日志及自检日志；不会重新运行 EDA 或写原仓库。

## 下一阶段及 M2 交接

可转发消息在 `M2_准备阶段交接.md`，**待用户转发，尚未送达**。

M2 须将原 DVI IP、原 V0171 manifest、实际工程/完整运行选项及原报告打 ZIP **直接发给用户**，附清单和 SHA；不是写入用户本机路径。收到核对后先跑完整 60K 控制组，再按有依据的副本适配跑 138K B/C；保持冻结功能、50/25/125 MHz 和 sys Hold 0.550 ns，不放宽 SDC。当前不能提供整机 PnR 对比或判定 138K 优势，未上板、未烧录。
