# R8-02 C9 端口静态后继（L0，未运行）

基线16ac226552f6fb65347b229b8fad42146ed45644。新增独立c9_binding，未修改已测m3r08_02.py、共用helper或M1/M2源。R08 S50匹配仍只覆盖旧冻结输入，不能覆盖本C9后继。

ACTUAL_C9_REQUEST.json固定实际M2 C9 wrapper、官方exports/schema/合同/源ZIP、R7-A C9 TB/passive observer和原driver身份；STATIC_DECLARATION_COMPARISON.json逐项列67口实际声明。C9_COMPLETE_CAPTURE_MATRIX.json进一步列67期望obs+5pins的DUT连接、passive连接、raw key、69个实际映射字段，以及全部74字段的来源/排除/缺项。仅apply_event_seq/audio_stable没有实际来源；新路由十九项及伴随量不再统写PENDING_M1。

后继CLI为`c9_ports.py --request ACTUAL_C9_REQUEST.json --output NEW_DIR`。当前仅交代码、不执行。未来调用时复用固定SHA旧R8-02 lexical checker，并额外强制67个obs输出和passive输入的方向/width/signed一致，且每个口唯一、非空、直接接同名net。输出留空即使旧parser接受，也由C9后继拒收。比较成功仍只报告PENDING_C9_FUNCTIONAL_AND_HDL_NOT_RUN，不生成准入。

四个待运行案例为实际同版绑定、DUT kind口留空、driver ready错误相连、passive PCM signed丢失；都未执行、未分配组预算。字段语义保留kind/mask/router seq/valid、实际config_take及三clip；请求tag≠FRAME，实际lane_tick才推进，独立plan映射和audio_stable仍待真实输入。M1 NoteOn文字勘误不由本项代签。

本交付的检查仅为文件身份、JSON和源文本的L0核对，没有候选导入/AST/功能/HDL/EDA/设备执行，也不全面重审旧包。真实采样、周期语义、可展开性和物理验证均未签。
