# N32-D 精确资源工程准备入口

当前完成 **L0/L1 静态／软件准备**，不是综合 L4 或物理时序 L5。
实际资源 UNKNOWN，STA NOT_RUN，完整 T061 保持 PARTIAL。
最新结果见 `RESULT_20261014.md`；本轮尚未提交／推送 GitHub。

## 工程与边界

`prepared/N32_R1_20261014_R02/` 为本机冻结工程：19 个 HDL 文件，包括 B 实际通过封存
中的 18 个业务源原字节，以及新的资源顶层 `m3_n32_resource`；另有 2 个 include、5 个
冻结 ROM 来源、A/B/C 身份／结果依据。所有 45 个输入文件及清单均有 SHA。

资源顶层直连 `b_n32_event_audio_prom #(.N(32), .RESPONSE(1))`，保留准确 clipped、
事件／采样／结果握手和公开读口，注入固定关闭。仿真兼容 wrapper、变异宏、TB 和
`prim_sim.v` 不进入综合源。该资源顶层只完成静态接线检查，未做新的 RTL 执行。
B wrapper 的正常结果六信号是原业务模块直通，不据此扩写新 top 已仿真。

固定器件：`GW5AST-138C / GW5AST-LV138PG484AC1/I0 / gw5ast138c-007`。
GPRJ 启用唯一 `clock.sdc`，Tcl 引用同一 GPRJ、顶层及 include 路径：25.000 ns／40 MHz、
Setup 1.000 ns、Hold 0.650 ns。无 CST、板级 I/O 或完整 reset STA 结论。
`synthesis_default_frequency_mhz=100` 只是同版工具历史默认报告口径，不是新报告；
SDC 传递正确不等于工具实际采用后已经满足物理时序。

用户明确指定的工具根为 `E:/FPGA/GAOYUNFPGA/138K/tools/gowin_1_9_11_03`。
8 项主工具与可信旧工具收据核同，另固定 `IDE/bin/**` 和目标器件数据目录的 1201 文件
库存，摘要 `b99201ced24fbf9023a10e8ddd466bbad9951327c56d54a29ae9ef8a8802394a`。
这只是静态身份，不证明动态加载或许可证。工具二进制不放入交付 ZIP。

## 可用命令（只准备，不执行 EDA）

在仓库根目录用现有 Python；已有结果不需要重跑：

```powershell
python -I -S -B -X utf8 code/build/138k_polyphony_resource/m3_n32_allocator_candidate_20261013/prepare_d.py verify --project code/build/138k_polyphony_resource/m3_n32_allocator_candidate_20261013/prepared/N32_R1_20261014_R02
```

需要在另一机器准备时，使用 `prepare --project <本目录prepared下全新ASCII目录>
--tool-home <同版实际工具根>`，产生新的机器／路径绑定和新 manifest。
不得把旧绝对路径或当前机器收据冒作另一机器实际核验。
`run_d_checks.py` 只运行新的纯软件准备检查，并保留逐步实际 argv／退出码／预算／SHA；
单步 90 秒、总 900 秒，输出和工程必须全新，无自动重试。

`prepare_d.py execute` 总是退出 1：`D_NEW_EXACT_SYNTHESIS_PERMISSION_REQUIRED`。
该文件没有任何 Gowin 启动实现，不能自行改 authorized 恢复旧额度。
`run_synthesis_only.tcl` 仅为未来 M2 接手的最小配方，**本轮未运行，不要直接运行**。
正式执行需要 M2 确认新精确候选与有效许可；PnR／STA／设备操作不包含在 D 准备中。

## 交付

`SEALED_PREPARED_RESULT_R02/snapshot.zip` 含工程、工具静态身份清单、完整软件收据、
检查器／反例测试、自审／说明和历史准备。接收方可只读核 ZIP，不依赖项目工具：

```powershell
python verify_delivery.py --zip snapshot.zip --manifest MANIFEST.json --seal seal.json --seal-sha <可信通知中的seal文件SHA>
```

该验证只读归档成员，不提取或执行归档代码；不替代 M2 最终签收或综合准入。
新的精确工具运行、正式接入、资源和 STA 仍归 M2。
