# R7-A 首组前自审

只读源检查，未执行HDL。核对M2公开38口及R6-2实际driver：不窥读私有DSP；driver ready输出只进未使用wire，不能接DUT输出；独立40MHz激励拍与实际core拍分别保留。所有core行按posedge PRE_NBA记录；F与真实req握手A分开。23项尚未公开的语义保null及原因；ID=0可有效；metadata错误不丢TX。

自审发现并在执行前修正两处：① ModelSim的`# MONITOR_END`前缀和额外畸形标记需兼容/计数，软件已先计全部标记再验证唯一行；② 独立driver下降沿直接置finish可能与core采样竞争，TB及生成器已改为随后core下降沿置位，下一core上升沿采样。未执行前的源码修正，不消费定向增量组。

执行器静态自审再补两处：CLI超时先有界终止、保存原双流和timeout收据再判失败；父组PASS必须总耗时≤90秒，包含执行后身份复核与收尾。均在首组前修正，未消费功能组或增量。

原始行epoch不预填；独立reset快照时间0取实际初值，后续按实际本地reset进入计数。同ps有多个可行epoch时保null；不由FRAME或已采样行反造边沿。真实工具退出、timeout、cleanup仍需M2外部收据；END中的ledger/tail为未核，不冒充真实finish通过。

首组计划：36个新表示层夹具（7正29负）及2个CLI进程检查，仅Python标准库。进程内拒绝码与真正exit0/2分开记录。旧R06组不重跑，HDL/EDA/设备新增轮次0；外部父Job约束子树，85秒工作截止与5秒清理余量，总预算90秒。所有源码/夹具/依赖与工具身份先冻结再启动。输出只签软件夹具；真实采集/M1语义及M2准入仍PENDING。
