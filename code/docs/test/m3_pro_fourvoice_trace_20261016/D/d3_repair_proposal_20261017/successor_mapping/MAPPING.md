# D3漏洞与现有monitor／B1／B2映射（静态）

**没有现成后继完成D3原入口的返修。** 已存在可复用的期限前置检查和取消账本，但计时锚点、事务终点、输入格式均不相同。下表“已覆盖”仅指对应后继自身范围的源码/旧证据；本轮功能执行0，所有新推演均非实际PASS，D3仍PARTIAL/REWORK_REQUIRED，真实Pro仍PENDING。

## 精确源

全部读取当前c7e0144树。monitor工作树blob与414e1a9指定路径一致；B1/B2工作树blob分别与5aa4959指定路径一致，未应用补丁。完整绝对路径/字节/SHA见INPUT_IDENTITIES.json。

| 代号与仓库路径 | SHA256／关键行 |
| --- | --- |
| D3：code/software/m3_pro_fourvoice_trace_20261016/D/ingest/ingest.py | 3217f97e57daec534306a213c64566fa111e3116f15a15967ca881847c218e07；96–124、130–132、164–169 |
| M：code/tb/board/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/pro_frame_monitor.sv | faf7cda22f928e7f0c40bd7ed164213e2282078e213ee1f472b331cfe098295a；66–105、119–128、145–163 |
| B1：code/software/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/check_observation_binding.py | 32af2a7d32c1e0e9a4b9451da3310c27eda20eaf96bfccb87f229b858a81951e；72–88、109–110、147–162 |
| B2：code/software/m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017/adapt_serial.py | c393a0d223781260101be1e553f3b7a1be2840547970d57902de97d69007b954；36–58、104–126、137–176、210–239 |
| B2加载器：同目录common.py | 086807e75aa18757ca68c8196b2c86f02d02788e9eda6bf2a09f5990f6b5def9；40–44 |
| PinDecoder：code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02/consume_capture.py | da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb；138–176 |
| 历史共同tick源：code/rtl/board/polyphonic_envelope_bank.sv | a9ac7a73ad1a3bd4e586f31a9e8bec3fac5a173ce956d05e420a41c48fca7119；45、58–81、97–114 |

## 逐漏洞覆盖

| D3缺口／原定位 | monitor M | B1 metadata | B2串行桥 | 可复用修法与仍缺内容 |
| --- | --- | --- | --- | --- |
| 漏截止FRAME后普通记录继续；D3仅收到FRAME才设due_cycle（109–124） | **部分**：每沿cycle递增（66–67），相邻帧833/834和均值检查（89–100）；无FRAME且未finish时超过834拍拒FRAME_STALLED。不是独立完整帧日历。 | **未覆盖执行行为**：public_trace只按字节/SHA读为身份（72–88），不解析事件（155–162）。 | **部分**：CSV行从1逐拍连续（52）、已出现帧的ID/间距/均值（177–185、220–221）；原pins连续时PinDecoder的FRAME_WS_BOUNDARY_PHASE（158）可发现帧与WS脱节。但下一帧来自被审CSV（117–126），无独立预期帧全集。 | 复用连续沿、相位与局部cadence检查；D3稀疏事件需显式独立帧日历/冻结相位。不能只看下次FRAME再定截止。 |
| 超期CANCEL用due=None清状态（164–168） | **自身已覆盖接受→清理预算**：71先查pending年龄>=833，早于reset/cancel；123再次检查，102–105清理。 | **未覆盖执行行为**：cancel_reset_priority仅声明字符串（141–145）。 | **自身已覆盖账本清理期限与匹配**：独立账本finish−accept<833（104–115），实际cancel须等于账本，清active（149–155），commit-on-cancel拒收（150）；缺取消/悬空终态拒收（210–218）。 | 两种“先检查、后清理”可复用；D3需从REQUEST及真实下一帧计算，不把接受+833直接替换请求帧截止。 |
| 超期RESET抹状态／帧历史；D3仅未终态才核<834（98–105） | **部分**：pending超期在进入reset前拒（71）；但reset清have_frame/intervals（81），不能证明复位前完整帧日历。 | **未覆盖执行行为**：只声明clock_reset_epoch/cancel优先级。 | **部分**：真实reset清active须账本cancel_cycle匹配（139–148），账本事先核<833；逐epoch隔离。未建立跨reset之前应出现的全部帧集合。 | D3每条事件进入RESET分支前检查截止/漏帧；合法提前reset允许重建新epoch相位，不能让迟到reset回溯擦除旧epoch缺口。 |
| END只查终态，取消后绕过截止（130–132、169） | **部分**：finish核pending/保持状态与accept=commit+cancel、唯一结束后禁沿（68、155–163）。99行明确!finish，故finish可跳过该沿的FRAME_STALLED；这不是独立日历完整性证明。 | **部分声明门禁**：147–154检查exit0/未timeout/finish/end/unique等布尔声明，但不解析原stdout或轨迹证实。 | **未覆盖真实结束闭合**：85仅capture_end_cycle等于末行；210–218核账本清理。223–228明确保留RESET截断/UNKNOWN尾部，238明确无MONITOR_END/finish声明。 | 复用终态与计数守卫；D3 END前仍需核独立帧日历及截止。真实采集的成功退出、唯一MONITOR_END、finish/END应另外绑定并核内容。 |

