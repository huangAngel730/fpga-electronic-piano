# task-day4 剩余项软件补齐入口

本目录只覆盖先前差额清单中的软件实现和必要验收。原件、命令、双流、退出码、消费和逐项结果以 `RESULT.json`、`CONSUMPTION.json`、`DELIVERY/ARCHIVE_RECEIPT.json` 为准；READY 文件是成员执行前封版声明，不是测试通过回执。旧版本及旧失败不覆写，R10 保持停止。

## 整链接口

入口是 `code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/task_day4_completion_20261017/chain.py`。`process(request, output_dir)` 接受 `M3_C9_CHAIN_REQUEST_V1`，输出目录必须全新、位于本轮独占 output 下。

`PREPARE` 装配 C9 75 单元申请与唯一 FRAME_PLAN，无需已有真实捕获。`PROCESS_CAPTURE` 按顺序串接完整74字段转换、CSV逐行往返、61+TX显式派生账本、原R6-5唯一计划/日历、TX/串行、机械数学输入包及原始来源/finish核验。处理器不启动 HDL、EDA、设备，也不授予执行许可。

request 的 `module_bindings` 是本目录 MODULE_BINDINGS.json 的 path/bytes/sha256。`inputs` 中每项也是原文件描述符；真实准备需要 application_request、frame_input、frame_rules、midi_plan、window_plan，处理捕获再提供 raw、resets、end、stdout。source_contract_refs 必须含实际 C9 SOURCE_CLOSURE_R06C9.zip。可选 math_inputs 放真实工具/driver/observer/TB/ROM/合同/执行回执等描述符；缺项保留 missing_roles，不能放空回执补齐。

真实候选必须满足申请 capture ID、stop ID、finish cycle、MIDI 计划与独立计划的同版关联。测试的 `synthetic_application_example=true` 仅配合 `origin=SYNTHETIC_SCHEMA_FIXTURE`，在回执中明确单列“应用示例与合成窗口分开”，不可用作真实准入。

例如，未来获得对应执行许可并冻结新的输入/台账后，文件接口形式为：

```powershell
python -B -X utf8 .\code\software\m3_pro_fourvoice_trace_20261016\pro_basis_r08_20261017\coordinator\task_day4_completion_20261017\chain.py --request <精确冻结的request.json> --output .\code\output\m3_c9_complete_d4_20261017\<全新目录>
```

CLI 退出3代表限定准备/候选输出，不能解释成完整通过。实际验证由总控冻结组执行；本轮组消费后不得把示例命令当新额度自行复跑。

## 证据与界限

本轮新台账一次初组120秒、最多三次定向修复各60秒，均在同一 Python 进程中执行；原已过204项不复跑。旧27项、旧R7-C六项和C9原42项严格绑定原定义；旧R7-C 六项明确使用同进程生产函数路线，不伪称启动 CLI 子进程。旧动态源码加载统一走冻结 .py 字节，不读写旧 pyc；原读写审计不放宽。

大于64MiB用例会真正生成完整文件，并逐行转换、增量哈希和逐件核同。复位与JSON元数据有明确上限，日志按有界行读取，失败产物保留。

整链文件正例为7行合成空闲窗口；完整立体声字、ID0和HOLD由单列串行用例检验。以上均不证明真实C9 HDL执行、独立数学正确、实际工具动态依赖或实物/板测。`real_verified`、`math_verified`、`execution_allowed`、`board_release_allowed` 保持 false。门禁中的旧工程测试也不能外推为新Pro通过。

M2 手动交接文字见 FORWARD_TO_M2.txt，发布后提交与远端核同见 PUBLICATION.json。任务看板与当前状态只由 M2 更新。
