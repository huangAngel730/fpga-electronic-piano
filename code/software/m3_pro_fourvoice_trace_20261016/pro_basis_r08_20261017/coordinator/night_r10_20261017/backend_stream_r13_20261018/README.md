# M3 R13 后端流式候选（静态实现，尚未运行）

本目录是 R12 的新后继，不是 D4 替身。实际调用链为：

`entry.py → binding.py → 冻结 R12 → R11 → R10 → 真实 D4 → application/frame/stream/codec/intake/calendar/serial/math/provenance`。

本文件记录源码冻结前的候选实现；实际执行与消费以同名证据根 backend_close 的回执以及最终 ignored 封存实际收据为准。冻结前未运行目标 P0/K/V/B/W。所有 `real_verified`、`math_verified`、`execution_allowed`、`board_release_allowed` 都保持 `false`。

## 关键接口

生产入口：

```powershell
python.exe -X utf8 -B code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/backend_stream_r13_20261018/entry.py `
  --control <absolute CONTROL.json> `
  --control-sha256 <sha256> `
  --output <absolute fresh child under code/output/m3_backend_stream_r13_20261018>
```

`CONTROL.json` 必须严格使用 `M3_R13_BACKEND_CONTROL_V1`，字段为 `schema/run_id/run_kind/envelope_ref/dependencies_ref/quota_bytes/volume_policy/authority`。`envelope_ref` 和 `dependencies_ref` 均为 `{path,bytes,sha256}` 文件描述符。控制 JSON 只读入并解析一个缓冲；结束前仅复算身份，不以第二次解析覆盖初始决定。完全改回的瞬时 ABA 无法由前后身份证明，完成收据明确保留此限制。

纯准入入口：

```powershell
python.exe -X utf8 -B .../run_plan.py --assess-one --group K `
  --snapshot <abs> --snapshot-sha256 <sha> `
  --prerequisites <abs> --prerequisites-sha256 <sha> `
  --now <ISO8601-with-zone> --output <fresh decision.json>
```

一次性监督器必须由 root 作为独立 Python 进程启动，不能在长寿命协调器内 import 调用：

```powershell
python.exe -X utf8 -B .../job_bridge.py --execute-one `
  --admission <abs> --admission-sha256 <sha> `
  --owner-output <fresh .../RUNS/K>
```

它冻结的 worker argv 为：

```text
python.exe -X utf8 -B selftest.py --worker --group <P0|P1|K|V|B|W|R>
  --admission <same abs> --admission-sha256 <same sha>
  --output <owner-output>/worker
```

普通组的 `owner-output` 保存原始 `stdout.bin/stderr.bin/RESULT.json`，业务输出只能在其 fresh 子目录 `worker`。B 组把实际业务 worker 放在 `owner-output/B02/worker`（admission 的冻结 argv 必须使用该路径），随后在同一 120 秒父层绝对预算内运行 `B03` 后代自然退出夹具和 `B04` 后代超时清理夹具；三案各自保存双流、Job 累计/归零和两类原生 CloseHandle BOOL，全部通过才写 `GROUP_COMPLETE.json`。worker 不会自签 B02/B03/B04。

## 流式卷与完成语义

- 所有 `.jsonl/.csv` 大逻辑文件生成时直接写为 gzip 独立卷；不会先生成整份明文。
- 每次物理读写不超过 1 MiB；每卷最多 31 MiB 解码数据，压缩卷硬上限 32 MiB。
- 清单绑定卷序号、逻辑偏移、逐卷解码长度/SHA、压缩长度/SHA，以及完整逻辑流长度/SHA。
- 读取严格检查缺卷、重复/错序、错偏移、压缩或解码身份、截断和整体身份；字节透明，不规范化 UTF-8、CRLF 或 LF。
- D4 必须从第一拍起就在最终稳定路径生成，因为冻结 D4 的描述符会记录该路径；不能把含自描述路径的 staging 树重命名到别处。
- 目录存在不代表提交。D4 任一异常保留同一稳定目录中的原 D4 产物和 `R13_FAILURE.json`，不写 `COMPLETE.json`，并原样重新抛出首个异常；清理或失败收据的次级异常不得覆盖首异常。
- 只有真实 D4 全链返回、发布后仍可按原描述符逐件重开、全部身份/资源终检通过后，才用同目录临时文件、`fsync` 与 `os.replace` 原子发布 `COMPLETE.json`。D4 的 `HANDOFF.json` 和没有完成标记的目录都不是 R13 完成。

