# 一次最小修复计划（≤60秒）

RUN_01退出0，15例通过；但自审真实原包清单发现审计器误报，不能宣称该首轮完整无缺陷。首源码/原输出完整保留RUN_01/frozen及cases。

具体缺陷与依据：

- 位宽去除时用空串，使signed[11:0]bend成为signedbend，真实pitch_mod端口被误判未知；改为空格。
- sustain_controller使用宏端口，未展开却被当完整端口表拒收；改标记port_inventory_complete=false，保留PENDING，绝不把宏端口视为验证通过。
- function automatic performance_event_t encode(...)被当模块实例；实例扫描排除function/task声明段、字符串与generate标签。
- ROM参数默认路径可能被上层覆盖，不是已生效的literal readmem依赖；默认缺路径保留PENDING，直接literal readmem缺件仍拒收。

新test_repair.py七个定向软件用例及一次真实原包解析增量，不重跑原15组或旧checker六例。新源码、配置、工具依赖在RUN_02启动前冻结；使用run_once.py的--repair，总60秒、子进程55秒扣前置。没有第三轮预算，失败立即交具体原件。
