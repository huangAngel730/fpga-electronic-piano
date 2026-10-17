# R8-01 递归依赖审计准备

PREPARED_NOT_RUN，八例仅归总控 S 组。入口：同名 software 目录 `m3r08_01.py --request REQUEST.json --output NEW_OUTPUT_DIR`；输出 dependency_graph.json。

请求 schema=M3_R08_INCLUDE_AUDIT_REQUEST_V1，archive 为 path/bytes/SHA 身份，selected_list 为 inputs/ 下相对编译清单。读取清单、+incdir+、递归 literal include、literal readmem、模块唯一性与路径边界；不调用编译器。参数、运行时或宏决定的路径保持 UNKNOWN。

实际 C6 以固定 SHA 接入，定位71单元、9 ROM、2头及3条include边；其参数/运行时 readmem 尚未 elaboration，预期 PENDING_UNKNOWN。错误 incdir、缺头、重复模块和路径逃逸拒收。C5缺陷原件不覆盖。当前没有编译、综合或时序结果。
