# M3：T052 P0-1／P0-2 精确静态组合

2026-10-13，用户明确主代理做 P0-1、子智能体做 P0-2。子智能体完成 checker／新24单测／完整软件反例，主代理完成 driver／observer／新8调度单测并整合审计。仅新增对应后继目录，旧源、DUT、ROM、数学定义、共享表和消费许可保持原字节。

## P0-1

新 `tb_t052_control_128_v2` 将驱动索引与观察编号分开。软件从新源有界调度语法和原170-bit memory逐字段推全部128沿，行0／1／127不漏重；时钟20ns、首沿10ns，四复位事件精确为0／40／1280／1320ns。公开observer在active区pre-NBA取值，异步reset原始转移单独记录，四轨迹绑定全部来源／时间元数据。

最终P0-1资格：`code/output/m3_t052_p0_1_20261013_02`，8方法通过，exit0，写收据后总耗时0.125秒；全部源码／输入前后SHA同。旧调度0,2,…,127,127可由原源软件重建；偏移、停步、末行重复、修改边界数据、错误时钟、延迟观察、漏异步reset与隐藏输入驱动都被拒收。源差异和全窗推演随包。

## P0-2

先用固定输入＋已冻结 `publication.calendar` 求128沿pins与6接受／3发布／3取消，再打开四观察轨迹进行精确比较。正常软件fixture通过但`RTL_verified=false`；新schema全ready／valid清零完整反例exit1命中`SOURCE_CALENDAR_PINS:0`，伪来源SHA完整反例exit1命中`SOURCE_META:controls`。END的bool／float、错误沿间隔／复位时间、包外自报来源、缺失实际receipt、篡改源／快照／命令／工具／日志／产物均有新拒收检查；开放窗口仍UNKNOWN。

M2原两完整坏轨迹保持原字节、未改标签，因旧META不能满足新合同拒收；它们不是新格式功能拒收的替代证据，新schema等价完整坏轨迹单独保留。

子智能体P0-2 `_02`首交通过后，主代理仅将fixture清单诊断改为精确索引0，并给新软件资格器补每步失败收据、输入漂移和最终预算拒收；`_03`因沙箱临时目录PermissionError失败，原收据和原日志保留。同源码普通权限运行 `_04`：24方法＋正常／两目标CLI均符合预期，exit0／0.453秒，源和依赖前后SHA同。子智能体原`SOFTWARE_RECEIPT.json`保持其当时`_02`状态，当前整合以`_04`收据为准；不回填历史。

## 组合身份与后续

`P0_1_DRIVER_20261013/combination_manifest.json` SHA：
`0949f09747f517b08b36d6df78f8712111bb84f2da152b5a6969986532421b6c`。

它固定原DUT／DDS／mixer／ROM、plan、日历、新TB／observer／memory，以及本机拟议compile/runtime可执行文件SHA和拟议argv。`execution_authorized=false`。本轮没有实际128沿编译／仿真收据；真实工具依赖闭包、执行机器与实际一次采集范围仍由M2精确批准。执行许可必须另给，不能从软件夹具或本manifest反推。

请M2预检此同一静态组合，并由M1只给算法／事务语义意见。旧4207完整性仍UNKNOWN；完整T052/T060/T061保持PARTIAL。新候选lower／compile／VVP／Gowin和设备操作均0；如后续发布运行强制仓库门禁，既有T007/T019另列，不冒充本候选采集。

具体Git发布身份、包SHA及必要门禁以随包发布收据和用户转发通知为准。本交接待用户转发，尚未送达。
