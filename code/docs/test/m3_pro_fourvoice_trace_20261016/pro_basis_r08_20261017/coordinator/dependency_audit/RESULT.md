# R08只读分组/新旧依赖核查（病例冻结前）

仅L0静态核查，程序/import/测试/HDL/EDA/设备/Git写入0。基线ef4fbc74b9d24e08de1e09d0be0eb3163118f258。5份输入大小/SHA及消费快照见ALLOCATION_SNAPSHOT.json。当前分配24项/24目录无重复，S/C/T/H各六项；未对尚未READY的代码/病例宣称通过，未触发任何消费。

## 五组边界：当前计划与授权相符

| 组 | 唯一范围 | 防止重复消费的具体边界 |
| --- | --- | --- |
| R | 尚未执行的R6-3/5新C3 profile/F-A/唯一计划及新跨包组合；总控PLAN限定更窄 | 仅冻结r08_integration的新case；R6-4已执行25、R6-6已执行28、RUN03旧15、D3旧24/25及R06/R07旧selftest/runner不调用。已有通过逻辑可纯函数复用，但旧case不能改名再计新检查。新增组合须明确新输出/新断言及旧SHA引用。 |
| S | 01–06，角色A/夜间2 | 六组件齐套后一次；03纯guard不能进R6-4.run/Popen，04竞争仅本包夹具账本+线程，不触碰总控真实CONSUMPTION。05不得跑EXE --version取身份。 |
| C | 07–12，角色B/夜间4 | 08只是唯一A采样器的独立记录组件；09核R6-5同一权威计划，不另产期望；同一F834/A835边界若已分R组，C10要验证新增关联表/双age/原行输出，不重复相同输入+相同断言。 |
| T | 13–18，角色C/夜间3 | 复用PinDecoder和R7-B，不启动它们的selftest/runner；13新增pins↔TX身份对齐，18新增解释输出，不能重跑旧串行/等价组算新成果。17不能复制R6-2旧23event，需新恢复断点。 |
| H | 19/20(A)、21/22(B)、23/24(C) | 三写者**一个H组**，六项及其精确输入/SHA全部冻结后总控只执行一次≤90秒；不是每人/每项90秒。22/23消费已冻结的16/19/21等输出或明确合成依赖，不重跑其它组case。真实输入缺件保留PENDING/UNKNOWN。 |

R/S/C/T/H各一次≤90秒，首组暴露具体新实现缺陷才各一次≤60秒对应增量；无变更盲重试/全组重跑不合规。全部测试在总控单个Python启动进程内执行：禁止subprocess/Popen/run、os.system/进程池/工具EXE、旧runner/未知设备；导入必须无启动副作用。普通文件/哈希/压缩/解析、本包原子占用和线程竞争可用。无子进程的边界包括依赖模块导入、CLI快捷路径与异常处理，不能只检查selftest源码表面。

病例READY后只需核四项：每组成员齐全；全局case_id唯一及输入/断言明确；相同旧输入+相同断言只读引用而不再消费；负例预期首拒收原因与PENDING/合成成功分类明确。冻结清单一旦消费，修复组只带该新失败和受影响边界，不回填新case到首组。此时五组初/修复消费快照均0；不将该快照当执行前锁。

## 新24项独立产物与旧件复用差额

