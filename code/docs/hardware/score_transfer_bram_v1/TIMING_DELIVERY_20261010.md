# 曲谱 RAM 独立候选：40 MHz 时序修复

本修版基线27e1fb2，用户新增授权见TIMING_AUTHORITY_20261010.md。
原交付DELIVERY_20261010/EVIDENCE_20261010及其失败结果保留，不回填。
只改原五个RAM候选路径；不改生产top/pkg/PLL/CST/SDC、接口/协议、共享表或其他任务源。
共享状态与编号按本轮任务单留给M2统一登记。
本轮执行期间fetch发现M2已推送11个新提交，最新ab8f4e1正式登记RAM任务T062/D045。
远端实际候选/仿真与构建依赖/授权五路径均无重叠，原共享四表由M2追加。
本时序修版及隔离PnR依据用户另外明确授权，不冒称已获M2正式接入签收。
发布时采用普通同步，保留队友提交；旧证据中的四表SHA仍是实际执行时的原值，
不回填为新表SHA。最终转交收据单列M2四表导入身份，所有实际功能输入须保持一致。

## 实现与合同

原响应CRC在单周期组合展开22/30 byte。现在先快照回复字段，新增FETCH/STEP/FINISH，
byte选择器和单byte CRC之间有真实寄存器切分；短回复增加45拍、READ回复最多61拍，
40MHz下设计上限1.525us。最终CRC写入后才进入原RESP发送/精确重复回复缓存路径。
这是结构推导的延迟界限，不冒充单独测量结果。
session计数和原RESP异常优先级保留，快照后不被新RX错误或超时打断；同步复位优先。

第一轮新综合后，PnR原生PA2122拒绝DPB read-before-write模式。
最小器件映射修复：私有B口写周期读输出保持，真实B读仍同步一拍。
控制器只在VERIFY/READ读阶段消费B值，COPY写阶段不消费；A口及双银行隔离未改。
未使用未经核实的截图属性、假路径、多周期、低于40MHz的频率或删除断言。

公开rd_req/rd_index到rd_valid/rd_event依旧一拍且可连续，COMMIT同沿读取旧银行；
512容量、非对齐分包、线上字节/序号/ACK/READ语义不变。没有增加公共ready。
CRC流水线不用于音频生产链，整机上传时声音共存仍需M2后续集成验证。

## 复现及原始证据

最终仿真使用全新code/output/m3_score_bram_timing_sim_20261010_02。
第一轮流水线仿真sim_01及不支持DPB模式的build_01原证据一起保留。
build_02原生布线实际900.781s超时，退出1；保留原收据，不构成物理STA通过。
用户授权的一次同源同配置1800s追加构建使用全新build_03目录。
2026-10-10 11:48恢复检查时，该构建的会话及原生进程均已不存在，
stdout停在Routing Phase 1，没有最终STA报告；receipt仍为综合完成状态。
中断/终止的具体原因、实际退出码和运行时长未获独立确认，不伪造超时或退出码。
观察及日志SHA另存build_03/resume_observation_20261010.json，原收据不覆盖。
因此本修版目前只完成仿真及综合估算，40MHz物理时序尚未证实；
再次启动需要用户追加授权，不把“继续”解释为突破原来仅一次追加构建的限制。
已向用户明确提出同源同配置1800秒重启请求；用户随后确认“请继续”。
本次在全新build_04目录执行，源码/工具/SDC/选项与03一致，
runner另绑定03中断观察SHA及02原超时收据SHA，不覆盖任何旧记录。
04实际综合15.172s、退出0；PnR于12:45:50启动，1800.594s达到限时，退出1、
timed_out=true。仅有放置完成及Routing Phase 1完成标记，没有最终STA或.fs。
最终独立审计为INCOMPLETE_PHYSICAL_STA，L2/L3及L4成立，L5未完成，
40MHz物理时序目标尚未闭合；Setup/Hold/Recovery/Removal/TNS/物理Fmax均UNKNOWN，
不能用综合估算94.910MHz替代，不能写成0违例。

用户要求区分卡住与时间不足。两次各40秒只读采样中，CPU分别增加39.8125及
39.671875秒，但原生阶段/输出文件均未更新；详见04/progress_check_01及02。
故可确认原进程持续计算，不能确认算法收敛进展，也不能确诊死锁或路由拥塞根因。
未满足“有可验证进展、仅时间不足”的延长条件，不再自动追加同配置试跑。
13:16超时后独立进程检查无gw_sh或本runner残留。旧03终止原因依旧未知。

建议M2下一步先审查原工具细粒度路由诊断/独立I/O放置与高扇出情况，
结合本实际命令的route_option2/place_option3/correct_hold1确定单一受控试验，
再批准更长上限或单变量路由配置；不预先把任一项认定为根因，不在本轮擅自实施。
实际各步命令、路径、工具/源码/配置/产物SHA、原stdout/stderr、退出码及超时记录见receipt。

