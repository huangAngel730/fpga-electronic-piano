# T062同步请求缓存新结构：独立40MHz实证交付

结论：独立模块L2/L3/L4/L5通过，未上板，未正式接入。
本文形成时未提交/推送；用户后续已要求上传GitHub，本次发布状态以
CACHE_PUBLICATION_20261010.md及最终GitHub提交为准，不回填原运行收据。
任务五路径/原05主动终止边界见CACHE_REVISION_AUTHORITY_20261010.md。
正式整机STA与统一登记归M2；本轮没有改共享四表/正式top/pkg/PLL/CST/SDC，
没有碰主对话2的T061 N8文件，也没有使用Git索引或任何设备编程工具。

## 新结构与保持合同

正文仍八lane同步双端口，公开A口一拍连续读，COMMIT同沿读旧bank，UART用B口。
512事件、双银行失败保护、非对齐128byte分包、原CRC/ACK/READ/重放/序号/超时不变。
新增512×8请求history ping-pong RAM；只保留24byte BEGIN字段并行寄存。
成功缓存只切bank，不再同沿复制138byte；duplicate比较读取同步RAM后再消费，
COPY_FETCH/COPY真实分拍读取payload。额外COPY等待最多128拍=3.2us，未延长协议超时。
新RAM无reset清空；cache_valid/元数据与body_compare_pending管理有效性。

第一次有效物理结果暴露复位输入与地址输入Hold路径后，增加真实核心释放围栏：
reset_ready每沿采rst_n，core_rst_n=rst_n&&reset_ready，断言仍同沿生效，
只将核心释放延迟一拍，原UART复位不变。两正文端口使用同一可逆prefix XOR地址编码，
bank不变，不加公开读拍，也不是仿真delay链/宽假路径/多周期/降频。

## 最终功能实测

最终目录code/output/m4_t062_cache_sim_20261010_02，ModelSim2020.4，40MHz/115200真实UART。
normal进程167.109s、exit0；完整runner还实际执行三变异和八阶段复位。

| 检查 | 实际结果 |
|---|---|
| 正常流程 | 731场景、710回复、710次独立管脚字节CRC |
| 原协议Python oracle | 574串行事件/1240公开快照/32负事务，exit0 |
| 每拍公开数据 | 89,083,073比较，其中并发89,081,833/非法或未发布44,092,905 |
| 定向覆盖 | COPY78/VERIFY4576/UART READ514，4次COMMIT同沿有效旧bank |
| 两容量与边界 | 1及512事件；首包1byte后128byte跨lane/偏移；并发读与失败保留旧谱 |
| 行为变异 | RAM地址/发布bank/回复CRC种子，编译均0，指定Fatal，非编译失败或超时冒充拒收 |
| 复位 | 原6阶段+COPY_FETCH+比较待消费，24复位沿及真实UART重新上传恢复 |
| 5s超时 | 原真实session定义保留，oracle记录199999649等待周期；未缩短测试常量 |

正常capture SHA256：104fa43a5121a4284e3ced1f559d0342576169e75cf38d7f92a2ff8390f3aa8f。
ModelSim指定Fatal在本-do配置下进程exit0，收据如实记录；负例同时要求指定断言且无正常END。
公开Golden由输入JSON独立组装，不读DUT RAM/bank作为期望；私有state仅用于覆盖/复位注入。
相同SHA的sim_01/02正例不表示两个版本没有变更，02源身份/负例/复位均另跑并保存。

## 最终综合与物理STA

最终目录code/output/m4_t062_cache_build_20261010_03。
GowinV1.9.11.03Education、GW5AST-138C/GW5AST-LV138PG484AC1/I0，独立top。
native综合11.032s/exit0/上限600s；PnR runner32.797s/exit0/上限900s，无自动重试。
原PnR报告内部统计placement5s/routing7s/生成8s/total20s；与外层runner计时口径分开。

| 原生结果 | 最终值 |
|---|---|
| 时钟 | sys_clk 25.000ns/40MHz，唯一运行域 |
| 实际生效保护 | Setup uncertainty1.000ns/Hold uncertainty0.650ns |
| Setup最差 | +7.654ns，超过>=0.5ns工程门槛及期望1ns |
| Hold最差 | +0.001ns，在650ps保护后；不冒称额外板级余量 |
| TNS/违例 | Setup0/0、Hold0/0，原生3774路径/4534端点分析 |
| 报告实际Fmax | 57.651MHz；不是综合估算，也不是许可提高系统频率 |
| 最小脉宽余量 | +9.346ns |
| 原生PnR资源 | Logic2437=2146LUT+291ALU，Register1316，BSRAM9/DPB9，SSRAM0，Latch0 |

