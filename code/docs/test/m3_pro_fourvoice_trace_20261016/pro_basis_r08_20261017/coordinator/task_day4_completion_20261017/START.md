# M3 task-day4 剩余项补齐执行单

本轮直接授权：用户在收到剩余清单后明确要求“把剩余没有完成的补齐”，由夜间1总控、夜间2/3/4实施，可各用只读子智能体自审，允许有依据的多次解决尝试。此前“不动工/仅核查”的限制在此范围解除；夜间5不参与本次实施。当前仍以无板离线工作，HDL/EDA/设备和受控M1/M2接口执行不因本单增加权限。

开工事实：2026-10-17 22:36北京时间，输入已读task-day4两份旧R08/C7通知及上一轮REMAINDER_AUDIT.json。最新发布164ed345，e394790b旧432文件/十卷/C9补包均冻结不覆写；当前无已跟踪脏改动。NoteOn文字由dfee2c14限定L0关闭，原语义与单字段后继并引，不再造勘误。按最新五小时上限保守沿用关联21:52 START，最迟2026-10-18 02:52收尾，达到必要结果即可提前结束。

## 独占写集

三根仍为software、tb/board、docs/test下的m3_pro_fourvoice_trace_20261016；各角色只在原所属包新增c9_completion_r01，不改旧已签字节。总控仅software/docs/test的pro_basis_r08_20261017/coordinator/task_day4_completion_20261017；所有实现输出用code/output/m3_c9_complete_d4_20261017/的独占新目录，原件只追加。

- 夜间2：pro_basis_r08_20261017/build_admission_bundle/c9_completion_r01，C9执行申请/实际源码与工具/guard/输出/窗口身份的同版装配。沿用已有纯guard，不自签执行权。
- 夜间4：pro_basis_r07_20261017/public_capture_tb/c9_completion_r01流式C9采样转换；pro_basis_r08_20261017/capture_csv_codec/c9_completion_r01完整74字段CSV往返；pro_basis_r06_20261017/normalized_intake/c9_completion_r01无损旧入口适配；pro_basis_r07_20261017/oracle_bundle_bridge/c9_completion_r01机械MATH_INPUT_BUNDLE及旧6例同进程适配。原R6-5唯一生成器只读复用，不造第二FRAME生产者。
- 夜间3：pro_basis_r06_20261017/tx_clock_reset_checker/c9_completion_r01同版TX/串行接入；pro_basis_r07_20261017/public_equivalence_tb/c9_completion_r01大伴随流转换。复用固定PinDecoder，保留startup/HOLD/ID0/clip与尾段UNKNOWN。只读旧T27和C9 B13用例，不改其期望。
- 总控：公共固定源码加载/产物身份函数、整链CLI、独立输入与唯一FRAME_PLAN绑定、同源来源/finish、统一有界软件组、原件及串行Git。成员不碰index/ledger或共享状态。

## 必须补齐的行为

1. C9 72源/9ROM/2头，加唯一driver/observer/TB为75单元；申请不再硬套C6 SHA及71→74。窗口/argv/cwd/env/输出/预算/独占消费有精确身份，可信执行器/动态依赖缺口明确PENDING。首次采集不能要求预先已有真实trace。
2. 新74字段封套完整保存原行/原SHA/reset边沿及X/null、raw ports/events/semantics；旧61字段投影与TX extensions为明确派生产物，原C9证据独立保留，不丢字段凑接口。不以投影签D3真实通过。
3. 流式读取/写出，不用整窗read_bytes/list收集绕过64MiB；单行、元数据与输出规模各有明确边界。实际大输入需增量哈希/读后核同，失败保留未完成原件，不删行降规模冒称全窗。
4. 日历仍调用原R6-5唯一FRAME_PLAN生产者，F/A独立、内部严格t-F<833且早于下一FRAME；TX833/834另核。kind3/4/8哨兵、同seq多阶段、真实lane_tick、实际config_take与三clip均保留。独立plan seq/audio_stable未证继续PENDING，不补0或固定延迟。
5. MATH_INPUT_BUNDLE按M1 NEXT_INPUT_CONTRACT机械包装，带源/ROM/合同/输入/公开trace/reset/finish/plan/TX与FX历史的原始索引；数学期望仍M1，不能把实际PCM当黄金。整链入口应可接受真实外部捕获候选，结构通过不鉴真。

## 软件验证与消费

本轮用户直接要求补齐刚列的未完成项，允许必要的有界纯文件软件验收。建立全新TASK_DAY4_REMAINDER_SW台账，绑定原未执行27+6+42定义及本轮新增接缝断言的精确源/输入/依赖/argv/cwd/输出。原R/S/C/T/H及R7旧台账不改、不恢复，已匹配204项不复跑。新批次不声称旧组整体重跑通过；旧6例若以同进程CLI函数适配执行，单列路线而不伪称启动旧CLI子进程。

总控统一一次初组≤120秒；只有具体失败才允许最多3次各≤60秒的定向修复尝试，逐次不同依据/修法、冻结新源码，仅对失败及必要对应增量检查，已过不重跑。禁止成员自行导入、编译或执行候选；READY前只编辑、读JSON/文本、哈希与封包，可用自己的只读子智能体。初组/修复均在同一Python进程内，禁止Popen/子进程/网络/EXE/DLL加载/HDL/EDA/设备；候选只能写本次run独占输出。审计/超时异常停止该组，保存首现场，按授权边界处理。

每个新包提供可运行CLI和无副作用run_case(id, output_dir)->dict；CASES.json写id/expected/description。只提供本次变化所需新正负例和跨包断言，不导入旧selftest全面重跑。原未执行case只经总控精确选择且在新台账另列。固定SHA从源码字节加载，避开旧pyc，不删除/放宽缓存审计。

## 接口与收口

公共helper由总控写common.py，提供ROOT/SOFT/DOC、identity、artifact、load_source、read_json、write_json、checked_descriptor、require、iter_jsonl。

- A build_application(request:dict, output_dir:Path)->dict；schema=M3_C9_EXECUTION_APPLICATION_REQUEST_V1，保留旧申请字段语义，产物返回artifacts（path/bytes/sha256），永远execution_allowed=false，待M2决定。
- B convert_files(raw,resets,end,stdout,output_dir,origin='SYNTHETIC_SCHEMA_FIXTURE')->dict，返回artifacts.public_rows；另给project/intake与机械bundle的文件API，完整74字段输出为唯一canonical，旧投影有独立来源。最终API在READY写明。
- C analyze_files(public_rows_path,frame_plan_path,output_dir,expected_scenario_ref=None)->dict；只消费既有唯一plan，不生成；无独立TX期望时保留选择策略PENDING，但可核观测TX与实际pins一致性。大伴随流转换单列文件API。
- 总控chain.py按同一capture/source和实际产物SHA串接；可执行申请先就绪，缺真实capture时明确HDL_NOT_RUN/PENDING_EXECUTION。实际source/数学/物理/板测不具备时整体仍PARTIAL，不能因SOFTWARE_READY冒签DIGITAL_VERIFIED。

各写者目标23:15前接口和最小可核原件、23:45前整包READY，完成后静止不再改SHA。只在READY/具体阻断/必要接口变更时与总控沟通；平台拒绝回传则落本地供读取，不重试绕过。源码/用例/输入/原始双流/退出码/失败史/消费齐备，最终一份交付，九项门禁、普通develop、远端SHA核同；M2最终复核与真人交接仍待用户转发。
