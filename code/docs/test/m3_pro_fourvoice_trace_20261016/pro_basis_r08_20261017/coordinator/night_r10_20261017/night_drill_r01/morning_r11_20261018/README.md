# R11 包 A：演练机制的静态源码后继

当前等级为 **STATIC_ONLY / RUNTIME_NOT_RUN / PARTIAL**。本包完成两项缺陷的源码接合及静态自审；没有运行、导入、编译或 AST 解析候选，没有执行软件组、worker、Git 网络、HDL、EDA 或设备操作。旧三组消费不恢复，整体双机演练不结项。

当前封存版本为 **R02_BASELINE_LF_STORAGE**。仅修正发布存储：正式 baseline 为同一 JSON 的 LF 副本，34907 字节，SHA256 `ca723ff05905b81dce4d2a80bf226369cc9f03def4e444245bbddb662350e6ce`。原36202字节、SHA256 `75e9ed9eb1421e3ea7b1cf924213bdd08b143b1538d9b84c45f9d931a4e189c7` 的 CRLF 原件及 R01 全包（含旧 READY、源码）逐字节留在 `BASELINE_ORIGINALS_R01.zip`。未改变旧运行账、`.gitattributes` 或台账的 JSON 内容；`.bin` 方案取消。最终 index 字节门禁仍由总控另验。

任务来源为总控晨接派工，实际 START 2026-10-18 11:57:42+08:00，统一截止 16:57:42+08:00。写集仅同名 software 与本 docs/test 后继目录。唯一 Goal、Git 发布者及最终集成者仍为夜间任务1；本窗口没有 Git 写入。总控继续使用原已验入口发布本包，不能迁移到本候选。

## 两个源码入口

软件目录为 `code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/night_drill_r01/morning_r11_20261018/`。

- `binding.py` 的 `verify(spec_ref, snapshot_root)`：从调用方独立冻结的原始 JSON 描述符开始，检查实际 HANDOFF 原始字节、完整身份、manifest 本体、原 run contract、输入和源码身份、实际结果及 ZIP 成员。禁止以批准字符串、短提交或内置样本 ID 替代原件。
- `transport.py` 的 `prepare_send`、`receive_frozen`、`send_once`：在实际调用原 `network.run` 前，以原 `intake/engine.py` 原子 Store 持久入队并消费尝试。实际 argv、退出码、耗时、原始 stdout/stderr 身份和错误落入 outbox；成功仅为 AWAITING_REMOTE_VERIFICATION。

它们是供将来获准执行器调用的函数，没有自动发送 CLI 或 import 时写入。固定 state 位于原 output 根下 `state/morning_r11_20261018/delivery`；当前尚未创建、启用或演练该 store，不是第二个运行中的发布者。

## 身份证据的缺边

两个 `*_BINDING_EXAMPLE.json` 引用真实旧 HANDOFF、冻结 contract、结果及成品 ZIP，**不是新交付、不是发送许可，也不是本轮测试结果**。文件元数据检查见 `HISTORICAL_INPUT_AVAILABILITY.json`；其中快照只说明检查当时本体可达，不执行候选 verify。

旧 local_group 的 SPEC 只有 source map，没有原 RUN_CONTRACT 的 raw SHA。RESULT/source_after、CONSUMPTION/spec_sha256、DRILL_RESULT/source_version 不能恢复这条缺边。本包不生成事后 provenance 给旧运行补签。历史 profile 无论其他身份检查如何，均返回 `direct_result_contract_binding=MISSING`、`queue_allowed=false`；发送和接收的 Store 入口另行拒收它。

新生产 profile 必须有由**获准执行器在实际读取及实际产出时写出**的 `M3_R11_RESULT_PROVENANCE_V1` 原件，绑定 raw run_contract、input_handoff、frozen_inputs、frozen_sources 和 result_refs，并核所有本体。SEND 还要求同一 HANDOFF manifest 的 ZIP 原样包含 contract、输入 HANDOFF、provenance 及必要执行结果。调用者自行拼装一份声明不构成实际执行证据；其来源及准入由总控/M2独立核验，函数本身不颁发执行权限。

provenance 的 delivery_identity 含 HANDOFF 的六个身份字段，刻意排除尚未产生的 result_commit，避免“归档内写自己的 Git 提交 SHA”的循环。完整 result_commit 由独立发布证明及实际 Git blob 原件在发送准入时核验，不冒充前置执行结果。

## 原运输与历史保留

固定复用原 Git 路径、代理、HTTP/1.1、禁交互和 Windows Job/隐藏进程树；仅把 loose develop 改为 `完整提交:refs/heads/develop`。原 network.py、engine.py 及其 Job helper 均不改。原 30 秒机制保留，wrapper watchdog 为 29.5 秒；消费前和运输调用前均要求至少剩余 31 秒。消费后若超窗，保留 IN_FLIGHT，恢复时为 UNKNOWN，不能退回待发重置次数。

原 network ledger 的 JSON 内容以 LF 正式副本 `LEGACY_NETWORK_BASELINE.json` 保存，精确 SHA 写在候选中；原始 CRLF 字节在前述 ZIP 中留存。要求该快照为静止的 OK 尾态，当前历史必须保留原前缀，后加记录允许；原历史有非本次未解决故障时立即停止。重复发现以 handoff_id＋完整 result_commit＋consumer 的全 SHA key 去重，operation_id 由同一 key 固定生成。outbox 与原 ledger 尝试数必须一致，最多首次加一次基于新证据的重试；只将明确建连前失败列为临时失败。拒绝、非快进、UNKNOWN、超时或异常均不盲重发。硬退出仍需原身份核验的 stale-lock 恢复，候选没有自动清锁或 UNKNOWN 解锁接口。

`check_admission` 要求独立冻结的新准入原件、精确工具/源/argv/cwd/窗口、近期 fetch/未包含检查，以及逐项 Git show 的原始 blob 与 manifest 相等。它只核材料身份，不能将任意 JSON 变成人类授权。当前没有这种准入，也没有同次新生产 provenance；因此不能启用。

## 后续责任

`VALIDATION_REQUEST.json` 只列新增断言和待申请范围，当前 granted=0；其中明确缺新夹具/runner、精确新输入和准入原件，不能直接当可执行合同。先由总控/M2决定新增验证范围，再冻结测试 runner 的 SHA、argv、用例、输出和预算。旧 120/60/60 秒三组、旧成功结果和旧 START 均不能拿来运行本候选。

所有本轮源、旧依赖及资料 SHA 见 `SOURCE_BINDINGS.json`；自审过程见 `STATIC_REVIEW.md`。本包不签真实运输、崩溃恢复、双机四类、完整 capture 或硬件通过。
