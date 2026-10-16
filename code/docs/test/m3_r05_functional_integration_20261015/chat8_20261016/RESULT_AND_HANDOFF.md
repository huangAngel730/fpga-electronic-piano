# chat8：M1 数学判据与夜间真实 R05 的增量对齐

2026-10-16，主对话2，基点 `57ad4aeb8ef0a1dad3fcfaf68f83aad6d08b0af3`。
本轮仅在分工的 software/docs 两个 `chat8_20261016/` 目录新增文件。
没有 Git 写入，没有新 ModelSim/RTL/Gowin/设备调用，没有联系审核员/预审员。

## 结论

**本轮输入解码与证据缺口分析完成，四独立频率→逐样本 PCM 数学补证仍 PARTIAL。**
`R01/ANALYSIS.json` 的出口 0 只表示软件分析成功，不是数学 PASS 或 R05 整机通过。
不重新实现 DDS/ADSR/分配器，也没有用正常输出倒推/填造黄金。

已核 M1 判据 MD：7737 字节，SHA
`d7a4ec69f04736fc414ab856c9e99893779e2b2192b16d2b727684fbba3e88c0`。
该 MD 不是完整第11包。第11包应为 750224 字节、SHA
`842fa8f75356090440a5e8237acafc209620d114f9e3c0ce2eab5ffdf30862da`，
应含 `INPUT_AND_ALGORITHM_IDENTITY.json`、`algorithm_reference/frozen/` 依赖闭包，
以及 416469 字节的完整算法 ZIP（SHA `5c18926ae307301e91ec0e44dcf4a48b2fb57adec71ad46c494b14df59913b06`）。
本次可访问范围的搜索见 `M1_SEARCH.json`；无匹配不等于证明别的电脑或不可访问目录也没有。
扫描1513个ZIP及其直接成员，11.719秒，精确目标SHA无匹配；保留40条访问/归档错误，
不声称穷尽不可访问目录或未递归展开的深层ZIP。搜索命令/工具返回见 `SEARCH_EXECUTION.txt`。
当前工作树同名模型不能自动视为该冻结闭包，不调用它们替代 M1 原件。

## 本轮确实新增的观察

只读核 A 原始输入 SHA、主 capture SHA、执行回执 SHA；核必要 11 项执行源码和全部9份 ROM
与原回执 `stage_before/stage_after` 相同。未重跑夜间 C 的逐请求期限/串行解码器。
按冻结 `audio_defs_pkg.sv` 的 64-bit 位域解码真实 `event_valid && event_ready && rst_n` 输入：

| pre-NBA cycle | 输入 | Velocity10 | 若成功分配的 Program 合同预期 |
|---|---|---|---|
| 38003 | Note On 69 | 806 | 0 / Piano |
| 72403 | CTRL_VOICE_SELECT=1 | — | 仅改变来源0/通道0的后续选择 |
| 110803 | Note On 64 | 645 | 1 / Triangle |
| 158003 | Note On 60 | 765 | 1 / Triangle |
| 196403 | Note On 67 | 685 | 1 / Triangle |
| 243603 | Note On 72（第五音输入） | 886 | 1 / Triangle |

六次输入与旧 C 的已导出日历逐项同值，新增 `source_line` 指向原输入行。
这些是实际输入接受，不等于槽位分配、victim、phase 或可闻声音已经独立证明。
表中 Program 是**源码合同预期**，没有把它填为 `program_observed_in_slot`。
原69按合同应保留 Piano；现有轨迹没导出该槽 `slot_timbre`，实际锁定仍 UNKNOWN。

真实配置握手一次，epoch0/cycle83、原输入第86行。
配置载荷没有导出；同版 board 源直接常量连接 enable1/delay1/dry32767/wet16384/feedback0，
这是静态接线证据而非动态配置载荷采集，不能错误套用子模块 reset 默认旁路。

## REUSED，非本轮重测

