# 夜间任务3：C真实R05消费者（PARTIAL）

本轮基线 `c12636c034be62e10c564217298564422a533b9c`。写集仅本软件目录及对应 C 的 `docs/test/.../night_20261016/`；没有新增RTL，没有启动A仿真、Gowin、硬件或Git写命令。旧C诊断夹具不重跑。

`consume_capture.py` 独立流式解析 `M3_R05_PUBLIC_PRE_NBA_V1`，不导入A checker，不使用旧C诊断输入日历。严格检查JSON重复键、类型/X、连续沿、独立RESET、唯一END；按公开接受/提交ID重建pending/held/clip元数据，按真实frame_tick核833/834及每三个间隔2500拍。已有下一帧却未提交的请求失败，包括首个请求；RESET取消单列。尾部尚未到帧截止的请求保留UNKNOWN，不能以停钟或缺帧无限延长尾段。

串行依据只读冻结 `i2s_tx.sv` SHA `6c703e31064e5943df4e310b3baddd8935362a1c028828d8e11f8f3c016267ad`：40MHz，BCLK相邻半周期6/7拍、完整周期13/14拍，WS低右高左，每半帧32上升沿，最后16位有效，前16位零；PCM24以+128、算术右移8位、PCM16饱和。WS/DIN仅可在BCLK下降沿改变。只在完整物理WS边界后解码，复位切断的半帧不伪造完整字。各真实frame_tick的pre-NBA播放PCM作为独立预期，与引脚字逐样本比较；held重复不算新commit。

`consume_real.py` 在上述原始轨迹验收之外要求A新成功回执的明确SHA、实际三工具argv/cwd/双流/退出/预算、执行源与stage前后SHA、冻结69单元/ROM、三项候选改动、一次消费/PREFLIGHT和输入时间线。只读实际文件，不执行任何A程序。输入合同包含最新 `INITIAL_INPUTS`；逐沿时间差必须25ns且和音频reset/cycle对齐，RESET时间必须落在对应时钟窗口。真实成功正分支因缺新采集而 **未实跑**；不能把它已写好说成真实来源通过。哈希仅提供字节身份链接，不是数字签名或独立的工具执行认证。

调用示例（从仓库根，输出必须全新）：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -X utf8 `
  code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/consume_capture.py `
  REAL_CAPTURE.jsonl --sha256 <原capture完整SHA256> --output NEW_RAW_RESULT.json

& 'C:/Users/songdongkuan/miniconda3/python.exe' -X utf8 `
  code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/consume_real.py `
  --producer-receipt <A新成功RUN_RECEIPT.json> `
  --receipt-sha256 <该回执完整SHA256> --output NEW_REAL_RESULT.json
```

真实消费前应先取得A的 `CAPTURE_READY.json`、`REAL_CAPTURE.jsonl`、`REAL_INPUTS.jsonl`及其成功回执本体；READY字段尚无实际发布原件，本实现不猜其字段、不把文件名当来源认证。使用READY所指向的成功回执和SHA作显式参数。若未来回执/合同有版本变更，先核精确差异，再改最小适配，不能修改原capture/header或补零。

已运行的软件回归命令、Python3.12.4绝对路径/EXE SHA、前后源SHA、双流、退出与秒数均在各 `RUN_RECEIPT.json`。最终主消费者49项、来源/输入时间线26项、真实TB成功标记窄回归11项通过；合成数据一律有SYNTHETIC标识。窄回归只读原7ms stdout核实际完整PASS标记，不重跑或升级该旧证据。

每笔数字时间≤400000个40MHz拍的判据有边界测试；真实R05数字上界本轮UNKNOWN，模拟输入到输出≤10ms也UNKNOWN。未公开first-valid、数学clip正确性、四独立声音数学、真实PLL/HDMI、STA与板级均未由本软件签收。`board_release_allowed=false`。

A已发布 `CAPTURE_BLOCKED.json`：平台审批阻断，新增功能进程0，真实capture和READY未生成。C只封软件成果，不转用旧fixture。本轮不提交/不推送，由夜间总控统一门禁与发布；给M2的回执待用户转发，尚未送达。
