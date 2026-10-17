# 夜间2：旧C9通知与最新R10阶段1/2只读核缺

结论：旧通知要求的同版接线、字段信息保留及离线软件差额已经有实物文件和限定软件证据；目前未发现需要重新实现采集器/74字段桥的具体缺口。尚未完成的是精确C9真实执行准入、finish相位、同capture原始采样、独立plan因果映射、audio_stable、真实公开等价与M1数学。整体仍PARTIAL，不能把旧通知的L0状态当作没有后继软件成果，也不能把软件成果升级为C9编译/数字/板测通过。

范围：按总控指定的旧16ac2265通知、已发布D4、R10源26cb6fed及收据82a9e826核对。完整R10源SHA为26cb6fed2cfa2302a2776cbe010d2e105d428bb1；D4源af25fa5e14d9c3a288e7d8a6a6d05f2f9cf75f95、证据358c16c2a927e3684c075dfc5ede70a6a67e036a。82a9e826及HEAD=origin/develop来自总控本轮观察，本窗口没有新fetch或独立网络核验，不猜补收据完整SHA。原START仍2026-10-17 21:52、截止2026-10-18 02:52，不新建Goal。

全部44个证据的**完整路径、实际字节数与本轮计算SHA256**在同目录EVIDENCE.json；下表使用其中证据ID，避免长路径混淆。报告只读源码/JSON/现有回执并哈希，未导入/编译/AST/执行候选，未启动测试/HDL/EDA/设备，未改源码或Git。辅助子智能体只读核查本次语义保留链，不启审核员。

| 核对项 | 已形成的证据与实际边界 | 尚缺及下一责任 |
| --- | --- | --- |
| C9同版72单元/9ROM/2头 | actual_application列72基单元＋driver/observer/TB＝75，9ROM、2头、2同字节别名；86个decision载荷＝84 inputs＋2 provenance，原MANIFEST保留；C9_closure/decision/exports/schema及应用ZIP均有身份。R10实际申请已组装，非仅空表 | 没有对应HDL编译/展开/采样通过。工具动态/延迟依赖、参数readmem和可信执行器仍待M2 |
| 67口/74字段 | C9_exports/row_schema/port_map、observer、stream/codec/intake/companions完整接续；61＋TX仅派生投影，新增字段/raw/events/semantics在sidecar保留 | 缺实际C9全窗原件；不能用投影或合成格式检查签真实通过 |
| kind/mask/router seq及valid | observer202–210、stream205–255保留原口和74字段；不把router seq当独立apply_event_seq | 独立前门计划→接受→应用关联仍M1确认；无可信关联时apply_event_seq保持null/PENDING |
| kind哨兵/同seq多阶段 | apply_valid时kind3/4/8若三项已知，则检查seq_valid/data/seq＝0/0/0，标INVALID_CAUSE；X/Z/null不补0。kind1/2同seq各阶段按行保留，stage_deduplicated=false | 实际运行是否满足哨兵/阶段行为仍待同源capture，不由本次静态阅读代签 |
| config_take与三clip | observer及stream记录实际config_take、62位payload及upstream/effect/feedback三独立clip mask；仅实际take时拆配置，不用config_valid或总体clip替代 | 尚无真实FX接受历史与独立数学期望；归M1数学/同版capture |
| tag/lane_tick/FRAME | lane_bank156/159由真实lane_tick形成advance_mask、tag来自pending_req_id；stream明确advance_frame_req_id_is_FRAME_F=false；frame_tick、A和请求tag分别保存 | 源连接正确不等于已观察真实推进。独立FRAME必须来自唯一frame_generator，不得从tag、A或固定延迟反推F |
| 阶段1安全与旧缺陷 | D4限定75旧未跑＋39新增＝114匹配；R10申请guard仍NOT_GRANTED，claim仅申请输出占用；startup/null、合法ID0、HOLD、cancel、F/A及串行接缝有软件边界证据 | D4逐例使用各自冻结版本，非完整最终版重跑。真实进程清理/HDL执行及整窗行为未验，不能恢复旧消费 |
| 阶段2driver/唯一公开TB | 复用原R62四输入及唯一公开observer/TB，采用真实公开ready观察，不force内部ready；来源SHA进入R10_handoff | ready.drv的event_ready输出未接DUT，仅诊断；不证明DUT背压注入。真实外部MIDI到达/异步reset原边沿/采样双流均NOT_RUN，是否改测法或TB后继由M2决定 |
| finish/唯一FRAME | R10_window明确PROPOSED_NOT_M2_FROZEN，首core12500ps/周期25000ps及release802/1002482只是源码推导；STOP1130660处finish可能D或D＋1，argv选1130661仅待批 | M2冻结具体相位或批准精确TB后继。unique_FRAME_PLAN_ref为PENDING，唯一生成器没有在R10调用；不能把FRAME_INPUT_DRAFT或源码冻结清单当已批窗口 |
| 真实公开等价/数学 | D4的大伴随流转换、>65MiB原文件流式74字段CSV、X/null长cell已有限定软件结果；R10_source-bound preparation及14字段交接已形成 | R7-B实际同输入双候选公开输出等价仍未跑；M1_NEXT_INPUT要求完整应用/推进/FX历史，机械wrapper已存在但本次实际bundle为NOT_RUN。不能把实测PCM当黄金 |
| NoteOn旧勘误 | NoteOn_binding已ACCEPTED_L0；原定义与仅改/fields/4/definition的后继并引。E分配，H首次后续CTRL_ON&&cmd_ready，C=H＋1且最早E＋2，背压可继续延迟 | 此文字项已关闭，不再索要勘误，不用固定延迟造实际期望；行为级证明仍随真实capture/数学 |
| audio_stable/复核 | C9_port_map与NoteOn_binding明确audio_stable待M2实现/策略，规范化保持null；R10_receipt为源发布而非M2验收 | 已读交接未见M2 RECEIVED/ACCEPTED/最终限定复核；发布、AI收件、真人通知与实机通过分别记录 |

