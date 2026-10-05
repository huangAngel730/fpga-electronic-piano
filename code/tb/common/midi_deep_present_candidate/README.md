# MIDI深流水与事件呈现隔离候选

只在test目录实验，不替换生产parser/top，不改变FIFO容量、ROM、ADSR、时钟或引脚。原FIFO头复制到呈现寄存器，但只在真实外部握手时出队；背压下不得撤回。控制可服务且达到burst1/8/16上限时先预留，不呈现下一离散头。

仲裁E锁有效mask和RR，E+1四组各8槽选局部前四，E+2合并前四，E+3锁event。计算期间最多3次单槽update，记录前两次+当前拍，从四旧候选与3新更新做7候选修正，取消/新插入保持锁定时live RR优先，最后读取最新payload。所有pending都取消时不发事件；仍有稳定pending时无需全局epoch重试。单在途，II/valid有空拍，本候选不宣称和原逐拍等价。

运行入口：

```powershell
python -X utf8 code/scripts/run_midi_deep_present_candidate.py --output code/output/<new-module-dir>
python -X utf8 code/scripts/run_midi_deep_present_pcm.py --functional code/output/<new-module-dir>/functional.json --output code/output/<new-pcm-dir>
```

模块oracle对真实字节decode比较原parser，再独立维护FIFO和liveRR/Mod去重/latest/cooldown状态；测试夹具强制decoded event只用于比UART更快的取消/锁定同拍压力，不称真实UART。burst1/8/16正常自检、真实50MHz两次50000clk发送间隔、18592前四snapshot、自检空/短输入和四可编译行为反例。初始50MHz完整重复场景300s超时保留，改为实际50000clk专用3发送检查，没有缩短真实interval。初始只检查最终发出会漏掉两候选fallback故障，补首轮livepending必须锁定断言；错误版非零退出才算最终通过。

PCM入口复用F原testbench、原V0171冻结音频银行/路由/47源manifest，唯一功能替换是parser+新增selector；不沿用上一新增audio阶段。最终physical必须门禁PASS并查完整STA；模块通过不代表PnR/上板。
