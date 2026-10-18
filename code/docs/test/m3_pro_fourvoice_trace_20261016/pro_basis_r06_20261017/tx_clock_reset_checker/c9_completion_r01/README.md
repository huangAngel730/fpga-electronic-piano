# C9 TX / 串行流式接入

本包为 task-day4、夜间任务3的独占后继。状态为 **READY / L0 静态检查，NOT_RUN**。候选、用例和原件生成仅由夜间1总控在全新 TASK_DAY4_REMAINDER_SW 台账执行；成员没有导入、编译或执行。

- 入口：serial.py 的 analyze_files(public_rows_path, frame_plan_path, output_dir, expected_scenario_ref=None)，返回报告字典。输入支持文件路径或 path/bytes/sha256 描述符；输出目录必须不存在且位于仓库内。
- 唯一输入封套为 M3_R7A_C9_PUBLIC_ROW_V1，完整74字段、source一基行号/零基cycle/25,000ps间隔、capture/raw/reset/origin绑定；原公开JSONL保留所有raw_ports/events/semantics，不从61字段补造。ROW_INDEX逐行指向该输入SHA/原行号。
- 只读复用固定PinDecoder与R6-5独立FRAME_PLAN原校验函数；本包不生成计划。原生产者路径和固定SHA见DEPENDENCIES.json。原计划source_identities每项必须恰为path/sha256两键，不能直接塞入含bytes的artifact描述符。
- 分别核内部F/A严格t-F<833、下一FRAME边界与TX833/834；startup空ID、合法数字0、新采纳、HOLD的PCM/双clip、result/commit/reset/finish及完整串行字。按实际读取字节增量哈希，再核读后身份。
- 未知phase/资格/关键控制使交易/串行链停在UNKNOWN直至reset；不会清零修复。缺独立TX期望时选择策略PENDING；给定期望必须位于计划FRAME。正常FINISH/END仍有已知未完交易拒收；串行半帧/尾段保持UNKNOWN。
- 输出SERIAL_FRAMES/SERIAL_HALVES/ROW_INDEX/TRANSACTIONS JSONL及REPORT.json。失败保留已写部分与FAILURE.json。限额：公开输入64GiB、总JSONL输出16GiB、单行8MiB、JSON元数据16MiB、FRAME/请求各最多200000。
- selftest.run_case(id, output_dir)定义6个新接缝；manifest位于tb/board同名c9_completion_r01/CASES.json。全部NOT_RUN。合成NCO/PCM/独立basis仅用于接口测试，不能当真实DUT捕获或数学黄金。UNKNOWN回归期望由basis和独立计划坐标构造。
- OLD_CASE_SELECTIONS.json只引用原T27和原C9 B13及依赖闭包，不复制其期望、不执行、不复活旧额度。

CLI：serial.py --public-rows <file> --frame-plan <file> --output <new-dir> [--expected-scenario <file>]。一致性/UNKNOWN报告返回退出码3；异常拒收保留FAILURE并抛出。CLI本身不授予执行权。

自审修正：重复result握手、关键未知后的硬比较、丢失FRAME造成索引漂移、未知覆盖后的期望误拒、跨reset gap混用、读取流身份。只读子智能体最终未发现该增量具体阻断，仅静态阅读。实际验证等级不升级为仿真/综合/时序/上板；real_pass和board_release_allowed始终false。独立映射、audio_stable、M1 PCM黄金、真实执行来源与设备实测仍待。NoteOn文字按dfee2c14在L0关闭，不再请求勘误。

未暂存、提交或推送；由总控统一冻结、执行和串行发布。本地READY供总控读取，不能冒称M2已收件或签收。
