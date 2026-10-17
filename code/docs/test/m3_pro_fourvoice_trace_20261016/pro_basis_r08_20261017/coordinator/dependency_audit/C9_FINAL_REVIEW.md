# C9 最终增量只读结论

基线 `16ac226552f6fb65347b229b8fad42146ed45644`；等级 **L0 / STATIC / NOT_RUN**。只核 C9_DELTA_01 的具体迁移点及其实际后继。结论绑定同名 JSON 的文件 SHA，不覆盖之后的并发修订。未 import、compile 或执行候选/夹具，未运行 Python 功能组、HDL、EDA、设备，未消费/恢复额度。只写本 dependency_audit。

**最终所读增量范围内，前次具体迁移阻断均已有静态修法，未保留新的具体阻断。** 这是静态源码结论，不签执行、行为等价、真实捕获或准入；不能代签完整C9任务通过。

## 已静态闭合的前次具体项

- **A 完整采样**：新 `r7a_c9_public_observer.sv` 在实际 `posedge obs_core_clk` 无延迟 `$fwrite`；67 obs 口及5外部 pin 共72 raw量均在接口/格式/实参中可见，signed PCM 为24位。新 TB 从 C9 DUT同名直连被动采样器，driver ready 仍独立。`C9_COMPLETE_CAPTURE_MATRIX.json` 列72 raw量/74字段，69直接映射，cycle/epoch/finish独立记录，只有 apply_event_seq/audio_stable缺真实来源。未见用请求接受推造 lane_tick。
- **R8-02 漏接输出口**：`c9_ports.py` 在旧 lexical checker 外增加67口方向/width/signed、DUT/passive唯一同名非空连线要求，前次“旧 parser ACCEPT 不等于完整采样”的具体缺口有对应保护。仍返回 PENDING，不产生执行许可。
- **阶段/config/clip**：A codec 保留 kind/mask/router seq/valid，各行不去重；kind3/4/8零哨兵标无效因果，kind0闲置不作事件解释；config只在实际take解析62位，三clip独立保留。apply_event_seq/audio_stable为null+明确待件。C新桥保留整个74字段及阶段/三clip，已移除旧61字段限制。
- **四 lane 与请求 tag**：C `_lane_advance` 只在精确1111给 all_four_lanes=True，mask1为PARTIAL且False、X/null为Pending；F仅取frame_tick，请求tag原样保留，不别名F。
- **B 同名源隔离**：实际读取 `SOURCE_BINDING.json`、两路compile.f、两个TB及`c9_pair.py`，并在README/A_DEPENDENCY到件后核说明：original/observer有独立cwd/源清单/TB，原路使用原top，新路使用C9 top，`assemble`要求compile_universes_separate，未看到把两路同名M1定义拼成一次平编译。observer伴随量在实际c9_obs_core_clk沿采；转换不去重，独立seq/audio_stable保持None。此为有限文件阅读，不是对全部源体/展开的证明。

## 同轮并发修订已闭合：A→C 封套适配

初读 C 源 SHA `f1d0fa28a71f7407d7c0885b605c636d6ac1e5cb474c1ce72ab973c562283526` 只收C自有封套，与A实际封套/schema/source/字段顺序不一致。封存时检测源码并发变动，只读取对应适配/序号修复增量，最终读取 SHA **`bbb4294e58052c8b8b65aca6eda29e44e539a0c36def2fd4f626ae92d3b0b603`**。

新 `_adapt_r7a_public_record` 与 CLI `--input-format r7a-public-c9` 直接收A实际封套，核74字段集合、origin/source，再按冻结顺序复制字段；raw_sha256正确映射，plan_association=None。原A文件按trace_input的path/bytes/SHA及各物理行raw_line_sha256绑定；原source/raw_ports/missing_reasons/events/semantics还逐行保留在upstream_evidence，不要求手改中间JSON。README已给该入口，`_bind_pending_trace`按实际输入字节建立descriptor。前述A→C格式阻断在最终所读版本静态关闭；实际A产出的PUBLIC_ROWS_C9尚缺，未声称真实接入运行通过。

## 同轮修复已静态关闭：声明式 association 冒充独立计划序号

在中间SHA `400113b31191957c62564c036e3067f685c71f370ad1c9f8f1b89f355adee06e`，`_plan_sequence` 仅核association文字/序号/路径与hash格式，未读计划或实际接受记录，存在以自声明序号冒充独立映射的静态反例。没有执行该反例，也未将其写成真实运行结果。

最终SHA `bbb4294e58052c8b8b65aca6eda29e44e539a0c36def2fd4f626ae92d3b0b603` 的228行起已改成：association非None或apply_event_seq非None即抛 `INDEPENDENT_PLAN_MAPPING_UNVERIFIED`，否则只返回None。对应自测已改为 `INDEPENDENT_PLAN_ASSOCIATION_REJECT`，README明确无原件不接受声明式映射；A适配路径也不伪造association。因此前述反例在最终所读源码静态被拒，独立序号继续PENDING。待运行用例只是代码定义，未消费组或产生PASS。

## 交接与未验边界

本次无保留给唯一写者的新返工项；A/R8-02、B、C均只在上列实际阅读边界内未发现前次同类具体阻断。不作全面审核通过声明。M1 NoteOn勘误、真实plan映射/audio_stable/trace/FRAME_PLAN/PCM及周期行为、可展开性和物理项仍待；同名源隔离、静态fixture和L0不升级为执行通过。

本地供总控读取，未发送跨窗口消息，未重试此前被拒通信；未提交、未推送、未动既有暂存/原封存。总控按实际READY版本收件，任何后续修法需另核SHA，本报告不追签未来版本。`board_release_allowed=false`。
