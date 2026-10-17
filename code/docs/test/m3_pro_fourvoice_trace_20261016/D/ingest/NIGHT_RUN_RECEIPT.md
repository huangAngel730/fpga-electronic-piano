# D3 摄取入口：夜间回执（2026-10-17）

状态：DONE（接口无关软件入口的限定范围）；真实 Pro 对照 `PENDING_PRO_SOURCE_OR_TRACE`。L1，`board_release_allowed=false`。未提交、未推送；最终统一发布状态以总控回执为准。

本包只写软件 `D/ingest/` 和证据 `D/ingest/`。输入为现场已核旧 decoder（README列完整SHA）、任务单及独立合成夹具。机器/绝对Python路径及EXE SHA、cwd、起止、固定源码与输入SHA、每条CLI原双流和退出码分别在 `ROUND_01/ROUND_STARTED.json`、`ROUND_02/ROUND_STARTED.json` 和各 `COMMAND_RECEIPT.json`；源码本体在各轮 `source_snapshots/`。

- R01：16条CLI，1正例exit0、15拒收例exit1，1.594秒；旧版结果保存。该组通过后静态自审发现到期漏消费可被CANCEL抹去，列为旧版已知缺陷，不能以16例通过掩盖。
- R02：修复到期取消旁路，仅5条相关CLI，2正exit0、3拒收exit1，0.718秒；包括允许期限前取消、拒期限后取消/同拍返回/RESET掩盖漏消费。最终5项增量通过；未在最终源码重跑R01全部16例。
- 合计2轮、21条CLI、2.312秒；从D共享六轮分配，D/D2剩余上限4轮。Python每轮≤90秒；Icarus/ModelSim/Gowin/设备调用0。首轮无运行失败，静态发现及旧源码未删除。

核心差额：缺 M2 新 Pro 精确 source/ROM/top/端口采样合同、真实 req/epoch/lane/左右PCM/frame/PA 原日志；M1数学黄金亦未到。现有 schema 是显式夹具入口，真实接入需 M2 映射 observer；C 冻结日历字段另交 M1，不由本入口签 PCM 数学或DUT串行边沿。下一责任人 M2 固定同版原件和 observer、M1固定黄金；M3收到真实材料后在新有效许可内消费。两份人岗交接均由总控准备并待用户转发。
