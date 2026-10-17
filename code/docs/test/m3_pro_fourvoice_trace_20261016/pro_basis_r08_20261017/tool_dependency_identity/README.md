# R8-05 实际工具文件身份准备

PREPARED_NOT_RUN，七例归总控 S 组。入口：同名 software 目录 `m3r08_05.py --request REQUEST.json --output NEW_OUTPUT_DIR`。仅文件读取/哈希/静态脚本导入与PE导入表解析；不启动EXE、不导入DLL、不取工具版本。

EXTERNAL_INPUTS.json 已由静态文件读取采集13份实际文件的绝对路径/大小/SHA，NATIVE_READ_REQUESTS.json 含Python、ModelSim SE候选vsim/vlog/vlib与Gowin两个程序共六份只读请求。版本字段不是新探测结果；目录名不构成版本/许可证确认。PATH中另一个ASE程序不等于这里固定的SE候选本体。

总控执行前须将EXTERNAL_INPUTS.json中的外部路径列入精确只读白名单；不能为测试运行这些文件。coverage=IDENTITY_ONLY 时未闭PE/动态依赖保持UNKNOWN；合成closure案例会对已指定必需依赖漏项拒收。实际请求始终PENDING_UNKNOWN，DLL清单只是当前可读子集，不宣称装载闭包完整。

产物保留每个实际文件身份和引用边、unresolved项；executables_started=0、DLLs_loaded=0、version_probe=NOT_RUN、process_cleanup_proven=false。实际工具版本、许可、依赖闭包和安全执行器均待独立确认。
