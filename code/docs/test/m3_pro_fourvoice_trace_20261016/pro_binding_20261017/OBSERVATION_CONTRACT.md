# B1 最小公开观察合同 V1（候选）

状态：PENDING_PRO_SOURCE_OR_TRACE。机器化合同为OBSERVATION_CONTRACT.json（SHA256 d89076836f8c60dd6544bbf2d9a5e8fa2f645ef49c8860458210562adf12d716），61个字段，包括B2同轴出口所需的最小补充。它定义隔离只读记录格式，不修改正式端口，不是假定新Pro已采用这些端口或位宽。M2须以同版源确认每个公开映射、位宽/packed顺序/同沿优先级；null宽度必须补齐，不由脚本猜测。

| 观察组 | 最小事实与归属 |
| --- | --- |
| 时基/复位 | 同一40MHz候选posedge、pre-NBA的cycle、rst_n、frame_tick；epoch仅从观察到的复位进入边界单调派生，初始必须有复位。不得用toy帧号推代际，也不据软件比例签物理晶振。 |
| 事件输入/真正应用 | 原event valid/ready/data64逐沿；接受是握手，应用另记valid、原事件seq/data，不假定input+1或下帧应用。source/channel/note/velocity从冻结输入计划与已签64位格式解码，不从最终DUT slot反推期待。 |
| 真实slot生命期 | occupied/releasing、note_on/off、retire四位mask，以及4槽source/channel/note/generation的公开packed身份。NoteOff进入Release，只有真实退休才释放；active_count不足以证明身份。 |
| 帧请求与声部推进 | 帧级req_valid/ready/id；advance_mask及所属帧req_id。允许一个真实共同tick以mask1111同沿推进四路；不能造四笔错开的lane请求。若真实结构是scalar lane，则M2明确公开onehot映射，保留原采样沿。voice slot、lane索引、帧请求ID不是同一域。 |
| 返回/运输提交 | 首次result_valid、ready、ID、signed24左右与左右clip mask；实际commit完整元组另记。首次valid就核归属，不等ready；握手及背压保持以完整payload判定。左右clip归并规则需源证明。 |
| 取消 | 同轴cancel及原因码；同沿取消/复位对请求、推进、返回、提交的优先级须冻结。取消不自动回滚已推进的DDS/ADSR。deadline到点不能靠reset/cancel隐藏。 |
| 配置与效果音频输入 | config valid/ready/完整payload与effect input valid/ready/ID/L/R/左右clip分开。config接受不是效果音频接受；M1继续拥有声音与效果数学。 |
| TX实际采纳sidecar | 每个真实frame_tick同cycle/epoch的TX帧ID、sample_valid、实际req_id（0合法）、signed24左右及clip、HOLD/启动零标记。来自TX公开采纳点，不能从commit、pending、M1黄金或DUT play字段反造采样事实。 |
| B2原pins及收尾 | 同轴bclk/ws/din原始逐沿，不由PCM再编码；PLL/audio_stable/高有效PA保留。真实finish、END和完整唯一MONITOR_END日志、捕获成功退出码与未超时收据都必须提供。 |

同一req_id可在不同reset epoch重用，单epoch不得重复；每次接受到提交/清理严格<833拍，并且必须在下一真实帧前完成。当前没有真实捕获，以上是待绑定判据，不是新增期限测试结果。取消后发布、重复发布、跨epoch、漏第四路的真实行为验证仍待同版输入与新执行许可；本轮仅测试对应观察字段/身份缺件的拒收，不把metadata反例说成RTL反例。

来源入口要求source_manifest、ROM manifest、独立input plan、public trace、独立TX sidecar、capture receipt、raw stdout/stderr、夜间5 intake报告和M2绑定复核十个原件；所有path/bytes/SHA与调用方独立提供的binding SHA核对。路径限指定artifact root内，拒绝绝对路径、父目录穿越、别名、布尔整数及重复JSON键；发布合同本体SHA被CLI固定，不允许换空合同漏检查。

软件check_observation_binding.py只核上述metadata声明与原件字节身份。它不解析HDL以验证出口、验证M2签名、检查MONITOR_END的真实内容、逐沿trace、四声日历或PCM。即使所有声明结构通过，输出仍为METADATA_STRUCTURE_READY_PROVENANCE_AND_CALENDAR_PENDING，authority_verified=false、real_trace_calendar_checked=false、pro_dut_pass=false。传入文件SHA不证明作者或板型；夜间5身份审计与M2最终复核仍独立必需。不存在把M2声明字符串当密码签名的逻辑。

实际调用：仓库根运行 `C:/Users/songdongkuan/miniconda3/python.exe -B -X utf8 code/software/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/check_observation_binding.py --binding <到件原件> --expected-binding-sha256 <独立冻结SHA> --artifact-root <原件根目录> --output <新结果.json>`。缺任何到件保持PENDING/exit2；结构/身份错误REJECTED/exit2；只有metadata准备成功exit0，绝不签真实Pro。无到件可省略binding参数，准确返回PENDING_PRO_SOURCE_OR_TRACE。不要覆盖旧输出或复跑旧C/D。

本轮不新增DUT或RTL monitor：旧scalar lane入口不支持旧真实四路共同tick；盲目实例化会改变观察含义。正式受控观察出口由M2决定，源到齐后再在新有效额度内接入。B2当前缺实际TX采纳sidecar、M1同源黄金和真实pins，保持独立PENDING。真人M1/M2交接待用户转发，尚未送达。
