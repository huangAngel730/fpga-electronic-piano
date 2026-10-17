# M2 内部静态边界核对：M1 第17批 B0 与 R06-C1

核对日期：2026-10-17。只读取附件 ZIP 内当前生产版 `repo/code/model/m1_r05_pcm_oracle_20261016/pro_successor_20261016/capture_compare.py`、其测试源码、B0 字段合同/README、`FINAL_RECEIPT.json` 及仓库 R06/C1 合同。未执行被审代码、测试、HDL、EDA 或设备操作。本记录不代替 M2 对整个附件的来源/CRC/发布范围核验。

## 结论

可以按历史窄 profile 的软件准备接入；不能作为已接好 R06 真实捕获、M1-R6-1 真实19字段语义、G1 数字链或 Pro 板测通过。当前实现没有发现将 REAL 误签通过的路径，无需为本次限定接入改写生产代码。

当前生产版 SHA 在 `FINAL_RECEIPT.json` 第52行登记为 `7213e9fdce5fcab4dd5828b282613def88e8f5d7566986e3af6b89ae9c899267`；完整包字节/manifest 身份由主窗口另核，本记录不以登记 SHA 代替原件核验。

## REAL 不能误通过的代码依据

- `capture_compare.py:29`：`APPROVED_PRO_MAP_SHA256` 为空。
- 第426–450行：缺 Pro source/ROM/map 原件或非受信 map 加入缺件；仅有自声明 approval 不产生准入。
- 第527–531行：无条件加入异步 reset、原始 driver/full trace/observer/source、工具/argv/双流/退出码/额度、连续性和同次真实性四类未验项。
- 第534–541行：初始状态为 `PENDING_REAL_CAPTURE`，`rtl_or_board_pass=false`、`board_release_allowed=false`。
- 第583–588行：REAL 只有 missing 为空才能选 `REAL_CAPTURE_PCM_PASS`；当前 missing 不可能为空。第617–618行对应 pending exit3。数学相等可显示 `identity_check/zero_lsb_check=PASS`，不能只取这些子字段当真实验收通过。

## 与 R06-C1 的具体差额

| 边界 | B0 当前实现/精确位置 | R06 接入要求与最小处理 |
| --- | --- | --- |
| 四 lane 共同推进 | 第275–285行要求四条 lane_cycles 按 lane0..3 且 cycle 同该事件沿；与共同 mask1111 语义相容 | 后继适配器读取一个实际共同 advance 事件，保留同沿四 lane；不能生成错开四拍或按 occupied mask 隐去空 lane |
| 时钟和采样相位 | 第226–234行只有严格递增整数 cycle；字段合同第23行排除同沿事件，没有 actual core/pre-NBA 域字段 | R06 原61字段必须按实际 core posedge 的 pre-NBA 原子行保留；B0 仅投影到已支持的 settled 场景。同沿应用/配置/推进等合法实际组合若不在旧 profile，明确 UNSUPPORTED/PENDING，不能挪动 cycle |
| FRAME F 与实际 ACCEPT A | 日历 kinds 第236–298行无 FRAME、request_first_valid、actual_accept；第307–319行只校 signed pipeline 最早时间，无 F 起算 deadline | 后继合同保留 F、first-valid、A、RETURN、commit、TX；A 最早 F+1，背压可更晚。另核 t-F<833 且早于下一独立 FRAME，不能将 B0 lane_tick 或旧D3 REQUEST 当真实 A |
| 输入应用和槽身份 | 第400–417行依已交的 event 应用周期重放已签 Reference 并核决策/slot/generation；没有独立驱动原件解析或实际应用出口绑定 | 数学重放逻辑可复用；真实 calendar 须来自 M3 独立输入及 M1 实际应用/slot/retire 公开事实，不得用 accept+1 或最终状态补算 |
| 全 FRAME 至真实 finish | 第201–216、299–320行只有文件自报 declared_count/八类counts 与交易关联；无独立 FRAME 计划或 finish/END | 另由 M3-R6-3/5/6 核独立 reset/clock/stop 计划及空闲/合法cancel后所有FRAME至finish。自报 counts 不证明漏行不存在；缺计划保持 PENDING |
| 异步复位 | 第236–243行仅逻辑 reset action；第395–399行拒绝重叠在途计算；第528行始终未覆盖 async reset | 保留当前窄 profile 和始终 pending 保护；R06 需原始 reset/lock 子周期事实、两级同步释放与首 PRE_NBA reset-high 功能沿，不能把 cycle0 reset 事件当全复位实证 |
| TX 采纳、HOLD、startup | 第352、362–364、381–383行要求每个 epoch/request 唯一公开样本并与 publish 集合全等；不接受同一请求多次 HOLD，也无 startup null ID | B0 只能处理每请求算术发布视图。真实接口映射必须明确它对应哪一级 PCM 发布；TX另保留 pending/held(epoch,id,clip,id_valid)旁带、tx_frame_id、HOLD继承和startup无合法ID，禁止把所有TX行直接灌本schema或将commit当TX |
| clip 编码 | 第372–376、577行使用 `[left_bool,right_bool]` | C1 packed bit0=left/bit1=right；新投影显式拆位，不能直接套数字或左右反序 |
| 配置/调度支持 | 第258–262行 delay length 0..1023、gain0..32767；第232–234行拒绝同沿；合同另限定 settled 八个安静时钟/advance+5/+7 | 这是旧已签 profile 的受限范围。源端配置宽度/真实接受语义未冻结前只报差异，不修改旧数学，也不能将其范围当新 Pro 硬件支持全集 |

## 发布/复用建议

1. 接入仅限 A0/A1/B0 新增目录及必要原件，保留原始 `FINAL_RECEIPT.json` 的离线来源、历史未发布状态和已消费执行信息；新的 M2 接入报告另写实际发布结果。
2. 把 B0 登记为历史 `R06_SETTLED_SIMULTANEOUS_LANE_TICKS_V1` 数学/软件准备，生产版当前始终 REAL pending。其名称中的 R06 是旧已签 profile 字符串，不能据名称认定已实现 2026-10-17 三岗执行卡 R06 的新包。
3. 不能为适配当前 C1 只填 allowlist、删除第528–531行或修改 result 状态；必须先有 M1/M2/M3 同版真实原件与后继合同/独立检查实现。当前限定接入不需要重跑旧30/32/新增1或旧黄金组，不恢复任一旧额度。
4. 未发现本范围需要阻止历史软件准备接入的具体代码缺陷；上述真实接口差额是已明示的范围边界，保持 PARTIAL/PENDING 即可。

本记录为 M2 内部自审辅助；没有启动审核员/预审员制度，没有向外部对话发送消息。
