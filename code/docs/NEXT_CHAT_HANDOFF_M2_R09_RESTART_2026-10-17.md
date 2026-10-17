# M2重启续接：R09最小单元执行准备（2026-10-17 20:11 +0800）

## 2026-10-17 R09重启后实际结果：软件通过，首个编译访问冲突，整体PARTIAL

本轮用户“继续 M2，从 R09 重启交接恢复”已执行，覆盖下方旧暂停状态。新独立执行器修正root引用/Job归零、最终日志水位和首异常保留；新软件组8实际启动场景+3启动前拒收通过，exit0/4.394秒。准入前发现ivl目录只扫顶层漏两头，保留失败后唯一软件增量5检查exit0/0.948秒；旧生命周期组不重跑。精确两单元准入绑定当前软件证明、50项工具与6源。UNIT01已消费：仅raw_compile一次，exit3221225477/0xC0000005、9.448秒、双流0B，Job共5/最终0、root已关、身份未变；4934B残留vvp未运行，raw仿真和boundary均NOT_STARTED。根因UNKNOWN，不以产物存在签成功；事件日志读取被拒不绕过。≤30秒修复额度未用，只适用于具体源码/入口缺陷，不作为盲诊断重跑。

R09未完成，M2-R6-1/2/3和Pro仍PARTIAL、board_release_allowed=false；新软件安全证明不覆盖旧执行器/P7，完整链/EDA/设备均未启动。M3最新R08的36项与五组消费保持，M1/物理真实缺件不升级。详细原件与下一执行边界见test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017/c8_unit_execution_20261017/README_R09.md；C4/C7旧原件和他人修改保留，M3通知待用户转发尚未送达。

用户最后要求“保存现有成果，准备重启codex APP”。已经停止继续工作；用户重启后说“继续”再恢复，不自动跑进程。下面是精确恢复状态，不把源码准备写成执行通过。

## 入口、Git与已封成果

- 工作主目录`D:/17/project_17/fpga_gowin`，主HEAD **ad2de2169230dc8fd9f4b6f8157d384306c2479a**，有长期脏/未跟踪成果；不reset/pull/rebase，不覆盖他人修改，不全量git add。
- 发布隔离树`code/output/m2_r06_review_publish_20261017`为 **ef4fbc74b9d24e08de1e09d0be0eb3163118f258**，当前干净；最后已核远端同SHA，本次保存未重新网络fetch。它已包含R08任务36项和C6勘误，V0397、九门禁9/9。主索引为空，继续保留。
- 旧C4未发布原件与旧发布树`code/output/m2_live_tasks_publish_20261017`原0f13不动。旧C4六文件、新C7十五文件及旧488候选/27 D3历史/他人四文件SHA保存核同。
- C7本地包`code/output/m2_c7_cancel_and_boundary_20261017/M2_R08_C7_RAW_CANCEL_AND_BOUNDARY_LOCAL_NOT_RUN_20261017.zip`，1113447B，SHA **53adb7f2ede327e265e20409484c0e98340d0812b54e3ddd819f0778bc77f327**，52载荷。包含raw cancel_reason公开39口/66字段、72单元9ROM2头及两个TB源码，全部NOT_RUN。C7源ZIP SHA **d191132ad9eae52fd35e4c1bd17d598e5204d3d7c4b8bdd3ca3a423e37eff226**。

## 当前R09新工作停点

用户在M2提出“收口最小单元验证条件、形成可接手基线”后指示“开始执行”。根已写`M2_Pro基础最小单元执行单_R09_2026-10-17.md`，范围仅新独立执行器和raw-cause/sidecar boundary两个单元；不扩旧owned_executor，不代写M3 adapter，不开旧P7/完整链/Gowin/设备。R08仍是M3最新有效任务单。

三件新源码都在`code/build/138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017/c8_unit_execution_20261017/`：

1. `owned_unit_runtime.py`：Job所有权、固定操作、直接双流、终止/归零与回执。**仍有下列未修问题，不是安全验收通过版本。**
2. `unit_fixture.py`：本轮新正常/非零、根退子孙继续写流、超时和日志越限夹具；未运行。
3. `run_r09.py`：software/units固定两阶段入口，固定两个单元源/工具，不接任意argv；尚未完整自审。**不要直接启动。**

本次SW_01与UNIT_01目录不存在；新EXECUTION_ADMISSION_R09_UNIT01.json不存在。R09-SW一组90秒/一次增量60秒、两单元一组60秒/对应缺陷一次增量30秒均**未消费**。这些范围在R09单列，不能拿来重跑旧组或扩全链。暂停期间不执行。

