# B0 独立日历与公开 PCM 比较入口

本目录只交付新入口、字段合同和**合成夹具**。实际命令、双流、退出码与结果由本轮总封存登记；本文件本身不宣称已运行。既签 Reference 的算术直接导入，未复制 DDS/ADSR/音色/混音/效果计算，也未运行既签旧套件。

范围是 `R06_SETTLED_SIMULTANEOUS_LANE_TICKS_V1`：四 lane 同时 tick；advance+5 读既签快照；效果接收最早 advance+7，允许更晚；每次 sample 前依既签 Reference 至少八个安静时钟。拒绝 stagger、同沿事件/重触发/退役仲裁、前端时序猜测以及 sample 计算窗口内的配置/事件。不是 Pro 调度器、deadline 或串行链的替身。

公开 PCM 的全部 scene、epoch、request、lane、source/channel/note/generation 身份先验完，再做 L/R PCM24 和双声道 clip 的零 LSB 比较。每次 lane_tick（包括未公开、未接受 work）、每次 effect_accept（包括取消公开）、reset、config_accept 都必须来自 M3 独立日历。DUT 内部 wave/env/phase 只可放入可选 `diagnostics`，不参与黄金生成。只有公开 PCM 而无内部观测时，首差异同时给四 lane 的期望音色/包络/混音/效果，`lane=null` 并明确不能唯一归因。

当前 Pro top 源码、ROM 对应及端口/复位映射未交付，代码内 `APPROVED_PRO_MAP_SHA256` 为空。本 profile 只有逻辑 reset action，未覆盖异步 `RESET_EDGES` 子周期事实；即使将来映射齐，也不能消掉此未验项。`REAL` 无论是否数学相等，均不能取得真实准入；缺件或未签映射返回 `PENDING_REAL_CAPTURE`。不允许把 `SYNTHETIC_FIXTURE` origin 用 `REAL` mode 接收。SHA 证明所收字节身份，不提供采集来源的数字签名；将来还须 M2 核验原始采集和映射原件。当前真实状态夹具：`fixtures/pending_real.bundle.json`。

静态原件夹具 `fixtures/synthetic_idle.*.json` 是人工明确填写的 idle/取消/reset 零值接受例。新自检另在临时目录用已签 Reference 生成有四个不同 source/channel/note、混合音色、已接受但未发布工作、未接受 advance、释放和 reset 的合成输入，验证解析与拒绝路径；不会写回仓库或旧原件。

建议从仓库根执行（输出名须全新，父目录须先存在）：

```powershell
python -X utf8 -B -m unittest discover -s code/model/m1_r05_pcm_oracle_20261016/pro_successor_20261016 -p test_capture_compare.py -v
python -X utf8 -B code/model/m1_r05_pcm_oracle_20261016/pro_successor_20261016/capture_compare.py --manifest code/docs/test/m1_r05_pcm_oracle_20261016/pro_successor_20261016/B0/fixtures/synthetic_idle.bundle.json --out code/docs/test/m1_r05_pcm_oracle_20261016/pro_successor_20261016/B0/synthetic_idle_result_R01.json
python -X utf8 -B code/model/m1_r05_pcm_oracle_20261016/pro_successor_20261016/capture_compare.py --manifest code/docs/test/m1_r05_pcm_oracle_20261016/pro_successor_20261016/B0/fixtures/pending_real.bundle.json --out code/docs/test/m1_r05_pcm_oracle_20261016/pro_successor_20261016/B0/pending_real_result_R01.json
```

CLI：`SYNTHETIC_FIXTURE_PASS=0`；`PCM_MISMATCH=1`；`CONTRACT_REJECTED` 或输出拒覆盖 `=2`；`PENDING_REAL_CAPTURE=3`。所有结果 `board_release_allowed=false`；本入口不签综合、PnR、STA、码流、真实发声或板级通过。拒绝覆盖已存在文件，即使其中是旧失败。