monitor的finish例外、reset清帧历史以及B2尾部UNKNOWN均为本轮静态阅读边界提示；没有新跑对应反例，也不扩大本轮为monitor/B2返修。D3定向补丁由patch_proposal窗口提出，本表只说明复用与缺口。

## 原反例的同义边界

M2原件code/docs/test/m2_pro_offline_review_20261017/D3_COUNTEREXAMPLE.json：req8在1677 REQUEST、1678 ACCEPT、1712 RETURN；漏FRAME2510；CANCEL2512、END2513，REQUEST年龄835。D3 166只看due_cycle为空；167改CANCELED，131/169只看终态及全局consumed/resets。req7已消费，故控制流静态推演可到PASS；**M2及本轮均未运行该新CLI反例**。

若把同样的接受/取消拍号写成B2合法账本，2512−1678=834，113行预期拒SERVICE_DEADLINE；若monitor的pending保持到2512，71行应已拒REQUEST_DEADLINE。这些是静态预期，不是实际日志，也不等于D3已修。尤其monitor/B2通常在commit清在途（M152/B2 170），D3在RETURN后仍等待下一帧CONSUME（151–162）；不能把RETURN、commit、TX采纳或串行完成合并为同一“完成”。

## 已存原件支持范围

下列全部只读原位置，不重新装包或执行。机器化输入清单保存各原件SHA。

- D3旧ROUND_02/RESULT.json及late_cancel/trace.jsonl、stderr.txt：旧late_cancel含截止FRAME2510，只证CANCEL_AFTER_DUE_FRAME分支exit1；不含“漏FRAME2510”的M2新反例。
- monitor旧D/pro_monitor_20261017/ROUND_02/RECEIPT.json，case_21/22.stdout.bin＋receipt.json：接受+833取消/复位均原exit1，FIRST_REJECT REQUEST_DEADLINE cycle859；case_23/24同类原件为+832清理原exit0、MONITOR_END。它们支持严格接受预算，不签D3稀疏记录截止。
- B1旧pro_binding_20261017/B1_ROUND_01/RUN_RECEIPT.json及case_00.json：原结构正例仍authority_verified=false、real_trace_calendar_checked=false。不能用39项metadata拒收作D3漏帧覆盖。
- B2旧pro_serial_successor_20261017/ROUND_01/RUN_RECEIPT.json：19项原版本检查；ROUND_02/RUN_RECEIPT.json仅3项取消增量。合法取消原exit0，unexpected_cancel_before_commit原exit1/UNEXPECTED_CANCEL，commit_on_cancel原exit1/COMMIT_ON_CANCEL。没有新增“D3漏FRAME2510＋迟取消”实际验证，也不能说最终22项全量重跑。

## 三个禁止等同

1. **scalar lane不等于真实共同tick mask。** M端口11–13、124–128每沿只有一个lane；历史envelope_bank 45、58–81用同一lane_tick推进四个g_lane，适配时须在原沿表示mask1111。B1合同OBSERVATION_CONTRACT.json（SHA d89076836f8c60dd6544bbf2d9a5e8fa2f645ef49c8860458210562adf12d716）443行及md10行已明确；B1代码109–110只是允许COMMON_TICK_MASK／SCALAR_TICK_ONEHOT_PUBLIC_MAP标签，不转换数据。B2含lane列但不验证推进完整性；不能造四笔错开交易或把slot当lane/frame ID。
2. **metadata不等于逐轨迹验收。** B1 check只核公开映射声明和引用身份；source/ROM真实出处、HDL公开出口、真实事件/帧日历与结束内容均待M2及B1真实接入。B2的basis同值也不签来源真实性（75–81、237）。
3. **加载D3不等于调用D3.intake。** B2 common.py40–44仅导入D3后调用decoder()，复用固定SHA的PinDecoder。adapt_serial.py62/128/173调用解码器，而非D3.intake；不调用legacy.analyze。修好B2取消账本不会修D3入口，monitor也没有调用D3。

## 给总控／M2的最小结论

已有局部修法可用：独立账本预检截止、所有清理前检查年龄、实际清理拍与epoch/ID一致、连续沿及原始行号、结束终态守卫。未有可直接替代D3的完整后继。应先由M2绑定实际新后继路径、独立帧日历/同cycle顺序、定向输入及单轮软件预算，再对D3原缺口做最小增量；不得修改封存原件或重跑已核其他包。当前只完成L0静态准备，实际修复/CLI/真实Pro均待许可或待件，board_release_allowed=false。
