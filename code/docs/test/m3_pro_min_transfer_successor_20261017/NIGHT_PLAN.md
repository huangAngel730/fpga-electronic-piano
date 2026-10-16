# M3 E3：10月17日第二夜间任务

岗位M3，整个E3最小传谱包；当前基线ad2de2169230dc8fd9f4b6f8157d384306c2479a。用户第二任务单SHA b8e6372b7cd9261f276247754a8f2f9bc8841c31344edc3116a78827d964ed0e，总控派单task2_coordinator/NIGHT_PLAN_20261017_TASK2.md。基础Pro与正式验收顺序保持；本包只做新增真实文件→实际RTL UART→公开RAM/完整串行READ隔离证据。

| 条件 | 本夜执行 |
| --- | --- |
| 写集 | 四处score_transfer_candidate、tb/input/score_transfer_candidate、software/score_transfer_trace_candidate_20261015、docs/test下m3_pro_min_transfer_successor_20261017新子目录。原件只读。 |
| 可用输入 | 本地真实MIDI_sample_2018-03-21.mid，300B，SHA c0a8cb9f1ba3496a00367786a2b4ee5e0580be7b4bfbf0891b75e3b7475f634c；沿SOURCE_RIGHTS.txt的CC0来源说明。只用这一份，不生成替代真实MIDI。 |
| 工具/额度 | 现有Python3.12.4和Icarus现场预检；新实现—定向验证最多6轮，Python每组90秒、模块编译/仿真每组600秒，子智能体共享。输出/源码冻结后启动即计消费；原双流/退出码/首失败齐备。无Gowin/下载/设备。 |
| 时间盒 | 本夜05:21北京时间硬截止，本包20:51UTC/04:51前收口留总控30分钟。成功即停，不凑次数。 |
| 独立判据 | 原严格导入器与T057 encoder只读；原MIDI独立oracle、逐记录RAM公开读口和完整UART READ核同；新增重放ACK、丢DATA、CRC错和帧/会话超时数字负例，异常后旧发布保持。 |
| 验证等级 | 目标限定L2隔离UART/协议/RAM与L1源文件数学核对；没有实体串口、手机有线、安全Bank/CST/精确Pro码流，整体E3仍PARTIAL，board_release_allowed=false。 |
| 停工 | 原件/工具身份不符先停；具体软件或TB缺陷可在剩余轮修，首失败不覆盖。需改正式接口/原RTL/任务外目录则交总控，不越界。 |

已知冻结合同差异：不完整COMMIT/NACK8后会话失效的书面约定与旧RTL不一致，保留未决，不藉新增正例消除该边界。本次不重跑旧T057全量685场景/旧软件自测，不开发BLE、编辑器、多设备、自动播放或PCM。

总控后续明确要求：新单授权整个E3后继，可在新RTL目录最小修复NACK8，不改旧文件或公共协议。PROTOCOL.md第26行明确失败COMMIT失效会话，无已知相反合同；后继统一修v1执行层4/5/6/8分支，保留版本/帧CRC及已签VERIFY9/10策略。定向补不完整COMMIT→NACK8/active0→旧cached DATA和新DATA均拒收、旧RAM不变及fresh BEGIN恢复；正常真实文件链在新模块重验属于修复影响范围。原先未决文字仅作开工事实，最终以新轮原件结论为准。

完成后自审与只读子智能体复查增量，封一页收据、所有来源/源码/工具/原日志与失败原件，由总控串行发布并交M2；子窗口不做Git/index/门禁/编号/共享状态。用户已授权本夜四窗口直接回传，真人交接仍待用户转发。
