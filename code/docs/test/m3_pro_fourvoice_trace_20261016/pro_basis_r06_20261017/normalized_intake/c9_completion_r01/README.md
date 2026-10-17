# task-day4 C9 intake projection

状态 L0 / SOURCE_READY / NOT_RUN。project_intake_files(public_rows_path,output_dir)产出artifacts.ledger/legacy_rows/c9_sidecar/preserved_rows。

完整C9 canonical原件保留并绑定SHA；明确派生旧61字段+真实raw口构造的旧TX extensions，新增13字段/raw ports/原因/semantics独立sidecar不丢。禁止把非空无证apply_event_seq投影为已证计划。原始74字段/同seq阶段不去重。

复用冻结r07_fix.analyze算法；唯一AST派生是preserved_rows=[]初始化替换为追加式JSONL保存器，所有验证、事务和F/A/held算法不改。返回旧ledger schema供唯一R6-5 calendar消费；preserved_rows字段为空占位，实际全部行在preserved_rows_ref，明确external storage。原数据和源码均不改。

逐行保存不再驻留完整原行，但原算法仍保留frame/transaction/TX元数据并扫描历史frame，不能声称全算法常量内存或线性时间。新容量限制一百万个事件观察，超限LEGACY_LEDGER_EVENT_CAPACITY拒收。日历仍只调用原唯一FRAME_PLAN生成器。两个新例待总控执行；真实plan/同版trace/数学/可信准入保持PENDING。
