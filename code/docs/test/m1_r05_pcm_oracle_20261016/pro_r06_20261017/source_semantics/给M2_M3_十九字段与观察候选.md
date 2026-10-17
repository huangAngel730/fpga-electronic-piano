# M1→M2/M3：R07 十九字段与M1观察候选

**待用户转发，尚未送达。**

已按第19批R07优先完成M1-R6-1自身实现：十九字段逐项真实来源/位宽/采样沿/更新条件、四份显式观察候选、source-list替换和可逆diff齐套。M2发布的61字段表已取得，十九项宽度与符号匹配；实际四份M1原源SHA与M2来源表中的router/bank/chain同源，audio使用同冻结R06输入。具体映射见`M2_FIELD_CORRESPONDENCE_R07.json`。

本批只在`code/rtl/audio/m1_pro_observer_r06_20261017/`及模型/证据的`pro_r06_20261017/`内新增。十九个新软件自检和实际候选连线检查exit0；候选去除标记块后逐字恢复旧源，源前后SHA未变。第一次准备因长路径失败，测试未启动；原失败保留，修复组约0.844秒。**候选仅L0，没有运行HDL编译/仿真，不能称行为等价或Pro通过。**

M2接续需完成：

1. 以本批四候选一换一替换同名router/bank/audio/chain源，保留其他算法/ROM；在M2的frame_core→board→Pro观察层显式连接十九项。M1不改这些M2文件。
2. 采用明确应用分阶段合同：`apply_kind/mask/seq/seq_valid`不可丢。输入accept后的分配、NoteOn消费、控制接受、释放应用、NoteOff消费、退休是不同边界；延迟释放与自主退休没有可信输入因果时不填伪seq。seq在router入口接受时从0递增，按reset epoch解读；同epoch回绕不保证唯一。这是router接受序号，不是MIDI字节seq；现有输入没有外部seq端口，M3须将独立输入计划与实际接受记录显式关联，不能声称外部seq已字节级直通。
3. 确认62位config观察拼接、真实take、FRAME F与bank请求ID的关系，并保留最终输出、上游和feedback clip的区别。M1的`obs_advance_frame_id`是请求tag，M2字段名为`advance_frame_req_id`，并非擅自定义FRAME序号。
4. 更新完整source-list、公开采样合同与M3采集接口后，按受控工具/真实双流/精确预算另签首次数字执行。旧R05/P7/既有额度不恢复。

M3接续：R7-C包装桥保持全部原始字段和seq_valid原因，不硬套旧B0或C toy。R6-5提供独立应用、共同mask1111推进和效果接受日历；R7-A只采公开口。当前所见远端尚无R7-C已发布文件，本批没有另造机械包装桥。M1-R6-2真实数学、R6-3同版板采仍待输入；已给下一输入合同和测量判据，未消费R6-2软件组。

正式Pro基础仍PARTIAL，`board_release_allowed=false`。本批实际Git提交/推送与门禁状态以最终交付回执为准，不用M2旧9/9代签新树。
