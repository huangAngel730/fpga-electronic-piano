# 主M2系统控制流水组合隔离试验 2026-10-05

用户最新授权统一pipeline边界，一次同时处理parser/RR与音频身份→ADSR两瓶颈。复用此前功能已验的cache3parser和identitylease/VERIFY音频方案；前两次单独物理候选仍不采用，本次是新组合试验，不改历史。不是新公共接口，不含最近T027/panel/T028正式功能，不可拿此版Fmax当全功能余量。

代码仅本test目录。来源manifest冻结，正常音频多1clk、heldbackpressure延后内部retire/activecount明确。任何寄存边界必须同时保持标签/FCW/数据/valid；sameframe取消优先、数据不回滚等沿原合同。主M2真实UART→32FIFO→银行/allocator/CC64/FCW/DDS/ADSR→PCMjointTB必须通过，再一次同V0171有效约束物理，仅3source变，限30min。

已有两子模块真实仿真证据按source/logSHA复用，另实跑新增joint路径，不重复开发；旧独立行为变异真实拒收证据保留。错误标签/FCW旁路/身份lease故障joint检验，source没有force内部状态。最终不得自动应用生产、群接口要求及跨岗通知仍适用于正式落地。整机门槛+.5、目标+1，Hold/Recovery/Removal和cost明确，失败保原版，不挑seed。
