# R7-A public_capture_tb 交付

状态：**SOFTWARE_READY / PENDING_REAL_INPUT**。本轮明确授权的公开采集源码、实际输出schema及新合成软件检查已齐；整体Pro四声、真实finish、G0–G3与板测均未签通过。`board_release_allowed=false`。

基线HEAD：`4fd3366e42fd2356e56eb96eee70b6771afd4bb1`。只修改本包三个独占根；未fetch/同步/改索引/提交/推送，发布由夜间总控串行汇合；共享状态、看板、M1/M2源和R06旧原件未改。

## 已交内容

- TB `tb_r7a_public_capture.sv`复用已交R6-2外部MIDI/reset driver；唯一passive observer `r7a_public_observer.sv`只读38个公开obs和5个物理引脚。实际core posedge PRE_NBA逐行输出，保留F、A、result、commit、TX、reset和唯一结束原件。结束请求在core下降沿置位，避免采样竞争。
- `CAPTURE_SCHEMA.json`为实际版本`M3_R7A_PUBLIC_ROW_V1`；裸61键不扩列，TX新字段置版本化extensions，原行号/time/SHA/epoch置source，23项尚未公开语义保null及逐项原因。`CAPTURE_FORMAT.md`说明原件和C桥接口。
- `assemble.py`机械转换并保留所有core行、无效metadata下的实际TX、有效ID=0和X/Z；流式CLI不收集整份capture到内存。epoch绑定独立RESET_EDGES，同ps歧义保null；不生成FRAME_PLAN，不核声音数学。
- `RUN_SPEC.json`冻结源码/输入/依赖/工具及36个新夹具。`RUN_01/SOURCE_INPUT_ORIGINALS`、`INPUT_ORIGINALS`、FIXTURES、原双流及逐例结果均保留；完整文件身份见FILELIST及SHA清单。

## 实际验证

初组唯一命令：`C:\Users\songdongkuan\miniconda3\python.exe -s -B <本包software根>\run_once.py`，cwd为仓库根。监督子进程的精确argv/cwd/UTC/PID及双流SHA见`RUN_01/PROCESS.json`，其cwd是本包software根。

2026-10-17 UTC 11:18:29.826726至11:18:30.656087，受监督selftest exit=0，无timeout、日志限额或stderr。父组含执行后身份复核耗时**2.061999999990803秒≤90秒**；初组消费1，增量0，HDL/ModelSim/Gowin/设备0，旧R06重跑0。前后各核1266个文件身份，漂移0。

**7正29负，共36例通过**，覆盖：F/A分离、signed24正负边界/unsigned64、左右clip、有效ID=0、无效metadata与HOLD采纳保留、X/Z、异步reset、同ps歧义和PRE_NBA；缺reset/初相位、端口/宽度、序列、时间、伪造epoch、缺finish/finish后续行、END行数/越权PASS、MONITOR缺失/重复/畸形/不匹配及Fatal等反例按指定拒绝。正负例均为新合成格式夹具，不代表DUT行为覆盖。

另2个真实CLI子进程：正例exit0，额外畸形MONITOR_END反例exit2；原stdout/stderr和进程收据已封存。进程内29负例只报告拒绝码，不冒充29次独立exit码。无意外测试失败，无RUN_02；全部预期拒绝输入及实际结果均留存。

Python源码静态AST读取7文件通过。schema检查是针对冻结schema所用关键字的标准库断言子集，未声称通用JSON Schema验证器。TB及observer **仅L0源码自审，未编译/未仿真**；转换器及夹具仅**L1软件**。

## 未验项与责任

1. M2按`SOURCE_ASSEMBLY.json`及其引用的M2替换闭包冻结实际source/ROM/IP/时钟模型、精确EXE/argv/cwd/输出/预算，绑定6个窗口参数后签首次HDL组合准入。源码默认参数会拒绝未冻结结束窗口，不能直接运行默认配置。
2. R6-2 driver独立40MHz时基不能当实际core拍号；ready.drv不支持在整机制造背压，driver辅助日志不作真实接受。实际A只读DUT公开req握手。
3. M1补真实19项语义出口及apply_event_seq等差额，M2闭合config_payload/cancel_reason/audio_stable等；当前共23项缺失明列，不填零。不回填真实slot/世代/算法或PCM黄金。
4. R6-5独立FRAME_PLAN及账本、R6-6串行尾端/TX/reset/finish规则尚需对应包核验。TB的END只记录实际采样到停止请求，不替代真实工具exit0/timeout/cleanup原件；real_finish_pass保持false。
5. C桥可读实际schema与`RUN_01/products/public_baseline.CLI/PUBLIC_ROWS.jsonl`作为明确合成样本。真实capture、公开等价、Pro物理/STA、电气和板测全部待后续授权及原件。

本包无Git写权限；未提交、未推送。交付只回传夜间总控一次，不启动审核员/预审员，不消耗剩余额度、不重跑成功组。送达状态以独立COMMUNICATION_RESULT收据为准；M2真人通知默认待用户转发、尚未送达。
