# 主控接入合同（精简 exact-target schema）

## 输入

`endpoint_audit.py --targets targets.json --targets-sha256 <外部核准SHA> ...`

```json
{
  "schema": "m3_audio_endpoint_targets_v1",
  "clock": "sys_clk",
  "period_ns": "25.000",
  "source": {
    "kind": "FROZEN_PHYSICAL_ZIP",
    "archive_sha256": "17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff",
    "member": "pnr/timing.html",
    "report_sha256": "524cea6ebb93eca719c5aa86cd6413129299ac2c9da78467ac7709cdf4e8ec62",
    "metadata": "必须是下列九项精确字符串组成的对象，不是本占位字符串"
  },
  "targets": [
    {
      "id": "由主控按真实清单给定的唯一ID",
      "from_node": "报告原文完整起点，含/Q等pin，不得通配",
      "to_node": "报告原文完整终点，含/D或/AD[n]等pin，不得通配",
      "require_directed": false
    }
  ]
}
```

以上是说明性模板，不是可通过输入。完整可运行 JSON 位于 `runs/R02/originals/targets.json` 和
`runs/R02/synthetic_positive/targets.json`；主控只读复用/在自己 `coordinator/` 写适配文件。

九项 metadata 键必须齐全且值等于原 HTML message 表中的字符串（仅 HTML 实体解码和字段内空白折叠）：
`Report Title`、`Design File`、`Physical Constraints File`、`Timing Constraint File`、`Tool Version`、
`Part Number`、`Device`、`Device Version`、`Created Time`。
原报告路径文本含双反斜杠；不要自行把它归一化为不同字符串。

source kind 只有以下三种：

- `FROZEN_PHYSICAL_ZIP`：必须为上述原 ZIP 和原 report SHA，不能重签替换。
- `M2_NEW_REPORT`：用于未来 M2 已独立核准的新原始 HTML；精确 report SHA/metadata 仍由已核目标计划冻结。
  本工具不认证许可签发者，不允许把 `SYNTHETIC_TEST_ONLY` 报告改标签变成真实。
- `SYNTHETIC_TEST_ONLY`：仅软件正负例，没有真实物理签收含义。

每个 target 只能有 `id/from_node/to_node/require_directed` 四项，1..64个；from/to 完全逐字相等，
不能以 substring、前缀、正则、clock-only 或“任意音频路径”命中。
`require_directed=false` 可检查精确 pair 是否存在于原 Setup/Hold slack 表，但不声明定向命令已执行。
`true` 要求原命令字符串为 `report_timing -setup/-hold -from [get_regs {<精确reg>}] -to [get_pins {<完整精确终端>}]`
及可选 `-max_paths N -max_common_paths N`；只有 `to_node` 以 `/D` 结尾时，另允许 `-to [get_regs {<该FF实例>}]`。
RAM/ROM地址终端和FF使能终端不得剥掉 pin 冒充 FF，`get_regs` 不得替代 `/AD[n]`、`/WAD[n]`、`/CE` 的 `get_pins`。
from端仅支持FF `/Q`，先去掉 `/Q` 得实例名；所有collection对象中的 `[`、`]` 分别编码成 `\[`、`\]`，
不得删转义让索引变成glob字符类。raw report `From Node/To Node` 仍是无转义的原文精确名。

例如 lane3 pair 的生成命令（仅文本，未运行）：

```tcl
report_timing -setup -from [get_regs {g_polyphonic.u_audio_core/u_chain/u_audio/u_bank/u_pitch_mod/g_lane\[3\].u_control/total_s2_10_s0}] -to [get_pins {g_polyphonic.u_audio_core/u_chain/u_audio/u_bank/u_pitch_mod/g_lane\[3\].u_control/oct_lut_oct_lut_0_0_s/AD\[7\]}] -max_paths 1 -max_common_paths 1
```

此规则与主对话4 `STA_PROPOSAL_NOT_EXECUTABLE.tcl.txt` 保持相同查询类型和转义，不修改该提案。
其他命令排列、自动规范化后的tool echo、新query语法需 M2 明确适配，不能通过放宽selector求PASS。

## 两种调用

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -B -X utf8 code/software/m3_m2td_audio_endpoint_audit_20261015/endpoint_audit.py --zip 'code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_整机PnR_STA_20261015.zip' --zip-sha256 17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff --targets '<主控已核目标JSON>' --targets-sha256 '<主控核准SHA>'
```

未来新原件使用 `--report <原HTML>` 代替 ZIP 两参数，plan kind 为 M2_NEW_REPORT。
报告文件上限 32 MiB；只读取，不改写报告，不接受中间 records JSON 代替原 HTML。
输出 stdout JSON；exit0 为 `SPECIFIED_REPORT_ENDPOINTS_SHOWN`，exit1 为 `REJECTED` 及指定 diagnostic。
无论 exit 是否0，`board_release_allowed=false/new_sta_executed=false/physical_signoff=false`。

## 当前主控预期

对原 ZIP 中已出现的 lane3 pitch Hold pair，命令真实 exit1/`MISSING_SETUP`。
对未找到的旧 `base_s1_18_s0`→`base_s2_18_s0`，exit1/`ENDPOINT_ABSENT`。
这不是原整机 L5 失败，而是没有足够原报告支持新增**指定端点**通过；不能把缺项改成PASS。
主控可据真实清单组成多个 targets，任何一个缺失都会退出1；工具从原文重新取span，
即使清单中的预计算slack或activity被篡改也不能代替原文。
