# M1-R6-1：十九字段语义与显式出口候选

已完成M1侧十九项源语义、四份隔离候选、逐级公开出口和可逆差异。19个新软件自检通过，实际候选的十九项静态连线检查通过；删除每份候选新增的`M1_OBSERVER_R06`标记块后，逐字恢复冻结原源。**这只是L0候选/软件静态检查，不是HDL编译、仿真、形式等价或Pro实际采集通过。**

入口：

- `字段语义_R06.json`：每字段位宽、符号、pre-NBA采样、更新规则、源SHA/行及公开连接路径。
- `router_semantics.md`、`dsp_semantics.md`：应用/释放/退休/世代及共同推进/效果/配置的实际语义。
- `M2_FIELD_CORRESPONDENCE_R07.json`：M2已发布字段名到M1候选端口的19项对应；位宽/符号一致。其后补收的M2输入本体在`M2_INPUT_R07/`。软件组形成时M2大包尚未取得，原合同的历史待到件状态保留，当前**M2字段表已取得、外层集成仍待办**。
- `SOURCE_REPLACEMENTS.json`、`CANDIDATE_DIFF.patch`：四份同名模块一换一，禁止新旧同名模块同时进入source-list。
- `SOFTWARE_GROUP_R02/RECEIPT.json`及两组原始stdout/stderr：19方法/实际合同检查均exit0，合计约0.844秒，源前后未变。`R01`在生成快照时因Windows长路径失败，尚未启动测试；仅修复快照文件名后，使用任务单的一次≤60秒修复组，不隐去首失败。

本次候选只增加观察口和与功能无反馈的事件序号记录。NoteOff不等退休；occupied包含Release；generation按成功分配/重触发/抢占递增。真实`lane_tick`使四lane同沿推进，`advance_mask`是0000或1111，不按occupied筛选；`advance_frame_id`为bank保存的请求ID，仍需M2关联FRAME F。

`apply_valid/data`须和新增的`apply_kind/mask/seq/seq_valid`共同使用：一个输入可以对应多阶段应用，自主退休与未存因果的延迟释放没有可证明的原始输入序号，此时seq_valid=0、data=0仅为无效占位，不能解码为真实全零事件。M2需确认此扩展再让M3采集器保留，不可把多阶段压成一条accept+固定拍。

效果观察为真实输入valid/ready/ID/左右signed24/双clip，bit0左、bit1右；最终输出clip、反馈内部clip与上游clip分开。配置62位拼接及take是观察提案，不改原控制接口；M2负责最终打包、frame_core→board→Pro观察口接入和执行准入。

本轮没有改M2/M3目录、正式top、约束、ROM、原算法或旧封存；没有执行旧黄金、HDL、EDA、设备。`oracle_adapter/NEXT_INPUT_CONTRACT.md`和`bench_math/MEASUREMENT_CRITERIA.md`位于上一层的对应目录；这两项的真实输入仍缺，不虚构PCM、板采或软件轮次。`board_release_allowed=false`。
