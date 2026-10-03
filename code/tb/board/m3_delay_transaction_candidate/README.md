# G：隔离 T028 单 PCM24 事务候选

只实现 `m3_delay_transaction_adapter`，不接生产链路、不改原
`code/rtl/audio/delay_effect.sv`。接口见 M2 G/H/I JSON 合同。
所有逻辑在 50 MHz clk；rst_n 异步断言，调用方同步释放。
DEPTH 默认 1024，测试 16/1024；位宽、PCM24、unsigned Q0.15 参数不变。

请求握手 E 直接产生原算法的一次 sample_enable，同时保存 id 和所有参数。
原算法 E+2 NBA 给 raw valid，适配器在 E+3 NBA 锁存并公开 result_valid；
最早 E+4 消费，连续成功请求通常相隔 5 拍。取消排空后最短可相隔 4 拍。
没有流水容量或 FIFO，不支持结果消费和新请求同拍。
结果在背压中保持 id/PCM/valid，取消是明确例外。

cancel 当拍屏蔽请求和结果握手、取消 held；若旧计算未给 valid，则排空后
才恢复 ready。接受过的样本即使取消仍在 E+2 写一次历史；不回滚历史、
不清回声。rst_n 才清逻辑历史/输出。delay=0 读上一整 DEPTH 圈，不是旁路。
这些取消和吞吐取舍是候选合同，正式采用仍由 M2 审查。

```powershell
python -X utf8 code/scripts/run_m3_delay_transaction_candidate.py
.\code\scripts\check_repo.ps1
```

真实 ModelSim 编译原算法和候选，两深度各逐拍比对：request/result
valid-ready、id/PCM、单次发样本、E+2 raw valid、真实缓存写地址/值。
独立 Python 整数递推：分别 floor(product/32768)，相加再 PCM24 饱和；
不导入 M1 数学模型。覆盖持续 valid、live 参数变化、背压、id 回绕、
五种取消时点/取消同拍请求、流水及脏历史复位、delay0/1/depth-1、反馈饱和。
统计 accepted=consumed+cancelled+reset_drops，复位边界不跨 epoch 检查发起间隔。
三个 scratch 反例实际编译运行后由对应断言拒收：重复 sample_enable、
id 破坏、忽略取消；不是靠编译错误或 timeout。空/截断/X capture 拒收。

2026-10-04 实际 L2/L3：16 深度 6287 拍 / 1106 接受，1024 深度 20767 拍 /
3757 接受，合计 27054 拍 / 4863 接受；三行为反例有效。
最终命令、计数、源 SHA 和完整日志以 `code/output/m3_G_release_20261004/evidence.json`
为准。未做 G 综合/PnR/整机 STA/上板/无爆音验收。
共享状态/编号表按本任务排除范围不改，由 M2 登记；交接待用户转发，尚未送达。
