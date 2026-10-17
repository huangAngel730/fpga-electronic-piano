# task-day4 C9 streaming capture

状态 L0 / SOURCE_READY / NOT_RUN；仅总控可执行本轮冻结软件组。

入口 c9_stream.convert_files(raw,resets,end,stdout,output_dir,origin) 返回 artifacts.public_rows、derived_raw_43、line_index。输出目录必须新建且独占。原始raw不复制进内存，逐行生成43口派生文件，复用冻结assemble.stream_rows(Path)的时基/reset/finish算法，再逐行合并完整C9 74字段与72个raw量。两遍原raw各有增量SHA核对，结束重核全部输入。派生投影只供旧验证，不代原始来源；物理行SHA另存RAW_PUBLIC_LINE_INDEX。

固定边界：单JSON行1MiB；reset/end/stdout元数据各16MiB；raw64GiB；每产物512GiB；最多一亿行。超限拒收并留失败原件。更大窗口必须另做受控适配，不能删行/抽样/改终点凑过。与冻结C9 codec的64MiB整窗限制分开，本次新用例实际生成>65MiB文件再往返。

common.py SHA固定55cb7481…c996dca。只复用冻结pure算法；未新造observer/FRAME/DSP。源码/用例未import、compile或执行。真实采集、独立plan、audio_stable、M1数学和M2可信准入保持PENDING。API.json为总控调用入口。
