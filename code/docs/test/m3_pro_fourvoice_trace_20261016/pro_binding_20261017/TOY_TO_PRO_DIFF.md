# 旧夹具到真实Pro的逐字段差额

以下是本机现有源码的静态差异L0，源字节与只读快照在INPUT_IDENTITIES.json。没有新Pro源/ROM/trace的同版签收，不称实际Pro采用了旧实现。旧R06 ZIP中的m1td源仅作历史定位，不解封运行；其身份与来源由夜间5另核。

| 旧事实/假设 | 现有源定位与真实差额 | 新Pro所需材料/责任 |
| --- | --- | --- |
| C input+1接受、下一frame应用 | code/rtl/board/polyphonic_event_router.sv:57的ready由state/sample_owner_ready/release/retire控制；137起ALLOC_APPLY等阶段才更新。 | M2给新源event输入与应用公开出口；M3从独立输入计划推导，不移植toy拍号。 |
| C最低空闲/立即NoteOff释放 | 同router:164置releasing、170退休清occupied；polyphonic_envelope_bank.sv:89按ADSR IDLE生成done。 | 真实allocator/Release/retire规则与generation出口；M1包络数学只读，不能以NoteOff当done。 |
| C source/channel为0、lane=slot | router:29–33 source/channel/generation是私有量；公开active_count不能区分身份。 | M2确认只读公开slot身份与generation，不能取私有wave/env/phase作黄金。 |
| C四lane不同offer/req_id | 现有envelope_bank的共同lane_tick接四个g_lane的DDS/ADSR；sample_req仅导致一次共同推进。 | 用真实advance_mask与帧级advance_req_id。旧上午scalar lane monitor不能直接表达同沿mask1111；M2固定映射后才适配，不造四笔虚拟交易。 |
| C独立lane请求vs上午帧级ID | 上午pro_frame_monitor.sv:11–13、124–128以一帧请求收四个不同scalar lane，且req_payload64不透明。 | 明确帧ID、lane标识、voice slot与generation域，不能直接复用C身份键。 |
| 每frame自动接受 | m2_fourvoice_timbre_delay_frame_core.sv:24–31中valid/ready是内部，公开request_accept；52–61绑定frame adapter，frame有取消优先。 | 原req_valid/ready/id、frame_tick/cancel须完整公开；credit/计数不替代实际接受。 |
| 返回/提交视作同一事实 | 同core:25–28 result元组内部；57–61左右clip OR交运输，外部仅commit和play。 | first-valid/握手/保持/commit四事实，左右clip及归并源证明；M1继续核PCM数学。 |
| effect配置即effect输入 | 同core:9–13、38–41公开config握手；效果音频输入valid/ready及ID未在该壳完整公开。 | config与effect-input分栏；M2出口与M1配置/效果口径，不能相互替代。 |
| C/D按消费帧序映射 | D3 delta_audit.py:validate_link保留各自时轴，只是诊断身份连接，不是共同因果日历。 | 同源输入/trace和共同cycle/epoch，拒用旧映射证明新Pro延迟。 |
| commit推成播放sample | 上午29列CSV没有TX实际帧采纳ID/PCM/clip，也没finish列；人工串行0。 | 独立TX采纳sidecar与完整finish/END/MONITOR_END原日志，B2只读消费；绝不以commit反填sample、人工0做串行正例。 |
| 40MHz/833为软件事实 | C时轴是fixture假设，D监视器只核采样域比例；electronic_piano_top.sv文件头仍为60K/PG484旧工程。 | 新Pro完整source/ROM/top/时钟复位身份由M2到件；物理时钟/STA/电气不能由软件比例签。 |

当前准确阻断：新Pro同版原件缺失；现有壳未完整公开slot身份、实际advance、result背压和effect音频输入；B2缺TX实际采纳与真实pins/M1同源黄金。任务内可做的观察合同与拒收入口继续完成；真实日历、RTL/ModelSim/Gowin、物理和板测均NOT_RUN。没有恢复旧预算或扩大正式接口写集。
