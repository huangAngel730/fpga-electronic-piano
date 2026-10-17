# M2 只读限定复核：M3 R6-5 / R6-6 / R6-7

被审提交：`ffc8b4cc94606cdd70941d2abaee8bbd93a654c5`。外层证据包 SHA-256：`ac9bcb31d21b3af247ca6305b2d83c76922a657ae743a5c4690d294ceb1ca205`，4105410 字节，ZIP CRC 全部正常。

本次只读取 Git blob、证据 ZIP/JSON/原始流与必要合同；没有导入或执行被审 Python、CLI、HDL、EDA、设备操作，没有修改被审源码或共享状态。下述反例均是静态控制流推导，`NOT_RUN`。

## 可接受的既有证据边界

- R6-5 RUN_02 summary 与 receipt 一致：14 项 = 1 合成正例、3 PENDING、10 预期拒收，exit 0，0.176560640335083 秒。RUN_01 首次夹具 writer 失败仍保留。正例只有 99 稀疏行，其 FRAME 是夹具预列的 50000、150000 等，不是真实 40 MHz/48 kHz 运行日历。
- R6-6 RUN_01 summary 与 receipt 一致：20 项 = 1 合成正例、7 PENDING、12 预期拒收，exit 0，5.205964088439941 秒。正例走 run_files，19 个非正例由 selftest 内存变异后调用 analyze；不应表述为 20 次 CLI 原始输入采集。正例确实包括 startup、真实数值 ID 0、同 PCM 不同 ID、HOLD、reset 截断等合成路径。当前生产 checker SHA 与 source_before/source_after 均为 `19673112f977bd559fe86eddd4f4cac7070c9a6bd7d71df00f5bff0f8a23f115`。
- R6-7 17/17 修复后软件自测原件存在，第一次路径 wrapper 错误原件亦保留；生产记录 fixture_only=false、board_release_allowed=false，20 个物理/工具声明组全为 PENDING/UNKNOWN。可签软件校验器准备，不签实物电气、工具可用或板级通过。
- event_calendar 当前生产 checker SHA `96a130ac0e17140c342dd15af05d124bc66287694b0e25f6a3d4657217197ac7`；原运行 SHA `3df7c588faeb7e381a57138d9b8a93a37df4008fdc3865635a19d44fcb6d0e3c` 的差额由附带 POST_SEAL 记录明确声明为仅删除一个最终 LF。不把当前 SHA 冒称原运行 SHA。

## 接入真实链前的具体阻断

1. **R6-5 强制 F=A，拒收合法真实采集。** `event_calendar.py:290-299` 在 frame_tick=1 同沿强制 req_valid&&req_ready、advance_mask=1111 并把 advance_frame_req_id 与该行 req_id 直接绑定。已发布 C1/R07 明确 F 时 buffer 才 NBA 置请求，A 最早 F+1，advance 属于真正接受后的 M1 语义。最小静态条件：F=834，frame_tick=1，req_valid=0；A=835，req_valid=req_ready=1。该合法分离在 F 先报 FRAME_WITHOUT_REQUEST。最小修法：分开 FRAME 账本 F、首 valid、ACCEPT A、共同 advance，按同版公开导出确认关联；不得挪动 A 去满足旧 D3。

2. **R6-6 从 A 而非 F 检查 `<833`，会漏掉 F 预算越界。** `tx_clock_reset_checker.py:220-229,321-324,347-350` 的 transaction schema 只有 request_cycle，按代码它等于实际 req_valid&&req_ready，即 A；没有 frame_cycle F，亦未要求 result/commit/cleanup 严格早于下一独立 FRAME。最小静态反例：独立 F=834，A=835，result/合法清理=1667，则 t-A=832 被当前年龄式接受，t-F=833 应拒。若取 result=1666、commit=1667，result年龄可过而实际完成链已到下一 FRAME，当前也未按 F/next_FRAME 阻断。最小修法：交易 schema 显式增加 F/首 valid/A 与原行关联，严格核 `t-F<833 && t<next_FRAME`，另报 t-A；三类完成/清理分别按 M2 冻结定义核。

3. **REAL 模式能够混入合成权威输入并产出真实 PASS。** `tx_clock_reset_checker.py:134-174` 在 REAL 分支只切换五个 binding 字符串，但 calendar/frame_plan/oracle 的允许集合始终同时含 SYNTHETIC 与 REAL；输出在 479 行仅按 status 设置 real_pro_tx_pass。保留已通过的 valid_synthetic 全部文件，仅把 binding.mode 改 REAL_PUBLIC_TRACE、五个 authority 改 REAL 分支值，calendar/frame_plan/oracle 仍为 SYNTHETIC；inputs_sha256 无需改变，后续算法与已过正例相同，静态可达 PASS_REAL_PUBLIC_TRACE。R6-5 同类自报字符串/布尔也不是真实性证明。最小修法：REAL 分支分别只许真实类型，并要求同版 capture/source/ROM/工具/实际退出/完成收据由 M2 可信准入或 R7-D 来源链提供；在可信入口不存在时 REAL 返回 PENDING_SOURCE_PROVENANCE，文件匹配本身不签真实性。

4. **两包 FRAME_PLAN schema 未接上 R07 唯一生产者；只有帧间隔无法证明初相位/全窗。** R6-5 用 `M3_R06_INDEPENDENT_FRAME_PLAN_V1` + frame_cycles；R6-6 用 `M3_R06_TX_FRAME_PLAN_V1` + cycles。R6-5 输出 report 并不生成 R6-6 所需计划；R6-6 的闭式 frame_cycles 只在 fixtures.py，生产 checker 仅比对给定列表/833-834/三间隔和 2500。冻结 reset/lock/stop 输入、n=1 功能沿及真实结束回执没有进入生产公式核验，无法防同样挪动期望与 trace 首相位。最小修法：R6-5 按 C1 冻结输入唯一生成版本化 FRAME_PLAN，R6-6 只读同份并复算公式/完整覆盖至真实 finish，缺初相位/结束回执保持 PENDING。

5. **C3/R07 TX 扩展尚未适配，不可直接声称接好了 sidecar。** 两包 integer 校验强制 tx_req_id 为整数；R6-6 `load_trace` 拒所有额外列，BIT_FIELDS 仅接受旧 scalar tx_clip。C3/R07 已定义 startup req_id_valid=false 对应 null、数字 0 是合法 ID，保留旧 scalar OR 但新增 tx_clip_mask、tx_metadata_valid、metadata_error、tx_frame_overflow 等。按当前 C3 正确归一化的 startup `tx_req_id:null` 会被拒；保留扩展列会 UNKNOWN_TRACE_FIELD；丢弃双 clip 会无法区分 01/10。最小修法：显式新增支持的 schema/profile，保留 null/validity/dualclip/sticky/overflow，旧 61 字段入口保持旧 profile，未支持新 profile 时返回 PENDING_UNSUPPORTED_PROFILE，不做丢列/填 0。

## 建议 M2 签收

七包总体可按软件/静态准备和原件归档限定接件；本范围 R6-5/R6-6 仅历史合成 L1 证据，当前 R07 真链准入不通过，真实 Pro 仍 PENDING。上述阻断交 M3 在新明确授权写集/额度内修复，旧测试组和旧额度不恢复；本次不代改、不代跑。R6-7 保持生产 VALID_PENDING、board_release_allowed=false。
