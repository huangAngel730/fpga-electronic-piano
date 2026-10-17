# R6-1 来源/目标装配审计器

本工具只读解析已冻结ZIP及显式候选清单，生成新的source-list、模块/端口词法清单、ROM/IP/约束依赖与输出载荷SHA。**不是Verilog elaborator，不运行任何编译器，不签物理或真实Pro功能。**

入口（仓库根，输出必须全新；执行需服从当前预算，不因命令可用恢复额度）：

```powershell
C:/Users/songdongkuan/miniconda3/python.exe -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/source_target_audit/audit.py --config code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/source_target_audit/real_config.json --root . --output <new-authorized-output>
```

退出0仅STATIC_CLOSURE_READY（词法清单条件），2拒收，3待绑定/展开。physical模式不输出物理PASS，即使元数据完整也需M2真实身份/IP审核；目标或Pro PLL未到时physical_status始终PENDING_PHYSICAL_ID。board_release_allowed/pro_dut_pass始终false。

配置：archive.path在root内，固定ZIP及MANIFEST双SHA；mode=simulation/physical；assembly=bound_list_only/bound_list_plus_wrapper。candidates数组各项必须给path、sha256、stage_as；可给replaces明确替换原source-list某项，保留原文件不覆盖。stage_as是独立相对路径，禁止已有文件、父目录、绝对路径、盘符、反斜杠或大小写别名。remove_sources只剔除明确列表项，不删除输入。M1/M2新候选到件后由M2选择冻结，不自动扫描最新文件冒充签收版本。

输出stage保存原source_closure所有字节及候选；source-list.f保持原列表顺序再加入wrapper/候选。**清单路径相对于RESULT.json.cwd指定的stage/source_closure/inputs，不是输出目录本身**；ROM相对路径因此保持原义。该清单是审计候选，不是执行许可。原compile.f不覆盖。

模块/端口支持ANSI及非ANSI词法列表、参数化模块和具名实例；位宽只保留表达式，不求值。宏端口port_inventory_complete=false，条件编译/generate生效分支、动态ROM参数/plusarg、参数默认覆盖均待真实受控工具确认。源表里未实例化模块的依赖也保守检查；因此MISSING_MODULE不自动证明顶层可达链编译失败。include仅核直接引用存在，宏展开/递归语义未执行。package只核名称，不验证类型。复杂多实例/escaped identifiers/interface等不在完整语义覆盖范围，不能用本工具取代编译或M2准入。

实际验证：RUN_01冻结版本15新增软件例通过；真实包自审发现解析误报后，以RUN_02冻结版本完成7个定向修复例及原包解析增量。**不是最终版22例全量重跑**，不重跑原来源checker六例。两组都仅Python/文件，实际命令及SHA见对应PLAN/RECEIPT。历史首轮错误输出不删除。

当前真实闭包结果：加wrapper后70编译单元、72模块词法条目、82实例、9ROM/4IP/2约束依赖。唯一剩余硬诊断dds_oscillator定义虽在原包，但未在原69项compile.f中；polyphonic_envelope_bank.sv:130引用。尚未判定顶层可达性，不擅自加入/删模块。M2需选择完整source-list，随后签真实工具准入。M1/M2 R06新候选本轮未到，完整Part/PLL仍缺。
