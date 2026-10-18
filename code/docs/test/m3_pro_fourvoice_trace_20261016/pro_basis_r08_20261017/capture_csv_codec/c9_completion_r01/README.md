# task-day4 full C9 CSV codec

状态 L0 / SOURCE_READY / NOT_RUN。CLI encode/decode及encode_file/decode_file只逐行处理。CSV列为74个独立JSON字段cell，加完整schema/capture/origin/source/raw_ports/missing_reasons/events/semantics；null/X/Z、双clip、全部来源和语义均保留。

严格单物理行解析，JSON内部换行转义；单cell/物理行上限2MiB，并恢复调用前csv.field_size_limit。所有canonical JSON行仍受1MiB限制，避免跨行逻辑record绕过内存边界。合法140000字节语义cell另有待运行用例。编码解码后重核输入身份；文件不覆写。

新增三例，合计十个新接缝例由R7-A c9_completion_r01/selftest.py统一实现，本目录selftest.py是固定SHA局部入口。旧R8-07已签61字段源码/五例不改不重跑。本源码不证明真实来源或数学。
