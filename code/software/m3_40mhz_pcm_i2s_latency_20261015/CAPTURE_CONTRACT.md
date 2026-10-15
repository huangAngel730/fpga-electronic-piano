# C_PCM_SERIAL_PUBLIC_V1

这是新隔离模块诊断夹具合同，不是已存在的R05采集格式。严格ASCII，每个sys_clk正沿一行**pre-NBA**公共端口值，无层级寄存器／DUT汇总反填。header：

```text
C_PCM_SERIAL_PUBLIC_V1,NEW_MODULE_RTL_FIXTURE,40000000,PRE_NBA,PT8211_LSBJ
```

固定23列：`cycle,epoch,rst_n,tick,frame_tick,request,req_id,pcm_valid,pcm_ready,pcm_id,left,right,clip,pending,play_l,play_r,frames,requests,commits,underflow,bclk,ws,din`。所有列十进制整数，flag严格0/1；PCM严格signed24，ID与计数unsigned32；尾行`END,<总沿数>`，尾后无记录。cycle由1连续递增，不跨reset回绕；epoch初始0、复位释放1/2，寿命不拼接。

- `request/req_id`为原buffer公开输出，request处于frame_tick之后一沿。
- 接受定义`pcm_valid && pcm_ready`；首次valid不是接受。原buffer的ready严格包含当前ID／无pending／非frame_tick。pending/held映射独立逐沿核对，不以仅valid更新账本。
- `clip`为本夹具生产者附加诊断元数据，原buffer/i2s_tx没有clip公开输出；不得将字段存在解释为真实R05clip已验。
- frame_tick取消未提交旧ID，旧结果不能新接受；已成功提交的样本可held重复播放，不能算新发布。
- 采用PT8211 LSBJ：WS低右高左，各半帧32个BCLK上升沿，最后16位MSB→LSB有效、前16位零填充。同步后由WS物理翻转划分；复位部分半帧丢弃，首次完整frame前的完整半帧只能为零。
- checker对本诊断计划要求两个寿命、每寿命至少60间隔，833/834都出现，累计周期偏差≤约1拍；故意欠载只限两次、旧ID与HOLD覆盖限本夹具。

**真实轨迹接入条件**：来源须由真实R05 observer和exact source/tool SHA证明，另给输入记录（MIDI/事件输入沿）、接受/取消/发布身份，映射此公开端口及实际reset边沿。现有R05仅END/PASS没有这些轨迹；当前checker默认fixture黄金日历，不能把真实log改header伪装诊断夹具，也不能把软件预测字段补成实测。真正真实A后继需要独立适配入口，去掉仅诊断场景计数的同时保留严格结构／身份／时序，并对缺观察列UNKNOWN；本次尚未实现或执行该真实适配。没有同一时基模拟输出，≤10ms模拟指标始终UNKNOWN。