夜间 A/C 原件仍有效：真实253456沿；303请求/303提交及全部下一真实frame deadline；
302完整双声道帧（301请求+1启动静音帧）；最后 ID302/303 被末尾复位截断串行，非丢提交。
使用 `DIGITAL_SUMMARY.json` SHA
`d70f2dda0b58585609ed5ca5f6a2e769537bdebe4ddb9f233d858fc24ed523fc` 引用该限定结果。
L=R、clip=0；不能外推左右交换或非零clip错拍覆盖。没有重复旧 C 10坏轨迹、旧27/86项。
原6ms FAIL/7ms PASS历史不改；测试看门狗不是算法处理延迟或模拟10ms。

## 当前不能证明的项目与最小补件

| 项目 | 当前缺口 | 优先复用的观察点/必要条件（仅建议，不是采集许可） |
|---|---|---|
| 四路独立频率与相位 | 只导出active计数及最终混音，不能从谐波或nonzero认四路 | M1冻结模型闭包；按实际事件/请求日历计算；必要时提供router的slot note/source/channel/generation/occupied与实际lane_tick、FCW、bank waves/env同请求快照。phase优先独立推导；源码日历无法无歧义绑定时才申请额外只读phase观察 |
| Program锁定/第五音 | 输入Program已核，实际slot_timbre/victim未导出 | router已有slot_timbre、slot_note_on与generation/identity的同沿关联；不修改分配器或Program算法 |
| Q15/gain/mix | bank wave/env与occupied没有导出，不能以最终PCM反填 | bank公开result_valid/ready/id/occupied/waves/envelopes/FCW及混音前后边界；按M1 floor-Q15、空槽0、signed32求和再sat24独立复算 |
| 延迟历史 | 仅最终commit不包含效果器真正接受/取消后继续推进历史 | stereo_delay已有input_valid/ready/id/左右PCM/上游clip、config载荷/握手、frame/reset及output_valid/ready/id/左右PCM/clip；按每个已接受效果事务前进，绝不按成功commit数量代替 |
| clip数学 | 已观察最终clip全部0，不能测饱和端点 | 先按黄金未饱和值及上游/effect分项clip核当前样本；无超界输入就只签零clip范围，另行定向夹具须独立标记并经新的精确执行范围确认 |

M1原包到件后先判断能否由完整冻结模型和当前输入无歧义重算，不把“缺字段”自动变成必须重跑全链。
若仍需上述模块已有端口的只读采集，由总控/M2确定精确观察版本与一次预算；本轮不改TB、
观察板top、模型或公共接口，也不消费夜间剩余组。`first_valid`、启动初始化、末尾复位释放
恢复发声、正式物理、模拟延迟与板级继续 UNKNOWN，`board_release_allowed=false`。

## 软件自检和原件

命令（仓库根执行）：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_r05_functional_integration_20261015/chat8_20261016/run_delta.py --run-id R01
```

R01 已存在，不能原样重跑覆盖。两条 Python 子命令均退出0；9项新软件例通过。
本轮软件调度2.062秒（测试0.125秒左右，增量分析1.688秒左右），两步timeout=false。
正例：真实事件位域、Program仅影响后续合同预期、来源/通道/epoch隔离。
负例：非法hex/X/宽度/reserved、重复JSON键、非严格0/1、用汇总/谐波或完整字段名冒充数学PASS。
零力度NoteOn不当新音，非法Program不修改选择。所有合成例仅标软件测试。
原始双流、argv/cwd、Python SHA、源码执行前后 SHA 与timeout在 `R01/RUN_RECEIPT.json`。
新增分析没有运行数学模型或RTL。单步90秒/软件总预算180秒；输出新建拒覆盖。

交总控/M2：请先补齐完整第11包原字节，再决定是否确需新的数学观察采集；已签期限/串行不重跑。
仅本轮新软件分析完成，完整四频数学未完成，不据本结果放行正式码流。
Git发布由总控统一串行进行。本消息给真人 M2 仍为“待用户转发，尚未送达”。
