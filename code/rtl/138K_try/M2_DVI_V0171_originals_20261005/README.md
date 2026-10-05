# M2 DVI / V0171 原件补件（2026-10-05）

本包按用户补件请求汇集已有原件，没有重生成 DVI IP、改写历史 manifest 或运行综合/PnR。

## 内容

- originals/dvi_gui/：2026-09-27 GUI 生成 DVI_TX_Top.v（保留原 CRLF）、IPC、定义文件、生成临时顶层及生成日志/资源报告。
- originals/dvi_actual_lf/：V0171实际工程使用的 DVI_TX_Top.v LF原件；与GUI版只差CRLF→LF。
- originals/V0171/：原最终 input_manifest.json、实际 GPRJ/gprj.user/run.tcl、PnR cmd.do/device.cfg、build.log/build_exit.txt、原始 STA/资源/引脚与综合报告、实际新parser以及原CST/SDC。
- FILE_LIST.tsv / FILES_SHA256.txt / PACKAGE_INVENTORY.json：此次打包新生成的清单，**不是原 V0171 manifest**。原manifest位于 originals/V0171/input_manifest.json，字节未改。

## 校验和使用边界

1. 先核对聊天中给出的ZIP SHA256，再逐文件核对 FILES_SHA256.txt。
2. 原 GPRJ/Tcl/cmd.do及manifest保留M2原机器绝对路径，不是开箱即运行的138K工程；在你自己的副本中搬迁路径，并核对每个输入哈希，勿改这份封存原件。
3. 不包含其余46个输入的重新整理包或 Gowin 工具；用户已确认这些输入和CLI已汇齐。若自动工具需要完整可搬迁工程，可将本包缺件装入已恢复的同版输入集。
4. DVI为60K上原GUI配置的源码（DVI TX3.0/TLVDS）。不宣称138K B/C兼容；60K INS_LOC、IO、电压和IP迁移需独立有据说明，不扩大声部或放宽SDC。
5. 用原60K基线先作控制组，再在138K副本试验，维持原50/25/125MHz及sys Hold uncertainty 0.550ns。本包未给出新138K STA结论，也不授权下载/烧录。
6. 本包保存的是 V0171 parser-only实际运行原件，不是 V0165失败旧 physical1，也不是重写的JSON摘要。V0171工具门禁通过不表示达到系统+0.5ns工程余量（原Setup+0.017ns、Hold报告边界0.000）；不得由此宣称系统稳定。

原件31项左右以 FILE_LIST.tsv 实际行数为准；对关键3件已严格匹配用户指定SHA256。此README及校验清单为此次说明资料，与原生成/运行文件分开保存。
