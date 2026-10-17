# R7-D capture来源一致性工具

capture_provenance.py只核文件身份、声明关联和R7-A原行来源。它不执行工具、不授予准入、不认证作者/签名/实际工具运行或独立输入，不重建PCM数学。即使CLI返回0，status仍STRUCTURE_IDENTITY_MATCH_ONLY_REAL_PENDING，M2_admission=PENDING，pro_dut_pass/board_release_allowed=false。

CLI：`python -B -X utf8 capture_provenance.py --manifest <capture.json> --expected-sha <独立冻结SHA> --output <全新封包目录> --registry <登记目录> [--registry-sha <已有同id记录SHA>]`。不会启动清单中的argv。已有id时必须提供独立冻结的registry记录SHA，且manifest/source/ROM/tool/raw全部签名一致，禁止把同capture_id重新签给另一版本。登记本身也只是本地不可复用身份，不是可信签发或M2认证。

M3_R7D_CAPTURE_MANIFEST_V1顶层只有schema/capture_id/kind/artifacts。kind为SYNTHETIC_PROVENANCE_TEST或DECLARED_REAL_PENDING_M2。21个必须role为source_manifest、rom_manifest、driver、observer、tool_manifest、execution_receipt、raw_stdout、raw_stderr、input_plan、window_plan、reset_edges、frame_plan、raw_trace、normalized、d3_projection、b2_projection、pcm、tx_sidecar、projection_tool、projection_manifest、finish_receipt。各role精确path/bytes/sha256，路径限制到原件根内，禁止穿越/绝对路径/角色别名/大小写路径冲突；缺件拒收，不拿marker补真实输入。

source/ROM/tool清单为M3_R7D_FILE_CLOSURE_V1及非空files列表；逐文件核本体，不保证所列即完整编译闭包。tool另绑定argv/cwd/version；execution_receipt精确绑定source/ROM/driver/observer/tool/input/window/双流/raw/reset/finish SHA，必须声明exit0、无timeout、清理完成及非空PID/group/带时区起止。身份匹配不能证明PID或运行声明真实，仍待M2的可信执行收据。

独立window_plan为M3_R7D_INDEPENDENT_WINDOW_V1，绑定input_plan SHA、capture_id、plan_stop_id、首core时间/周期、finish_cycle/time和row_count。按A实际格式：source_line从1、cycle从0，因此finish_cycle=row_count−1，finish_time=first_core_ps+finish_cycle×period。不得从被核FRAME/trace反推此计划；工具只能检查声明一致，独立性本身仍待可信准入。

原始raw/END采用A实际M3_R7A_RAW_CORE_ROW_V1、M3_R7A_END_V1。逐raw行核capture_id、原source_line/cycle/time、只在最后一行finish=1；核独立计划末拍/行数，END理由PLANNED_WINDOW_END。stdout须唯一且精确匹配`MONITOR_END capture_id=... cycle=... time_ps=... rows=... reason=PLANNED_WINDOW_END`；不能用EOF或一个布尔完成声明替代。RESET_EDGES至少一条同id的M3_R7A_RESET_SNAPSHOT_V1，不代R6-6推导epoch/复位电气。

normalized为A的M3_R7A_PUBLIC_ROW_V1 JSONL，逐行核capture_id、source.raw_sha256/reset_edges_sha256、line/cycle/time_ps/POSEDGE_PRE_NBA与raw一对一且全覆盖。字段值、X/null理由、HOLD/F-A、epoch语义由A/R6-3/5/6负责，不被本工具重算或丢弃。projection_manifest为M3_R7D_DERIVATION_LINKS_V1，绑定projection_tool/raw/reset/input/window与六份派生物的SHA；换投影或换原输入会被拒收。其他投影数学和重放结果仍NOT_RECOMPUTED，不能把身份闭合写成checker通过。

封包只含该capture列出的role本体、source/ROM/tool files、原始capture manifest和新载荷MANIFEST；生成后重开核CRC/大小/SHA。原件不改写；若登记/封包失败保留失败残件，不覆盖旧包。通过只建立结构关联，真实capture、M1语义/黄金和M2实际准入未到保持PENDING。

本轮合成正例使用A相同的RAW/END/规范行外壳，0起点cycle与真实日志标记格式；ports/61字段不声称完整A schema测试，工具/PID是显式SYNTHETIC声明，未真实执行该假捕获。真实软件启动证据只在本包RUN_01原收据/双流，不与夹具中execution_receipt混淆。R06旧组均不执行。
