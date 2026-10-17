# D3：Pro 同版原件摄取入口

## 2026-10-17 M2代修：漏FRAME期限旁路

用户本轮直接授权M2修复旧D3，仅修改本入口的三个期限边界：CANCEL清交易前独立检查`cycle-request_cycle < 833`，RESET由旧`<834`收紧至`<833`，RETURN也须在年龄833之前。即使缺少下一条FRAME，超期CANCEL/RESET仍不能把交易抹去后让END通过；END原有未完成交易检查保留。实际消费仍在下一条833/834拍FRAME同沿，不对已RETURNED等待该FRAME的所有中间记录一律判超时，因此合法834帧间隔及其中PA记录保持可接收。

旧源码SHA `3217f97e57daec534306a213c64566fa111e3116f15a15967ca881847c218e07`原字节另存`../ingest_deadline_fix_20261017/before_ingest.py`，仅供本轮已知缺陷重现，不能作为生产入口。旧R01/R02源码快照、结果、双流与夜间封包不改；下文16例/5例仍是历史版本结果。新定向harness和说明在`../ingest_deadline_fix_20261017/`，新输入/双流/收据与原件ZIP在`code/docs/test/m3_pro_fourvoice_trace_20261016/D/ingest_deadline_fix_20261017/`。本轮确切实际结果及SHA以该目录收据和M2自审报告为准，不把旧例并入最终版全量通过。

本次仍限L1合成软件期限拒收；真实Pro观察、M1黄金、完整链/时序/板测不由该修复签收。执行范围和本轮新有界软件预算见`code/docs/M2_D3期限旁路定向返修执行单_2026-10-17.md`。M3开工和完成消息待用户转发，尚未送达。

本入口只读使用旧 M3 解码器的严格 JSON 解析和 PCM24 舍入/范围判据，固定 SHA `da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb`。未重跑旧捕获或旧专项；不运行采集、RTL、EDA 或设备。

使用示例（先由 M2 固定真实原件，再填写实际 manifest SHA）：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -X utf8 'code/software/m3_pro_fourvoice_trace_20261016/D/ingest/ingest.py' '<manifest.json>' --sha256 '<64位现场SHA>'
```

可重放格式见证据 `D/ingest/ROUND_02/positive/`。该目录内 source/ROM 均明确标合成占位，不是 Pro 工程或 M1 黄金。实际到件必须替换为原件及现场 SHA，不能仅改 provenance。

- manifest：`M3_PRO_INTAKE_V1`，含 package、clock_hz、sampling_phase 与 source/rom/contract/calendar/trace 五个独占相对路径、大小及 SHA；拒收重复角色、缺件和越界路径，解析前后复核原件不变。
- 日历：`M3_PRO_INTAKE_CALENDAR_V1`，每笔独立 `epoch/req_id/cycle/lane_mask`；不是逐样本 PCM 数学黄金。C 的完整日历需经明确字段适配后接入，不冒称两种 schema 天然相同。
- trace：逐行 `RESET/FRAME/REQUEST/ACCEPT/LANE_TICK/RETURN/CONSUME/CANCEL/PA/END`，所有事件采用同一递增 sys cycle。每笔四 lane，PCM24 左右保留有符号整数；FRAME 分布使用输入实际833/834，不写死833。
- 返回严格早于下一 FRAME，消费在该 FRAME；到期未消费不能由 CANCEL/RESET 抹去。取消允许在下一 FRAME 前生效；同沿事件的采样/排序必须由 M2 observer 合同固定。
- `PA` 采用高有效候选规则 `pa_en = rst_n && stable`；`stable` 的真实来源、稳定等待及电平仍需 M2 固定。此入口不是功放安全证明。

本夜 R01 旧源码16例（1正15负）通过，但自审静态发现到期取消旁路；旧源码、runner及全部原件保留。修复后 R02 **仅5个相关增量例**（2正3负）通过，不能写成最终源码21项全量重跑。自审和原命令见两轮 RESULT/COMMAND_RECEIPT。

软件限定 L1。`DECLARED_REAL_PENDING_M2` 只表示声明的材料结构可核，始终 `pro_dut_pass=false`、`board_release_allowed=false`；当前 `PENDING_PRO_SOURCE_OR_TRACE`。未签真实 Pro 来源、48kHz实采、串行边沿、PCM数学、模拟延迟、实屏或硬件。

执行中来源更新：通过现有系统代理同步并快进至 `b6f289110a0b7341f1f9234c945bcb8d31d95aff` 后，M1旧R05五目录已恢复；旧“本机黄金缺失”只描述T0。新Pro source/trace及同版映射仍缺。新到原件仅只读核身份，未重跑303数学或任何旧专项，见总控 `SYNC_INTAKE/SYNC_INTAKE.json`。
