# T058 reset_hold_v3

2026-10-09：原v2精确工程RTL/ROM/PLL/CST/GSC不变，新增SDC只追加4个严格from/to reset_sync CLEAR异步入口例外、定向原audio短路径set_min_delay0.200与6个D路径报告，保留40/25/125MHz和650ps Hold保护门槛。原目录和旧失败收据不可覆盖。

运行前必须有新reset合同自检和scope/resource负例预检。新reset TB覆盖64phase、pixel/audio停钟、overflow/flush/旧包不复活，原RTL数字合同5335checks通过，两编译行为反例指定assert拒收。首轮反例label和preflight替换空格错误均保留，不算通过证据。qualified27项门禁拒降hold、broadfalsepath、Dpin cut、资源错及oldv2报告等。

新资源profile严格23BSRAM/89SSRAM/DSP46：audio20BSRAM/32SSRAM，wave3BSRAM/0SSRAM，observer0BSRAM/28SSRAM；工具实际需再次符合，不改v2门禁追认。

准备：`python -B -X utf8 code/scripts/prepare_138k_waveform_integration_v3.py --output code/build/138k_waveform/<NEW>`。
自检入口：`run_138k_waveform_reset_contract_v3.py`、`test_138k_waveform_integration_v3.py`仅独立预检，不program。当前实现输出qualified固定独立目录，已存在即拒，不能直接重复覆盖旧结果。
构建：`run_138k_waveform_integration_once_v3.py --output code/build/138k_waveform/runs/<NEW> --simulation-receipts <all9qualified_old_logic_receipts> --reset-contract-receipt <newqualifiedreceipt> --preflight-receipt <newqualified27receipt> --timeout-seconds 1800`。旧9逻辑因RTL不变核SHA仅复用，新reset自检独立执行；不声称再跑全部旧仿真。
验报告：`check_138k_waveform_integration_build_v3.py <run>`。全部旧pin/clock/LOC/Setup/Hold/Recovery/Removal/pulse/TNS/fmax/CDCbus/二段/无latch检查保持；追加精确SDC命令白名单、四CLEAR裁剪对象、6局部D路径及SSRAM实量。缺report/任一负值或额外例外非零拒收。

本版本一次完整run，拒overwrite/不自动重试/no烧录。是否L5以实际新STA全部门禁为准，异步入口例外不替代物理亚稳态/MTBF/硬件测量。本README准备阶段不宣称构建通过。

## 实际结果补充

唯一Gowin388.900s/tool0完成；原集成checker1因旧false-path集合未认识4reset例外，原记录保持。独立最终`check_138k_waveform_integration_v3_final.py`在同份报告上全门禁0：Setup+1.846/Hold0/Recovery+0.938/Removal+0.002，严格局部表与27preflight/11报告坏例通过。离线L5按此精确组合通过，不允许下载；Hold/Removal紧，无新增硬件证明。后续复验请用final入口，不修改原checkerSHA或重复旧run。详见结果复核报告。