## 数学输入/输出边界

D4 当前真实数学**输出六件**为 `MATH_INPUT_BUNDLE.json`、`RECEIPT.json`、`MATH_ROW_INDEX.jsonl`、`FX_HISTORY.jsonl`、`ADVANCE_HISTORY.jsonl`、`INPUT_AND_APPLY_HISTORY.jsonl`。不得虚构第七输出；取消后 advance 仍由原 D4 逻辑保留。

M1 消费合同的**输入七角色**为 `mechanical_index/public_rows/raw_capture/independent_plan/frame_plan/reset_edges/provenance`。旧 `mechanical_index rows[]` 与流式 `MATH_ROW_INDEX.jsonl`、reset 投影的消费者适配仍为 PENDING。因此 `FORMAL_REAL` 被明确拒绝；当前入口只能形成软件合成候选。

远端新增的 M1 R13 bounded consumer/independent semantics 已按提交 `86cd5975f5679ad2db9da7b0d20d2892e76e76b1` 和绑定提交 `7319fe670d3524252ac299e11f00d00ae52c9953` 收件；其 36 个声明原件可取，但仍是 L0 候选，本窗口未导入或执行。`CAP01=GENERATOR_BINDING_PENDING`，54 案、容量与数学均未验，因此它不会自动解除上述 FORMAL REAL/消费者兼容缺口。

## 已知限制与 W 状态

- 按旧明文形状推算的有条件几何约 32 GiB（不是所有压缩布局的下界），超过 24 GiB；本候选用生成即分卷避免多份明文并存，但改用全部写入者共享的预写配额限制自有产物峰值；它允许实际 W 因配额不足而失败，不预签压缩容量通过。
- W01 当前必须保持 `RESOURCE_PROFILE_PENDING`/NO_GO，直至 32 GiB 起始空闲、8 GiB 结束保留、24 GiB 全工作区峰值、512 MiB worker/进程树峰值和所有 writer 覆盖均有证据。
- W01 已静态接通独立全窗生成器、真实 entry/D4、终检以及全部 inputs/physical 输出的 DELIVERY 无损分卷导出；这些步骤都计入同一次 W900s，尚未运行。不得从小窗输出反推预期，也不得在组外预生成后虚称容量通过。
- 历史 frozen owner 的 Job 累计 `total=2`，不能仅以根进程峰值证明无子进程/树峰值；P0/B worker 只写 `WORKER_LOCAL_RESULT.json`，父层缺严格 Job 收据时不得生成组完成。
- frozen owner 本身未记录 `CloseHandle` 原生 BOOL；`job_bridge.py` 仅在私有 owner/单个 Popen 句柄上装配一次性观测并记录真实 BOOL，不修改冻结源码或全局对象。装配失败、缺事件、重复事件、BOOL=0 或 Job0 先后错误都不能 PASS；只有将来 P0/B 实际运行才能验证该接缝。
- 旧链的 8 MiB 控制 JSON（包括可能增长的 intake ledger）、16 MiB metadata 和 64 MiB PE/source payload 可达边界仍须 P0/B/W 实际证明；本候选没有擅自抬限。
- 用户确认最终大卷可从 `code/output/.../DELIVERY/` 人工转发；Git 内 `<32 MiB` 的执行原件包只放索引和小原件，不能声称包含所有大卷。

