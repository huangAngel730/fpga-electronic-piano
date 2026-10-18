# 10.18 两处入口去重及 R10 捕获入口补齐

本地 `10.18/FORWARD_TO_M3_PUBLISHED.md` 是 16ac2265 的旧 C9 静态通知，其首段与仓库通知同文。GitHub 最新有效入口仍为 edab067e 更新的 R01 与 R10，按 R10 顺序处理；旧通知的 NoteOn 文字待确认项已经后继 L0 勘误关闭。本次不恢复旧额度。

三方核缺后发现 M3 自身的具体遗漏：原 R10 新入口只生成申请，未分发 D4 已有的 PROCESS_CAPTURE。现以 `capture_link_r01/entry.py` 作为后继统一入口，保留旧源码与原件，只在新清单中把 D4 的 application 绑定替换为严格限制 R10 输出域的适配器。规范化、唯一 FRAME 生成、日历、TX/串行、数学机械包装和来源核验仍调用固定 SHA 的原实现。

本次限定 L1：唯一 LINK 条件修复组 6/6 MATCHED，实际退出 0、0.5 秒，已消费原有一次不超过 60 秒增量。正例仅使用分发探针；没有处理真实 RAW、生成完整 FRAME、重新解码串行或执行数学比较。旧 114、204、LINK 七例和 H54 均未重跑。首次静态缺陷与冻结清单准备时的错误路径失败均保留，后者没有导入或执行候选。

当前整项仍为 PARTIAL／WAITING_INPUT。M2 仍需冻结 finish 的 D/D+1 相位，核可信执行器与动态工具依赖、精确新 C9 HDL 许可和预算，并明确 audio_stable／实际背压范围；M3 后续取得同次真实采样原件才处理完整链；M1 负责独立计划映射与 PCM24/ID/clip 数学。两机演练的发送端明确主机／会话、真实故障恢复和 M2 最终回执仍缺。后台半小时触发与 App／机器重启没有验证；本轮不擅自部署或代签。

统一入口接受三个字段：`schema=N10_M3_UNIFIED_PIPELINE_REQUEST_V1`、`mode`、`request`（原请求文件的 path/bytes/sha256）。准备模式的原件封装见 `UNIFIED_PREPARE_REQUEST.json`。捕获模式要求原 D4 PROCESS_CAPTURE 请求、这里固定的 `CAPTURE_MODULE_BINDINGS.json`、已冻结独立 finish/window 及 raw/reset/end/stdout 等完整输入；缺件在创建输出前拒收。入口不授予工具执行、REAL、数学或板卡许可。

在后续有效预算内的调用形式（本轮不再执行）：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 'code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/capture_link_r01/entry.py' --request <envelope.json> --output <R10-output-fresh-child>
```

候选准备／处理成功的 CLI 退出码为 3，表示限定软件产物，不能当作真实验收通过。当前真实捕获模式尚未调用。

`INTEGRATION_HANDOFF.json` 为本轮唯一现行后继交接，保留原 14 项合同内容并补上统一入口／新绑定／修复证据；原交接文件不改。`ROOT_RECONCILIATION.json` 是三方结论、历史结论更正及逐项恢复条件；`DURABLE_DEDUP.json` 防止重复推进。成员早期报告反映各自读取时点，member3 的 R02 与总控最终结论覆盖“没有 M3 代码遗漏”的过宽判断。

实际 START 为北京时间 10-17 21:52，截止 10-18 02:52；续接 Goal 和新目录不重算时间。当前 Goal 的 createdAt 为 1792257077，旧有界准备 Goal 1792253457 已结束；成员报告中的旧 Goal 值仅属原阶段记录。额度只按 API 快照报告，其他成员额度不可得，不估算金额。

原件 ZIP 保存本地通知的原始字节、成员原报告、新源码、运行合同、六例原始输出与冻结输入、共享修复台账和实际 Git 查询；外部商业工具只列身份，不随包分发。旧 D4／R01／R10 结果通过已发布的原包复用。M2 可从本轮 RESULT_RECEIPT 获取源提交和原件清单；发布、AI 收件、M2 验收和板测分别记录。
