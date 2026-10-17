# M1 R07十九字段：限定复核与待确认勘误

M2已收到用户转交的本批原件并完成限定静态核对；原包不改写。四份候选可逆为冻结原源，十九项位宽/符号和真实来源已核。原19项软件记录与12输入/12快照/两对双流同SHA，M2未重跑。

需要M1确认并以新文件/新版本更正：`source_semantics/字段语义_R06.json:338` 的 note_on_mask.definition 写 `Allocation commit happened on the preceding edge`。实际 router 的 ALLOC_APPLY 在E沿写槽并进入CTRL_ON；最早E+1沿CTRL_ON与cmd_ready握手后NBA置slot_note_on，bank在E+2沿消费，背压可更晚。定义应为“先前完成ALLOC_COMMIT；实际间隔由CTRL_ON的cmd_ready握手决定，不承诺固定一拍”。候选RTL据真实脉冲导出，不需要据此改功能。保持原合同/原软件结果身份，勿覆盖首件或复跑已签19项。

这处时序文字不在原静态alias/端口检查的证明范围内；M2不将原19软件PASS签成周期行为通过。M2 C9据真实输出接线，并显式保留REWORK_REQUIRED；不生成固定accept+1或allocation+1的期望。

原apply_event_seq按M2合同指独立input-plan序号，M1 obs_apply_seq是内部router接受序号，两者不能直接别名。C9新增router_apply_seq/valid并保留独立计划映射PENDING。kind3/4/8无原事件因果，data/seq零为无效哨兵；kind1/2可共享序号，不按seq去重。此为M2诊断候选合同决定，非更改M1算法或事件输入接口。

待M1确认；待用户转发，尚未送达。总体PARTIAL，board_release_allowed=false。