| ID | 本轮必须新交的机器可读产物 | 复用／防重复边界 |
| --- | --- | --- |
| 01 | dependency_graph及递归include/search/readmem/唯一模块来源 | R6-1装配与C6只读；补两头/3边，不再封M2包 |
| 02 | module_ports/connections及方向/位宽/公开层级差额 | 复用R7-A/driver，表达式UNRESOLVED；不另造顶层 |
| 03 | spec→规范plan逐字段纯校验结果+R6-4接入diff | 若r07_fix已有相同guard则导入，新增安全字段差额，不复制实现或重跑25例 |
| 04 | capture_id/plan SHA/nonce/输出根原子占用与失败状态收据 | 旧R6-4并发case只作来源；新持久状态/nonce输出才计新增 |
| 05 | 静态工具本体/脚本/DLL依赖身份图及UNKNOWN | 不重扫旧873/1152运行时，不调用版本命令或加载DLL |
| 06 | 精确source/include/ROM/TB/工具/断言/预算申请清单及缺件 | 复用R6-4计划与R7-D引用；只能request，不产生准入 |
| 07 | 原61+版本化TX扩展的无损codec及原行/缺值信息 | 对接唯一R7-A与R6-3；29列不能反填，未知版本拒收 |
| 08 | RESET_EDGES记录组件/schema及源沿/首功能拍索引 | 由A原写者最小接入；不抢写R7-A，不force私有量 |
| 09 | 同份FRAME_PLAN的缺/多/重复/相位差额与raw索引 | 唯一生产者仍R6-5；复算核验不冒充第二权威生产者 |
| 10 | F/A/result/commit/cleanup关联表+双age | 不重写D3；保留F与A及同沿顺序，t-F<833独立于TX消费 |
| 11 | END/MONITOR_END/收据/尾段一致性及缺件报告 | 不重复R7-A写observer；EOF/timeout不能当正常finish |
| 12 | capture/source/clock/reset/calendar/frame/oracle/receipt模式依赖图 | 复用R7-D；同SHA/authority字符串不认证REAL |
| 13 | 串行位/槽↔实际TX身份的首位/首帧索引 | 只适配固定PinDecoder；PT8211按LSBJ16，不硬套I2S延迟 |
| 14 | 独立事务输入驱动的startup/HOLD/ID0/reset新场景 | 不用DUT标签反填；旧28case不复制 |
| 15 | result握手→pending→held→TX双clip/valid/error谱系原行 | 保留tx_clip单bitOR与mask左右，不能取当前result冒充旧commit标签 |
| 16 | 原始MIDI pins解码与byte/event到达窗口对照 | 复用R6-2计划但实际到达独立核；不能串行四音伪同拍 |
| 17 | 支持规范内的半消息reset/失步恢复等新外部计划 | 原23event不重做；未确认策略UNRESOLVED，应用≠到达 |
| 18 | R7-B差异首现场解释/允许差异依据/raw索引 | 不新建第三top，白名单不得吞生产PCM/pin差异 |
| 19 | 实物照片/芯片/修订/测量ID交叉索引 | R6-7只是资料底座，官方图/合成图≠实物 |
| 20 | Bank/方向/VIH-VIL-VOH-VOL带来源裕量/UNKNOWN | 数据缺失不填标称实测，不改接线或默认Bank |
| 21 | 仪器时基/校准/量程/分辨率/误差profile | 无设备访问；声卡与LA时钟分开，无校准不出精确结论 |
| 22 | 同会话输入-数字-模拟延迟区间/误差/触发依据 | 阈值/公共时间轴未知就UNKNOWN，不能听感签≤10ms |
| 23 | MIDI/UART/LA/WAV/.fs/会话离线原件索引 | 复用R6-8步骤/格式，不打开串口，不把截图当原音频 |
| 24 | Part/version/完整STA-CDC/.fs/恢复/精确SRAM许可关联缺件 | M2原件未到保持PENDING，不能自造许可或迁用PG484 |

独立产物须由实际代码/可运行CLI实现，空schema/README不是交付完成；旧功能完整复用时登记“复用+尚缺差额”，不能把同一结果再计新增完成。当前不验收这些尚在实施的产物。

## C6与仍缺真实输入

C5漏两头/include路径已被M2明确勘误，保留历史；新C6保持71源/9ROM，新增`sine_table.svh`与`sustain_controller_ports.svh`、3条include边。C6 ZIP声明SHA `155177a23ae724a1c8d9a0ca3480781d0b76ae62f5a95f59c65a15a96e0d70e4`；解包inputs为cwd，首行+incdir+include，ROM相对rom/。R8-01验证原件图，A/B只在新装配引用C6，不覆盖旧C5。实际编译器开关兼容、HDL、M1十九语义及config/apply_seq/audio_stable、真实工具安全/准入、Part/Bank/商业许可/完整物理/新.fs/恢复/SRAM仍未签。

M2 R08报告中的“R6-4七历史组”应按原台账理解为**一个组的七类case**，不能据措辞重算消费。R组新授权现允许验证此前L0的R6-3/5，但不会把其测试倒写成R07已执行；本轮结果另记R08组。总控角色映射保留旧包原写者，未按R08抽象角色表转移原包写集，当前未发现分配/配额的具体冲突。后续只在READY后核case清单；不请求或消耗额外功能额度。
