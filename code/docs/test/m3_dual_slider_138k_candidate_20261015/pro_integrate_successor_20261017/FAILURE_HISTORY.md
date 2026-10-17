# task-day E1静态核验首失败

RUN_01消费1/2，audit退出1，未启动seal；0.860s，无超时，源码/输入/工具前后一致。原命令、cwd/机器/PID、原stdout/stderr、退出和身份在RUN_01。唯一定位为`ANCHOR_MISMATCH:scanner_origin:frame_start = line_start && pixel_y == 0`，原stderr SHA e83df6730d992b932a288e751ddafd43c91e3e7cc088e79de305173873945baf。

原因：ANCHOR_SPEC把扫描器原文范围写16–34，但frame_start赋值实际第35行。核对真实code/rtl/common/video_scan_timing.sv后，只将该范围末行改35并同步差异表；对应原语句、源SHA、判据文字均未变。不是新Pro故障或RTL坏例PASS，不放宽UNKNOWN/准入。旧ANCHOR_SPEC、差异表与消费文档已从可逆改动恢复原字节并与RUN_01/before.json逐件核SHA，实际本体保留RUN_01/execution_sources，非仅提供SHA或反推期望；原执行脚本/双流/收据未改。

同次静态修复顺带消除收据缺口：runner现在将全部新源指纹文件（含ANCHOR_SPEC/三份差异表）实际复制进本轮execution_sources，不只记哈希；RESULT的software_validation_round改从RUN_nn读取，避免第二轮仍写硬编码1。均不改旧源码或UNKNOWN判据。第二轮运行后仍以CONSUMED/实际receipt为准。

下一步仅允许有此具体修复的RUN_02，仍总90s/最多2轮，成功即停；不删除首失败或新换包获得额度。无新功能正负例，ModelSim/Icarus/Gowin/设备0。