## 文件职责

- `entry.py`：一次控制、稳定目录、真实链、终检和原子完成标记发布。
- `binding.py`：私有命名空间中按 SHA 装载并接通真实 R12→D4。
- `stream_bridge.py`：同缓冲控制、≤1 MiB 身份读取。
- `volume_io.py`：无损可逆卷。
- `finalize.py`：六个 D4 数学输出、全产物身份和唯一完成屏障。
- `resources.py`：资源阈值/观测数据结构；W 严格证明仍待协调器收据。
- `run_plan.py`：纯 GO/NO_GO 算术，不消费、不启动；P1/R 只在保存失败、定位本方缺陷、冻结 diff 与新旧 SHA 后进入预算和顺序。
- `job_bridge.py`：冻结 R12 owned_call 与 Windows Job 生命周期。
- `selftest.py`：P0/K8/V12/B12/W1/R worker 候选；K 使用独立冻结的实际合同 bundle/变异件，不使用内置 toy 字典；V12 实际拒绝仅本地路径且无完整交付说明的控制；B/W 每案需要独立 control SHA 和案别后置条件。测试结果尚不存在。

## root 必须冻结的 admission 资料

- P0：本文件中列出的 R12、Windows Job 与真实 D4 pin；worker 只做本地 pin/可用性，Job0、后代、超时、双流与原生句柄结果由父层收据闭合。
- K：root 提供 `contract_index_ref`，组内复制8件并构造8个独立索引；变异重算外层SHA，再由同一语义消费器拒收缺源、profile冲突、计划身份替换、trace反推和reset错源。K04 保持计划路径只替换其身份。
- V：V12 另需把已确认的 `delivery_channel_confirmed=true` 以及 `delivery.location/retrieval_method/all_logical_originals_recoverable=true` 冻结在 admission；用例会构造 local-only 反例并验证拒绝。
- B：`fixture_templates` 为已冻结9个原件描述符，组内构造独立当前控制及语义预期；W：`w_input_freeze_ref` 为新nonce及同源9模板/物理预算的冻结对象。B07 冻结三种往返身份；B08 必须绑定 `roles/main4/B08_MINIMAL_FIXTURE_NOTE_R02.json`（18457 B，SHA `f74e26b6d7351af164863c12be32d470b30332deb7be9e885aa28e43a7b389be`），按 `public/advance/cancel_evidence/serial/frame_plan` 五个实际角色和固定独立语义坐标验收，产物SHA在执行后记录。检查固定为 837 行、FRAME=833、A/四 lane advance=834、cancel=835、finish=836，以及 cancel 后唯一 advance 仍在；该夹具由总控在同一 B 组 120 秒内物化，不另开执行槽。B10 冻结完整 terminal；B11 冻结资源下界并声明父进程树收据必需；W01 冻结 raw role并满足不少于 1130662 行/1398627657 原始字节。失败案必须产生 `R13_FAILURE.json` 且没有 `COMPLETE.json`。
- P1/R：snapshot 的 `repair` 必须冻结 `failure_group/affected_case_ids/failure_receipt_sha256/old_source_sha256/new_source_sha256/diff_sha256`，并声明已定位本方软件缺陷及新源已冻结；R 只运行该单组最多 16 个已冻结受影响案。

最小公共 admission 外壳如下；尖括号必须由 root 用独立冻结值替换，不能原样执行：

