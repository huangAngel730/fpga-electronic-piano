# B2公开CSV串行桥接测试视图

这是新软件适配器的隔离测试/接收视图，不是正式Pro接口或B1的61字段trace格式。来源文件的安全摄取与M2身份准入继续归B1；本包只做显式输入SHA、跨输入basis一致及逐沿/串行检查，不复制D3来源摄取，不调用旧R05 analyze、自测或采集。

实际CLI为`adapt_serial.py --binding <B2测试视图> --sha256 <独立冻结SHA> --csv <原29列CSV> --samples <公开TX采样记录> --calendar <B1独立帧请求账本视图> --oracle <M1同源只读PCM视图> --output <全新目录>`。具体绝对argv/cwd和原双流见每CASE_RECEIPT；缺实物不安排串口/下载。

| 输入 | 格式和严格边界 |
| --- | --- |
| binding | B2_PUBLIC_SERIAL_ADAPTER_BINDING_V1；40MHz候选SYS_POSEDGE_PRE_NBA、frame_transaction ID域、CSV/samples/calendar/oracle SHA、source/ROM/input声明basis、声明观察末拍。来源声明匹配不等于真实来源准入。 |
| CSV | 上午monitor的29列原表头，cycle从1连续，epoch仅从实观reset-entry递增；ID8hex、payload16hex、PCM24有符号十进制。保留原CSV本体及原始行号；不补行、不重新编号或补造串行pins。 |
| samples | B2_PUBLIC_TX_SAMPLES_V1，每frame同cycle/epoch给frame_id、identity_valid、实际选中request_id、left/right/clipped。ID0合法；None仅启动无请求且PCM为零。来自公开采纳观察，绝不在适配层从result/commit推导。 |
| calendar | B2_FRAME_LEDGER_V1：每笔epoch/request_id/accept_cycle及commit_cycle或cancel_cycle。这是B1独立期望的显式测试视图，不能从CSV反生成。桥只核身份、清理和期限，不重复B1四声/lane/事件算法。 |
| oracle | B2_EXTERNAL_PCM_ORACLE_V1：epoch/request_id/L/R/clip及同basis。只核输入一致和运输，M1继续拥有DDS/ADSR/混音/效果数学；本轮只有明确标识的手算运输夹具，无真实M1 Pro黄金。 |

固定复用D3的decoder()依赖门禁，加载已pin SHA da91462e8421719e09ffab60d7bbe38d4ee05ac1793ea70e1f09c7a69ccda0cb的PinDecoder/quantize/parse_json。没有复制解码核心；其冻结64 BCLK/立体声、每半槽32位末16位LSBJ、WS低右/高左、PCM24加128再右移8饱和、pre-NBA帧相位等合同，必须等M2确认与真实Pro一致。

桥仅在独立观察的frame_tick后给PinDecoder设置已观察TX选中元组，保留原采样沿。请求接受/commit/cancel/reset与独立账本核同，严格<833拍且在下一真实帧前清理；commit当沿不能cancel，取消后不能提交/采样。完整stereo、复位截断和观察尾UNKNOWN分开，HOLD重放不算新提交。未观测完整串行尾不补签。

**明确兼容限制**：本入口要求binding声明unused_fields_policy=ALL_COLUMNS_KNOWN_FAIL_CLOSED，并拒所有列中的X/Z，严于原monitor“控制/实际使用数据已知”的规则。遇闲置字段X保留原件并拒收，不补0；如真实Pro允许闲置X，应另经最小兼容修订。当前视图没有直接消费B1的HOLD/startup/finish记录语义，B1→此视图的真实归一化仍PENDING，不据选中元组自动推断hold。

观察末拍只与CSV末行比对，是声明窗口而非finish/MONITOR_END验证。真实完整捕获须由B1绑定成功退出、未超时收据、唯一MONITOR_END及真实finish/END原件；本包不会把恰好EOF写成完整成功。所有结构成功输出仍pro_dut_pass/PCM_algorithm_pass/physical_48k_PT8211_pass/board_release_allowed=false。
