# 静态元数据读取历史

2026-10-17 19:40 北京时间，首次临时 ZIP 元数据脚本 exit1：查找 */dds_oscillator.sv 返回空列表，取首项产生 IndexError。71单元、73字面module、leaf SHA等前置断言已执行，但脚本未完成，未产生绑定结果。工具原始输出为 `DDS_ORIGINAL_MEMBERS []`，`IndexError: list index out of range`，没有 HDL、编译或 B 功能测试。

随后只读成员清单确认真实成员为 `provenance/ORIGINAL_dds_oscillator.sv`。修正静态脚本使用该精确成员，结果见 STATIC_BINDING.json。此元数据读取不恢复/消费B功能测试额度，不修改B旧原件。