```json
{
  "plan_sha256": "729cb21bd4b759f7d5738bdc14964bee1eaf5da053eee20b4a278acf651357d3",
  "group": "<P0|P1|K|V|B|W|R>",
  "state": "CONSUMED_RUNNING",
  "absolute_cap_seconds": "<60|120|900>",
  "argv": ["<python.exe>", "-X", "utf8", "-B", "<selftest.py>", "--worker", "--group", "<group>", "--admission", "<absolute admission>", "--admission-sha256", "@ADMISSION_SHA256@", "--output", "<exact worker output>"],
  "contract_index_ref": "<实际9件合同索引描述符；变异在组内形成>",
  "fixture_templates": "<B或R/B的冻结9模板；W另需w_input_freeze_ref>",
  "delivery_channel_confirmed": "<boolean>",
  "delivery": {"location": "<accessible path>", "retrieval_method": "<method>", "all_logical_originals_recoverable": "<boolean>"},
  "resource_profile": "<PASS或RESOURCE_PROFILE_PENDING>",
  "repair_group": "<仅R: K|V|B>",
  "affected_case_ids": "<仅R: 1..16件>"
}
```

`run_plan.py` 的 snapshot 必须含 `plan_sha256/start/member_end/deadline/explicit_cutoff/slots/network_charged_seconds/local_git_charged_seconds`；`slots` 必须恰有 `P0,K,V,B,W,P1,R,GATE_01,S1,GATE_02,S2`，每项含 `state` 与满额计费的 `charged_cap_seconds`。条件修复时另加：

```json
{"repair":{"located_own_software_defect":true,"changed_sources_frozen":true,"failure_group":"<K|V|B>","affected_case_ids":["<case>"],"failure_receipt_sha256":"<64hex>","old_source_sha256":"<64hex>","new_source_sha256":"<different 64hex>","diff_sha256":"<64hex>"}}
```

执行结果统一以 `status` 和 `cases:[{id,status,...}]` 为本地 worker 判据；P0/B 的 `PASS_LOCAL_PENDING_PARENT` 不是组 PASS。最终只接受父层 `GROUP_COMPLETE.json`，且 B 的 `B02_B03_B04_parent_observation` 必须为 `true`。

验证等级：**L0 静态候选，未运行**。只有协调器按批准的组别、额度、截止和冻结 SHA 执行并形成实际回执后，才能产生软件级结果；任何结果都不是 HDL、FPGA、数学黄金、上板或发声验收。


##2026-10-19 continuation actual evidence
Original START00:00:26; explicit2h continuation06:49:19.2870279..08:49:19.2870279+08. Old failed P0/B/R/W attempts and charges retained. Whole-Job final member peak/closure observation repaired; logical writer tell supplied; frozen helper factories and bounded pure scalar memo avoid repeated hash/parse overhead; synthetic pin timing follows frozen transmitter.
K8 andV12 passed. B12 actual business/parent evidence reconciled at B04_RECOVERY_05; current-source B01 actually completed in B_SCALAR_06, but that whole B replay timed out. SCALAR_FOCUSED_08 compared60328 scalar calls/error outcomes against unchanged decoder; focused equivalence is not a full D4 replay. W successor reuses and rehashes the complete first W input; no old partial backend output reused. Current W state: FAILED_STOP.
All data synthetic; real Pro capture, mathematics, HDL/EDA and hardware remain unverified. See backend_close and ignored final receipts; no future gate or publication is pre-signed.


## 2026-10-19 current runtime result
Original START 00:00:26+08, current explicit cutoff 12:00+08. P1_FILES_R01 passed; current B_FILES_R01 completed all 12 cases, C_CODEC_08 all 15 targeted cases; W_HOUR_10 completed the full 1130662-row actual R12/R11/R10/D4 software pipeline and byte-preserving original export. Old failed B/W attempts retain their original states and charges. CSV logical tell avoids per-row flush; bounded private codec scalar caches preserve options/error/container behavior; only file-count constants were raised by explicit authorization. All .py runtime bytes equal the W freeze; this README and CASE_MATRIX are documentation-only successors.
This is synthetic software L1 capacity/processing evidence. Real Pro, M1 mathematics, HDL/EDA, physical timing and hardware are not verified. Gates and ordinary remote publication are only proved by their ignored actual receipts; no future result is pre-signed.
