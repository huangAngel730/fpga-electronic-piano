# R6-1 source_target_audit 交付

实现及本轮软件自审完成；真实闭包仍PARTIAL。工具新软件用例为L1合成/纯文件验证，真实来源装配仅L0，不签Pro数字链、编译、物理或板测。board_release_allowed=false。

## 实际结果

- RUN_01：15新软件例通过，退出0，1.328秒，timeout=false，输入前后SHA同。该版在实际原包自审中有词法解析误报，不称无缺陷版本；frozen与所有错误输出保留。
- RUN_02：唯一获准最小修复组，7定向例通过，退出0，0.843秒，timeout=false，输入前后SHA同。只修紧贴位宽端口、宏端口待展开、函数误判实例和ROM参数默认语义；没有重跑原15例或旧来源checker六例。
- 子进程实际2次，均纯Python；审计函数15+3原包、7+1原包，共26次调用。HDL/Icarus/ModelSim/Gowin/设备0次。独立CLI main未作为子进程另跑，已运行其核心audit/write_result路径。
- 当前实际原包加wrapper：70单元、72模块、82词法实例、9ROM/4IP/2约束清单；输出source-list.f、RESULT.json、MANIFEST.json及原字节stage在RUN_02/cases/real_incremental。
- 新解析器剩余MISSING_MODULE:dds_oscillator：定义在封存source_closure/inputs/sources/dds_oscillator.sv，但不在原69项列表；polyphonic_envelope_bank.sv:130调用。本工具检查全列模块，不做顶层可达性/条件generate展开，不能说已证实生产编译失败。留给M2决定精确列表，不擅改旧闭包。
- 模拟时钟/DVI、宏、动态ROM/覆盖参数均如实列待决。physical_status=PENDING_PHYSICAL_ID；真实Part/version/板/Bank/Pro PLL未核。stage含旧物理候选只是原件保留，不是物理清单PASS。

## 实际运行命令（repo cwd）

```powershell
C:/Users/songdongkuan/miniconda3/python.exe -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/source_target_audit/run_once.py E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/source_target_audit/RUN_01 E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/source_target_audit/real_config.json
C:/Users/songdongkuan/miniconda3/python.exe -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/source_target_audit/run_once.py E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/source_target_audit/RUN_02 E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/source_target_audit/real_config.json --repair
```

两组各有PLAN（实际argv/cwd/UTC/机器/源码/输入/Python/已加载标准库/DLL SHA）、frozen、原stdout/stderr、CASE_PLAN、逐例JSON、SUMMARY、RECEIPT（产物SHA与退出码）。不是全部操作系统DLL闭包证明，标准库以实际加载文件记录，未安装任何工具。运行前只读找新目录不存在产生过PowerShell退出1，不是仿真/测试失败。

## 交接与未完成

M2接手选择/签真实同版source-list，确认未列dds引用是否可达或应补入，冻结Pro Part/PLL及后续M1/M2 R06候选。未来候选以显式path/SHA/stage_as/replaces摄取，当前candidates为空。复杂宏/生成分支/端口位宽和实际依赖需精确工具准入后确认，本工具不代授权。

本次未创建TB（不需要HDL操作），只写指定software与docs/test的source_target_audit目录；未修改冻结源、算法、ROM、共享top/CST/SDC/表、旧B1/B2/D3或其他窗口成果。未Git add/commit/push，交总控统一发布。实物能力本轮未检测，不声称已核有板或可下载。
