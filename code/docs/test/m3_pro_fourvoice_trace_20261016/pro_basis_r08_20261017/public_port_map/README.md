# R8-02 公开端口核对准备

PREPARED_NOT_RUN，十二例归总控 S 组。入口：同名 software 目录 `m3r08_02.py --request REQUEST.json --output NEW_OUTPUT_DIR`；输出 module_ports.json、connections.json。

请求 schema=M3_R08_PORT_MAP_REQUEST_V1，包含 module_files、top_file 文件身份、required_modules 及 direction_rules。只读取 ANSI 声明、named 参数/端口连接、受支持表达式位宽及裸 net 输出驱动。缺必需输入、错方向、位宽、同网多输出或私有层级拒收；不支持的宽度/输出范围保持 UNRESOLVED。

参数覆盖只在调用方环境解析，再应用到被调模块；同名未知量不使用被调模块默认值代替。调用方当前仅取源码默认参数，报告不声称外部工具参数覆盖已核验。参数及端口元数据完整输出，compile_proven=false。

实际公开driver的event_ready是output，接driver_ready_not_connected；DUT的obs_event_ready另网，公开core clock送observer。event64、ID32、signed PCM24与clip mask2依据真实声明读取；不从信号名称推断方向。HDL未编译。