## 三个具体未修问题

详见`code/output/m2_unit_execution_c8_20261017/executor_readonly/C8_NEW_RUNTIME_READONLY_FINDINGS.md/.json`：

- root句柄与Job ActiveProcesses归零顺序：现版保留root句柄先等空、0.2秒非零就判ORPHAN；先核微软官方计数语义再做最小修正，保存root退出/WAIT_OBJECT_0并关闭引用，再等仍打开Job归零。此项是静态语义风险，**未观察到本机泄漏/死锁**。官方原文入口：https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information 。
- 日志watermark尾部竞态：最后一次stat与root结束判断之间仍可能写入，最终日志超限却clean_exit；双流最终关闭/取得bytes后须再次判定并保持失败。
- finally的close/日志identity/save可遮蔽原BaseException，首流关闭失败会跳过次流；需独立清理/记录finalization_error并保持首错和非成功终态。

读取快照runtime SHA **62b0838227c613bf92052e9703037467c6c69778cc90424346f71e58bc572070**；fixture SHA **4fd5c4760f9771d6c2f5190e42bacd20139ed6c2641224cdbedd3f9c732cfc00**。恢复时先核实际文件，不沿用旧结论签新版。原Job/helper/R03最小要求也在同目录，只读来源，不重跑旧执行器。

## 工具静态材料与边界

`code/output/m2_unit_execution_c8_20261017/tool_inventory/`已封：

- TOOL_FILES.json：26项实际文件（20 suite PE、2 config、3 OS直接边界DLL、cmd候选），4799B，SHA **c2a79e3eb6086bab7d689b56944e722b86145aae4b905d65273f6df9131383a5**。
- TOOL_RUNTIME_BINDING.json：68967B，SHA **ccb5cf0935f2d33428ba3adff1e82d507911255a02be3f72725f1c4b8276cef5**。57条应用静态导入、ivl目录36原件身份、配置/环境与动态缺口。
- 原始TOOL_INVENTORY：361 PE/11753边。初resolver将vvp.tgt合法导入ivl.exe误附.dll，原扫描保留、派生绑定已明确纠正；不能称安装缺件。
- 真正涉及iverilog.exe/vvp.exe/ivl.exe/ivlpp.exe/libvvp-1.dll、target与7 VPI；应用侧静态未见缺件。OS API-set/KnownDLL/SxS及动态LoadLibrary/VPI实际装载未观察，不能标动态闭包齐套。
- compiler调用system/_popen，必须覆盖内部shell/子孙Job；清除或精确固定IVERILOG_ICONFIG/IVERILOG_VPI_MODULE_PATH、PATH/组件目录、cwd/tmp。不得source suite environment脚本，它会额外启动gdk-pixbuf-query-loaders缓存程序。

两位内部协作任务已停止，均确认没有仍运行的自有脚本或工具进程；本轮工具EXE启动/DLL加载/SW功能组/HDL/EDA/设备均0。

## 恢复顺序

1. 读AGENTS、协作入口、R08、M2卡/R09及本交接；检查主树保护SHA和最新远端，保留所有未发布成果。已有用户授权不重复询问，实际前置不齐不得先跑后补。
2. 在C8独占M2写集中修上述具体问题，并静读`run_r09.py`预算/一次消费/源码绑定/环境处理；保留本次未修版本和两份只读报告。旧executor和M3源不改。
3. 明确工具绑定的实际可证边界/动态验证方法，先冻结新software组的入口/工具/源码/输入/预期/输出/90秒期限，再一次运行。失败原件留存，具体缺陷才用一次定向额度，不恢复旧组。
4. 软件安全和精确工具输入齐套后，由M2冻结只针对两个单元的新EXECUTION_ADMISSION，再进行一次60秒组合；否则保持approved=false。不把Job清理成功当单元PASS。
5. 当前限定任务真实完成或形成新的准入/阻断节点后按根规则集中交付。必要验证/自审/原件齐套才发布；单文件Git写、最终fetch取号、精确树9门禁、普通develop和远端核同，保留C4/C7及他人修改。当前不得声称已提交、已推送或已仿真。

M1十九语义/apply/config/audio_stable、M3 R6返修/R7-A/B、真实Pro Part/version/板修订/Bank/许可/完整物理/板测仍未齐。整体PARTIAL、board_release_allowed=false。M3说明仍待用户转发尚未送达；未经授权不向别的聊天发消息；官_主开发2此前发送被平台approval-never拒绝，不能重试/换工具绕过。正式审核员/预审员制度未启动。