最终ModelSim 2020.4正常仿真164.265s、退出0；731场景、710回复均通过独立UART CRC，
原Python协议oracle比较574条串行事件和1240条公开快照，32个负事务；
公开读89,083,006次、并发89,081,766次、非法/未发布44,088,176次，
COPY96/VERIFY4576/UART READ515次覆盖、4次COMMIT同沿有效旧银行读。
RAM地址/银行/CRC种子三项编译成功变异分别按指定行为断言拒收，
COPY/VERIFY/READ/最终发布前沿及CRC FETCH/STEP六阶段、18次复位沿和真实上传恢复通过。
正常capture SHA256为7804da4a53adc293964d0a0a7f910a78e294b0367514d355dab88d08fa1ecdbf。
仿真Fatal的实际进程exit0仍如实记录；负例判定要求指定Fatal和没有正常完成标记，
不以编译失败/超时/进程exit0代替行为拒收。

最终原生综合报告V1.9.11.03 Education：Register3392、Latch0、
Logic3895（3624 LUT等价＋271 ALU），BSRAM8，原语DPB8；8个正文lane各1。
综合估算94.910MHz、Slack14.464ns、12逻辑级，仅为L4估算。
原轮24BSRAM/7446Logic与本轮工具入口/默认选项也不同，不把资源差全部归因CRC，
更不用于推断整机资源。正文memory推断日志及逐lane层级XML独立核对。
保留9条EX3791截断警告；新增CRC pos由2至31，6位容量足够，新警告不静默删除。
旧序号16位回绕、事件数512/字节4096、copy最多128等界限仍按原协议回归，
此次不顺手重写原字段。SSRAM未列出，不把未列出冒充明确0。

截断警告逐项处理边界（实际日志不删，行号对应本修版）：

| 行号 | 字段 | 范围/语义 |
|---|---|---|
| 187 | reply_pos + 1 → 6 bit | 回复最多34 byte；到最后byte走结束分支，不再递增 |
| 198 | reply_crc_pos + 1 → 6 bit | 从2开始，到23或31进入FINISH，最大31 |
| 245、249 | body_length、pos → 8 bit | payload经检查≤128，body≤138，索引≤137 |
| 272 | event_count → 10 bit | BEGIN先检查事件数1至512，10位可表示512 |
| 311、316 | copy_pos + 1 → 8 bit | payload最多128，完成阶段额外到129；不存在256回绕 |
| 315 | next_seq + 1 → 16 bit | 沿用冻结16位协议序号回绕，不改变线上字段 |
| 350 | verify_pos + 1 → 13 bit | 总byte数最多4096，13位可表示终点4096 |

这些界限由现有输入验证/状态终点和1/512容量、非法载荷等回归支持；
不是新增形式化穷举证明，也不把保留警告描述成“零警告”。

```powershell
& 'E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe' -B -X utf8 code/scripts/run_m3_score_transfer_bram_acceptance.py --output code/output/ram_timing_sim_NEW --timeout 1800
& 'E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe' -B -X utf8 code/docs/hardware/score_transfer_bram_v1/timing_build.py synth --output code/output/ram_timing_build_NEW --simulation-receipt code/output/ram_timing_sim_NEW/receipt.json
& 'E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe' -B -X utf8 code/docs/hardware/score_transfer_bram_v1/timing_build.py pnr --output code/output/ram_timing_build_NEW --allow-isolated-unreleased-bitstream
```

综合上限600s，原PnR上限900s；用户另批准一次1800s同配置追加，已启动但未取得最终结果。
03中断后另获一次同配置1800s重启确认，实际04结果以新收据和原生报告为准。
不自动重试或更换种子。PnR必须建立在相同已通过仿真和
成功综合的源/工具/配置/网表SHA上，runner保存自身快照。仅生成隔离未放行.fs。
历史package.py/review.py仍对应原轮，不应用于本修版；新封存入口timing_package.py。

## 时序签收边界

独立顶层score_transfer_bram_candidate，器件GW5AST-LV138PG484AC1/I0，C版，clk25ns。
独立SDC用全部数据I/O max/min delay0的虚拟同步环境；无原板CST、无真实板级接口预算。
这不等于UART异步引脚、真实板线或整机时序已验证。公开数据端口只是独立综合的虚拟I/O。
需检查实际Setup/Hold/Recovery/Removal、TNS、违例端点、未约束路径，不能由综合Fmax
或PnR退出0替代。原报告与独立审计sta_review.json共同交付。
码流及大体积物理数据库仅在隔离output保留并记录SHA，不放入转发ZIP，不准下载。
本轮未完成码流生成；前述.fs许可是工具若正常完成时的隔离权限，不是产物存在声明。
审计脚本8项自检实际通过，原stdout/stderr/退出0齐套；它只验证审计逻辑，
不是本候选实际STA通过证据。最后九门禁属于仓库推送要求，其中T007/T019为必跑基线，
不将其记成重跑T060旧RTL/Gowin或扩大本候选验证等级。

完整T059/T060/T061不随本轮关闭；无安装APK、串口、接线、Programmer或烧录动作。
T062同样不由本轮自动关闭或宣布正式采用。
正式接入、真实I/O/CDC/复位及新整机STA由M2负责。通知待用户转发，尚未送达。