综合XML为1316Register/2147LUT等价/266ALU/9BSRAM；不要与PnR口径混写。
旧实际综合3392Register/3624LUT等价/271ALU/8BSRAM；本次减少2076FF，新增1请求BSRAM。
不是相同约束/源码的单变量A/B：新工程另有1ns/650ps保护与地址/释放围栏。
正文八lane仍各1BSRAM，请求history另1，逐模块XML与native memory日志齐套。
DSP原生此报告未列，不能因此写0。9条EX3791保留在原日志，不宣称零警告。
对应reply索引<=33、CRC位索引<=31、body<=138、event_count<=512、copy_pos<=129、
received<=4096/写有效地址<=4095等边界沿原协议，16bit序号回绕不擅自改变。

Recovery/Removal原表为空：四个staged源所有顺序event control均为posedge clk，
原UART和候选均同步reset，无异步FF复位域，审核明确分类为本模块不适用（slack=null），
不是“Recovery/Removal=0ns”，不能沿此结论豁免整机异步复位/CDC。
本GowinCLI无report_timing命令、原报告无unconstrained-count栏（只读probe原日志已封存）。
审核器不编造原生count=0；另完整匹配131个native虚拟端口、12data输入及118输出
max/min delay均Actived、单clk/无派生clock的staged拓扑、无false/multicycle/clock-group例外，
作为本单时钟虚拟环境的显式覆盖分类，原生未约束count仍null。
实际约束/报告SHA、解析器/审核器快照、11项审核自测和原日志见sta_review.json及audit目录。

## 所有失败原样保留

旧m3...build05用户主动终止，13787.109s/native4294967295/timed_out=false，
FAIL_INPUT_CHANGED是共享登记后验身份问题，不是新的RTL错误；不恢复旧定时计划。
新cache_build_01综合通过但uncertainty作用对象语法TA2000，未进放置布线；修正-from/-to，保护不变。
新cache_build_02首次有效PnR完成但Hold12/TNS-7.826ns/最差-0.797ns，明确不通过，
按11个CRC同步reset和1个BSRAM地址实际端点才做上述定点修复，不换seed重跑。
新cache_build_03才是通过的版本。所有旧收据/日志/原fs均隔离保留，不回填。

## 可重复入口与交付

所有命令使用现有E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe，
前缀-B -X utf8，在仓库根目录执行，全新输出路径不可覆盖：

```text
code/scripts/run_m3_score_transfer_bram_acceptance.py --output code/output/NEW_SIM --timeout 1800
code/docs/hardware/score_transfer_bram_v1/timing_build.py synth --output code/output/NEW_BUILD --simulation-receipt code/output/NEW_SIM/receipt.json --structural-revision
code/docs/hardware/score_transfer_bram_v1/timing_build.py pnr --output code/output/NEW_BUILD --structural-revision --allow-isolated-unreleased-bitstream
code/docs/hardware/score_transfer_bram_v1/cache_delivery.py audit --output code/output/NEW_AUDIT --build code/output/NEW_BUILD
```

共享四登记SHA另存前后变化；所有功能/只读协议/接口输入继续严格逐件SHA，不删除保护。
runner源快照、工具身份、实际命令/stdout-stderr/exit、native产物SHA及失败证据完整保留。
仓库九门禁及准确前后输入变化由新gate收据记录，不借用主对话2结果、不称已提交树。
gate_01首次环境Python被WindowsApps别名抢占，Python语法/Reference exit9009、
依赖Python的三个T007基线失败；原6PASS/3FAIL收据保留。只将已用的现有Python目录
前置于门禁子进程PATH，启用UTF8/禁止pyc，再新gate_02；不改系统PATH/安装工具或修改公共脚本。
单一ZIP预定为code/output/m4_t062_delivery_20261010_01/T062_M2_HANDOFF.zip，
尚未生成，不得把预定路径当作已交付。cache_delivery.py提供seal/verify入口，
生成后才有内部PACKAGED_INPUTS.json逐成员SHA、外部manifest.json及ZIP本体SHA。
工具设计排除.fs/.bin/.binx及大物理数据库，现有隔离原件保留，未下载/烧录。
本次按用户新授权仅上传RAM源码/测试/工具/说明；ignored code/output原始证据不随Git提交，
共享状态及正式接入、新整机STA仍由主对话2/M2协调。
最高只本模块L5；整机共存、真实UART/BLE/播放/电平/CDC/引脚/上板/长期运行均未验。
