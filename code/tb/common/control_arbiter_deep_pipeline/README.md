# 独立深流水仲裁原型

本模块不是midi_event_parser替换件、不自动改pending/FIFO/同拍调度。request_mask和rr冻结，E+1组内8slot top2，E+2四组合并top2，id/epoch全保留；minII4，heldready稳定，cancel/reset清。真实18592快照/151154检查/三编译行为反例及empty/shortcount通过。genericYosys205bits/无latch，不称Gowin映射或STA。

run_control_snapshot_selector.py --output code/output/<新目录> 自检，不启动厂商工具。正式接入前需明确freshness、不可无限epochretry、不得撤回已呈现FIFO头、burst1/8/16有界控制机会和presentationbuffercapacity门禁。当前只原型与合同审查，没有parser整链/整机/PnR/上板。

另有STA局部拥塞100%热点和高扇出证据，见更深流水仲裁原型与局部布线审查_2026-10-05.md；不能从globalarea未满推导routing不拥塞。主M2不重复M3DVI试布线任务或更改IP/约束。
