# B1到件合同与B2接入差额

只读消费B1最终OBSERVATION_CONTRACT.json，schema M3_B1_MINIMAL_OBSERVATION_CONTRACT_V1，61字段/11760字节，SHA d89076836f8c60dd6544bbf2d9a5e8fa2f645ef49c8860458210562adf12d716；FINAL_ENTRY及RECEIPT同属DONE_LIMITED_PREPARATION__PENDING_PRO_SOURCE_OR_TRACE。原件位置及现场SHA见SOURCE_LINK.json；遵照总控最新收尾要求，只引用上游原件，不将旧源码、已签案例或旧包重新装入本包。未运行B1程序或重新审其来源门禁。

| B1候选组 | 本B2原CSV/测试视图 | 真接入状态 |
| --- | --- | --- |
| cycle/epoch/rst_n/frame_tick；POSEDGE_PRE_NBA | 原29列同名时基，frame_tick逐沿，不按toy重计周期 | M2映射/时钟/复位未到；软件候选相位一致不证明源已采用。 |
| FRAME_REQUEST ID；advance mask可同沿四路 | 仅帧请求ID，0合法；不把slot、lane_req_id当帧ID | 不新增scalar-lane推造，真正B1帧账本待件。 |
| commit_left/right/commit_clip | CSV commit_left/right/commit_clipped；与独立oracle对照 | result_clip_mask2→commit_clip1的归并需M2/M1冻结，不自行OR或丢位。 |
| tx_sample_valid/frame_id/req_id/L/R/clip/hold/startup_zero | 独立每frame已选TX快照；identity_valid与sample_valid不自动同义 | 真HOLD/启动语义归一化未实现/未验，必须M2公开采纳点，不能从commit/pending/DUT play或黄金反填。 |
| bclk/ws/din | 原逐沿pins传给PinDecoder | 原上午自检为零，已作为新入口拒收；无真Pro串行正例。 |
| finish、END、唯一MONITOR_END及成功完整收据 | 当前CSV无finish列，只保声明末拍和尾部UNKNOWN | 真实闭合和收据先由B1绑定，当前未连通，不能签完整捕获。 |

B1负责原件路径/来源结构门禁；其metadata成功本身也不核HDL出口、签名或真实逐沿日历。B2不会将B1声明当已签真实源，也不提供另一套D3来源工具。适配器当下接的是明确测试视图，尚未声称61字段trace可直接调用。

下一责任：M2交精确Pro source/ROM/top及同版公开映射/采样与结束原件；B1固定独立输入/真实帧请求账本和源绑定；M1交同源PCM/clip只读黄金；M3 B2在后续有效预算下将真实HOLD/启动/finish映射到本桥，再检查逐沿pins。缺上述材料保持PENDING_PRO_SOURCE_OR_TRACE。正式接口变更仅由M2按规则处理。
