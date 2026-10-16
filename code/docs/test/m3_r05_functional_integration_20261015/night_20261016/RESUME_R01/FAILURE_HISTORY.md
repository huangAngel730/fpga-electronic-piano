# A恢复批次失败原件（尚未最终收口）

旧night封包和已暂存77文件只读，未覆盖。用户本次恢复授权在总控对话userMessage `01a14237-c04d-7d41-ae9d-cd8493ff0dd9`，正常提升审批本批已放行，无新审批拒绝。

1. `RUN_01`：恢复准备失败，无version/functional进程、无消费。首次复制到 `execution_sources/<repo relative>` 遇Windows长路径。旧runner误将未建立tool_before情况下的准备异常覆盖为`IDENTITY_CHANGED`；此份原收据保留，不回填未知异常原文。`DIAGNOSTIC_01/RESULT.json`在新诊断目录无工具启动复现FileNotFoundError，目标字符串长262。恢复runner采用`source_snapshot_layout=FLAT_RELATIVE_SHA_MAP_V1`及`source_snapshot_files`完整relative→snapshot路径/大小/SHA映射，并保留original_exception。C需最小适配此映射；旧源快照实际缺失处不冒称完整。
2. `RUN_02`：本批实际功能组1，消费标记`RUN_02_CONSUMED.json`。固定工具版本/EXE/静态依赖pin与旧2020.4一致，vlib通过，vlog报2个vlog-2730：新观察config wires声明在过程使用之后。未启动vsim。原双流/argv/退出/耗时见RUN_RECEIPT和logs。`FIX_01`仅将新观察wire声明前移，未改算法/ROM/激励；修前/修后/增量diff在FIX01_RECEIPT。
3. `RUN_03`：本批实际功能组2，消费标记`RUN_03_CONSUMED.json`。vlib/vlog通过，vsim在12.5ns第一个40MHz正沿触发`R05_OBSERVER_UNKNOWN_PUBLIC_PORT`。原reset_sync在常低复位开局的pre-NBA第1沿尚未初始化；当次新监视器没有填0/跳沿。捕获仅HEADER/END、输入仅HEADER/INITIAL_INPUTS/END，不是有效业务capture，不出READY。原双流和源本体齐备。

以上前两组之后，总控明确接受分段原始采集，合同和机器字段已在最后执行前固定。

4. `RUN_04`：本批实际功能组3，消费标记`RUN_04_CONSUMED.json`。FIX02的vlib/vlog通过，vsim在1587500ps触发`R05_STARTUP_OVER_64_EDGES`。STARTUP_CAPTURE与STARTUP_INPUTS各保存64个连续pre-NBA正沿，12500ps起、间隔25000ps；其中音频公开字段只有`clipped`持续`z`，其余音频字段全部已知。主capture仅HEADER/END，TICK=0，无boundary。不得把此段剪掉或填0进入主段。

最新原件纠正前述首沿解释：RUN03聚合检查只能证明存在未知，不能证明它来自reset初始化。RUN04逐字段原件明确定位持续`clipped=z`；源码显示该新增观察wire在generate中连接后才在外层声明，符合局部隐式net与外层未驱动net分离的作用域问题。这是新观察候选连接问题，不是已确认算法失效。ModelSim编译虽0错误，未对该隐式net给专门警告，不能以无warning代替scope核对。

总控最后“只读定位、不实施新修复”的消息到达前，本窗口已在原隔离范围生成仅前移该wire声明的`FIX_03_PENDING`静态候选与diff（见FIX03_PENDING.json）；**未编译、未运行、不能声称修复成功**。收到新限制后停止所有进一步修复，保留该未执行原件并明确时间顺序，不删除或冒称它是运行源。

最终实际功能额度3/3已消费，剩余0；没有第4功能组。输出编号RUN01为准备失败，RUN02/03/04才是实际三组，编号不等于消费数。算法/ROM/时钟/正式接口保持只读。后续执行须新的有效授权，当前以PARTIAL封存。
