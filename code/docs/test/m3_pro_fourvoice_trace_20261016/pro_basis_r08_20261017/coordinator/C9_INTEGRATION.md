# C9 同版接入与限定交付

整体仍 PARTIAL。本节是发布前新到 C9 的 L0 静态后继，不把原 R08 已测20项/204个匹配用例升级为 C9 功能通过；原 R08 27例、旧 R7-C 6例 NOT_RUN 和全部消费不变。

发布父基线 16ac226552f6fb65347b229b8fad42146ed45644。M2 C9 源包182685字节，SHA d458ab16277bd46751318ac368b22df1b21b35c4867c47942e7bff7d27fc3aa2；M1原包166433字节，SHA 019d50298c171b4359c7882a092f11f5b582033a8d81cb318f22b817a6c3e287。总控分别核86/60个载荷大小、SHA及ZIP CRC；76份新发布文件与Git blob核同。原件见 C9_INTAKE_RECEIPT.json 与 DELIVERY_C9 补包。

- 夜间2：R7-A 唯一公开采样 TB/passive observer及codec接入67观察口、5外部pins；74字段逐项来源矩阵与R8-02精确接线后继。原R6-2 driver复用；无私有层级。64MiB批处理限制明确，不能据此签大规模完整采集能力。
- 夜间3：R7-B 新旧同名M1源分成独立装配，两路同输入公开行为流及伴随字段；合并入口供既有B比较器，未执行比较。A的唯一74字段采集依赖另列；B伴随流不冒充完整A采样。
- 夜间4：R7-C 74字段机械桥，保留kind/mask/router序号有效位、config_take和三类clip；A封装适配按原始身份保留，未运行候选。
- 夜间5与各写者子智能体：只读具体增量自审；总控核文件身份、原始包与封包边界。未启动审核员/预审员制度，不替代M2最终复核。

kind3/4/8的零data/seq且valid0是无效原因哨兵；kind1/2同seq多阶段不去重，合法seq0保留。内部router_apply_seq不替代独立input-plan apply_event_seq。advance_frame_req_id仅请求tag，FRAME F来自frame_tick；四路同时推进只接受advance_mask=1111，部分/X/null保留。配置仅依实际config_take解释62位拼接，upstream/effect/feedback三clip独立保留。M1“分配前一沿”文字待勘误，不生成固定延迟期望。

所有42个C9新增用例（A/R8-02共12、B13、C17）和SYNTHETIC原件均为待运行输入，不是日志或测试结果。没有为C9启动功能组、导入候选、HDL、EDA或设备；纯文件读取/哈希/CRC/封包属于元数据核验。独立plan映射、audio_stable、真实trace/PCM及可信执行器、物理/板测仍待。

DELIVERY十卷保持原字节；DELIVERY_C9/M3_TASK_DAY2_C9_STATIC_SUPPLEMENT.zip按仓库相对路径封存所有c9_binding原件，含SOURCE_STORE和INPUT_ORIGINALS。需要完整原件时先在独立资料目录按归档路径解包，读取各包README；源码装配ZIP可独立展开。解包/静态装配不构成候选或HDL执行许可。Git直接文件保留小入口/合同及源码，生成的原始闭包在ZIP中。

最终READY、源码SHA和静态收集收据见 PACKAGE_STATUS.json.c9_static_successors。各旧报告中的“尚未收到M1十九项”属于历史状态：现在静态来源已到，但M1勘误/独立映射/真实输入并未闭合。最新准入目标应为C9精确装配；C5/C6仅保留历史证据。M2最终登记及许可决定待用户转发，尚未送达。
