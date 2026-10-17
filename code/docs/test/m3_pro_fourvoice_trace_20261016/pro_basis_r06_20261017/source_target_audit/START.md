# M3-R6-1 唯一软件组计划

基线42d28c4ad8250b9064099da4742fbde12a254444。机器LAPTOP-KSS1MRR7；解释器C:/Users/songdongkuan/miniconda3/python.exe；无板卡/HDL/EDA操作。

本包源码/配置在对应software/source_target_audit目录。只读来源为已发布M2静态ZIP（931b7d2b…c1ba2），MANIFEST独立pin 8591e407…c265。实际M1/M2 R06候选目录本次查找尚不存在，配置candidates为空，不虚构其到件；CLI支持新增带SHA候选与显式replaces，旧原件不覆盖。

执行一次run_once.py，总预算90秒，子进程最多85秒扣除前置耗时；独占RUN_01目录拒覆盖。启动子进程前生成PLAN.json：实际源码/配置/ZIP/Python及已加载标准库和Python DLL SHA、机器/UTC/命令/cwd；frozen保存原源码。新合成fixture由冻结test_audit.py生成，CASE_PLAN记录生成原件SHA后才调用审计器。15个新软件用例，另对真实原包做三种只读装配分析（原列表、加wrapper、物理模式）；不调用旧来源checker六例。

用例：正常装配、physical缺身份、wrapper缺席、缺模块、重复模块、输入/输出路径逃逸、候选SHA漂移、覆盖原件、显式替代、错命名端口、缺include、缺ROM、预处理未展开保持PENDING、注释伪模块。输出RESULT/源表/模块端口/依赖manifest；原ROM路径与字节保留。软件用例PASS不代表真实原列表完整，更不代表Pro可执行或物理通过。

首失败保留RUN_01 frozen/双流/收据。仅新实现缺陷允许一次≤60秒定向修复组；不自动重试。最终不Git写，交总控统一处理。