执行额度以现有台账为准：D4初组1/1、定向修复3/3均已消费；R10 N10-M3-LINK初组1/1已消费，7/7匹配、退出0、9.391秒，旧114未重跑。R10唯一尚未消费的是**首个具体新LINK缺陷**的一次≤60秒增量；当前7例全匹配，本次静态核缺没有定位新LINK实现缺陷，所以这不是可随意再跑一组、补真实材料或调用FRAME生成器的额度。旧R08/R09/drill及其他岗位额度不恢复，本窗口不替M1/M2认领任何余额。

当前可做：本轮授权目录内只读核缺、既有SHA/封包/回执关联、准备精确owner待决清单；总控可按既有唯一发布者规则处理本报告。不能在本轮报告写集实施代码修复，不能重复已签测试。若以后确有新LINK缺陷，先留首失败与依据，再由总控在原写集和剩余条件额度内定向处理。M2未给相位/执行准入前，不动HDL/EDA/设备；M1未给独立映射/支持profile前，不造数学黄金或补seq/audio_stable。

额外入口边界：当前R10_chain只支持PREPARE_APPLICATION_ONLY；旧old_chain具有PROCESS_CAPTURE路线但其原绑定指向D4输出域。以后接真实capture时还需在明确授权和冻结输入下选择R10 adapter对应的兼容模块绑定及F/window/source输入，再使用唯一生成器和现有消费者。该准备入口的有意限制不是本次软件测试失败，不能据此消费条件修复额度，也不能声称R10实际整链已经跑过。

优先交M2一次决定：① STOP/finish D或D＋1及是否需要TB后继；② 精确源/TB/工具/依赖/argv/cwd/env/输出/预算及可信执行器、参数readmem与真实HDL新准入；③ audio_stable及DUT背压测试边界；④ 对现有完整软件包限定复核/签收。随后M3按有效许可取得同capture原RAW/pins/reset/end/stdout/stderr，M1提供独立plan关联和PCM24/ID/clip黄金。未验项仍PARTIAL、board_release_allowed=false。

旧通知的生产者D盘总ZIP本轮未读取，不冒称已核；当前结论依赖仓库可取得的C9本体、D4封存回执和R10两份交付ZIP。旧通知“R08最新36项”“NoteOn待勘误”不能覆盖最新R10任务顺序及已经关闭的文字项。
