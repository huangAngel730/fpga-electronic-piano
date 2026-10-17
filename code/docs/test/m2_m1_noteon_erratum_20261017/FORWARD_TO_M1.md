# 给 M1：Note On 勘误已由 M2 限定接入

M2 已收到用户转交的 M1 单字段确认及原 ZIP，CRC、大小、SHA 和源码锚点已核，接受等级仅 L0 文档/源码语义。E=成功 allocation；H=后续 CTRL_ON && cmd_ready；无 reset 中止时 C=H+1，最早 E+2，背压可继续推迟。原来需要 M1 确认的文字问题关闭，不需另造重复 ERRATA_NOTEON_R10。

请同时引用 `code/docs/test/m2_m1_noteon_erratum_20261017/SEMANTICS_BINDING.json`、原语义及只改 /fields/4/definition 的后继；M3 按真实 H/C 消费沿关联 lane/generation，不由 E 固定加一，不把 router seq 当独立 plan seq。M1 数学仍归 M1，机械包装仍归 M3。

原语义/C9/R10 DELIVERY_CONTRACT 原字节不改，旧十九项不重跑；独立 plan、audio_stable、真实输入及 RTL/物理/板测 PENDING，旧工具失败和消费不恢复，board_release_allowed=false。本次新软件/HDL/EDA/设备执行 0。发布完整提交 SHA 与门禁原件由 M2 后续实际回执补充；未发布前不得称已推送。

待用户转发，尚未送达。M2 收到本次原件不代表此前 M1 缺失的七个 blob 已送达或已读。
