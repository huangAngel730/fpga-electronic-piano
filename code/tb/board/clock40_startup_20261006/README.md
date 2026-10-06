# M2必要启动场景

使用已签收M3 L原始源码，新testbench不改生产top/CST/PLL/算法，不启动新PnR。场景0：外部复位初始即高、无需人工按键启动；场景1：外部复位103ns提前释放，不等PLL锁定；场景2：真实声部/踏板/MIDI半包/运算中，注入LOCK低并冻结core-clock，验证立即静音/复位、无时钟不能释放同步器，恢复后旧状态清除与新NoteOn/Off至少16PCM帧。

真实厂商gw5a PLL数字模型，DVI是边界stub；不验证PLL电气、模拟爆音、TMDS数据或显示器识别。注入force是明确测试故障，不称为硬件PLL失锁动力学。初始化后1ns起检查关键PA；启动即低的外部reset在第一个core-edge前可能没有仿真negedge事件，内部同步器不确定不冒称硬件安全证明；PA直接异步guard必须始终为1，核心开始后及已运行的失锁立即严格查reset。

重用Icarus适配为include-basename、路径重定向和allocator结构字段拆分，仅模拟副本，保留原位宽/NBA顺序；原M3源码不改。runner从已校验ZIP取原56inputs，用原GPRJ45Verilog顺序。

```powershell
python -B -X utf8 code/scripts/run_clock40_startup.py --output code/output/<new-dir> --scenario 0
python -B -X utf8 code/scripts/run_clock40_startup.py --output code/output/<new-dir> --scenario 1
python -B -X utf8 code/scripts/run_clock40_startup.py --output code/output/<new-dir> --scenario 2
```

无--scenario时按0/1/2及两个编译反例运行；--mutants-only只新增反例，不能冒称正例重跑。场景限900s、反例120s；2026-10-06 04:30绝对截止，到点终止自己的vvp，不执行无收益重试。04:30之后若要复跑必须另行更新合同。

反例：绕过LOCK复位安全条件、去掉直接PA静音guard。后者预期在没有核心边沿而同步器初始化状态不确定时被拒收；已初始化后仅~rst_sync_n也可能通过1ns失锁检查，不能伪称反例必须在停钟时失败。不以编译错误、超时或无关marker充当有效反例。

本目录只新增必要覆盖，不重跑既有189帧频率探针、40MHz样本捕获或32轮压力；M1独立ADSR数学和M3后续板型电气尚未替代。
