# 七组CDC与64/98bit路径：静态端点映射

所有旧路径来自INPUT_ORIGINALS/old_sdc.sdc，实际源路径/全SHA见INPUT_IDENTITIES.json。新路径中的`<E1>`是**待M2确定的实例前缀占位**，不是已存在的Pro层级。RTL寄存器名与旧网表`_s0`优化名有意分开。此表不是可执行SDC，不报告Active/matched数量或STA通过。

| 组 | 域方向 | 旧SDC首级（行） | D候选RTL首级→二级 | 源码锚 |
| --- | --- | --- | --- | --- |
| event ack | pixel25→sys40 | u_visual/u_event_bridge/ack_meta_s0/D（300） | <E1>/u_events/ack_meta→ack_sync | event_bridge:30/54–61 |
| event request | sys40→pixel25 | u_visual/u_event_bridge/req_meta_s0/D（301） | <E1>/u_events/req_meta→req_sync | event_bridge:31/94–105 |
| event desync | sys40→pixel25 | u_visual/u_event_bridge/desync_meta_s0/D（302） | <E1>/u_events/desync_meta→video_desync | event_bridge:34/102–105 |
| score ack | pixel25→sys40 | u_visual/u_control/u_score_mailbox/ack_meta_s0/D（303） | <E1>/u_control/u_score_mailbox/ack_meta→ack_sync | mailbox:21/27–34；control_bridge:42 |
| score request | sys40→pixel25 | u_visual/u_control/u_score_mailbox/req_meta_s0/D（304） | <E1>/u_control/u_score_mailbox/req_meta→req_sync | mailbox:22/45–52；control_bridge:42 |
| mode ack | pixel25→sys40 | u_visual/u_control/u_mode_mailbox/ack_meta_s0/D（305） | <E1>/u_control/u_mode_mailbox/ack_meta→ack_sync | mailbox:21/27–34；control_bridge:49 |
| mode request | sys40→pixel25 | u_visual/u_control/u_mode_mailbox/req_meta_s0/D（306） | <E1>/u_control/u_mode_mailbox/req_meta→req_sync | mailbox:22/45–52；control_bridge:49 |

D:60实例u_events，D:68实例u_control；source异步首级均有async_reg=true。同步器首级例外不意味着二级免分析。旧SDC:314–327各组列级间setup与hold报告，但只属于旧对象；新Pro首级/二级对象数、属性是否保留、扇出及路径都UNKNOWN。各reset_sync链、PLL lock与serial reset以及全音画路径还须单独分析，不能把七组表等同完整CDC或完整STA。

| 载荷 | 结构/保持条件 | 旧物理文本 | 新Pro待核 |
| --- | --- | --- | --- |
| event64 | package:121–133 =3+4+4+7+10+10+8+12+6；event_bridge:26 payload_hold，:84–87从队列弹出后保持到目的接受+ACK，:122 video_data捕获 | SDC308 payload_hold*→video_data* max_delay10ns，312 setup报告 | <E1>/u_events/payload_hold→video_data，每位实际保留/优化、起止端/命中/最坏setup与hold、稳定时间；全部UNKNOWN |
| score98 | control_bridge:32 SCORE_WIDTH=34+2×32；:36–40按id16/note7/hit32/duration_valid1/duration32/velocity10打包；mailbox:19/40–43 hold，:66 dst_data捕获，目的背压保持 | SDC309 score_mailbox hold*→dst_data* max_delay10ns，313 setup报告 | <E1>/u_control/u_score_mailbox/...每有效位setup与hold及命中/优化原因；全部UNKNOWN |
| mode1 | control_bridge:49–56 src_data固定1，mode_data未参与功能；邮箱用于可靠valid/toggle | 旧SDC未单列mode payload max_delay；有req/ack级间报告 | 常量载荷可能消失，按实际网表说明；不能要求一条不存在的动态payload，也不能漏mode控制/复位 |

**不要误读旧hold证据**：SDC314–327含7组同步器二级hold，不是event64/score98 bundled-data hold。文本10.000ns也不是测得的余量，且旧_s0对象/旧u_event_bridge层级不能移作新Pro网表命中。M2需要同版真实Setup/Hold/Recovery/Removal及完整报告；本轮没有运行任何EDA，真实匹配数量/时序值保持UNKNOWN。
