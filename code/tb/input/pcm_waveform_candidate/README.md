# 独立验收结构

`reference.py`逐项校验原L基线56输入载体SHA，按raw_manifest解码正常5849和诊断41条A记录，
保留signed24十进制左右/sample_seq=adoption_index-1；不使用请求ID/S串行记录替代。
真实normal全流逐条回放，synthetic定向向量独立标识，不拼长诊断流或重新运行原音频RTL。

`tb_waveform.sv`实际编译/运行DUT，通过公开口以完整2048整数数组、pending/front快照参考，
每周期检查mask/RGB固定2拍、trace_valid/gap/drop；不读取DUT私有银行/层级。
8个完整800×525扫描含3360000像素，第8帧关闭覆盖；另外定向矩形逐像素扫描。
诊断短流不应发布，极值/尖峰四位置/不足2048/重复与丢序号/回绕/restart优先/复位/
背靠背包/停止输入/禁止中途换图/待发布替换/同沿发布与完成均覆盖。

日志capture记录公开输入R/T/I/V、完整每行800像素的32位滚动摘要和END计数。
Python独立由公开输入重建快照，复算4200行全部像素摘要，且与封存normal/diagnostic逐包比对。
RTL TB逐像素比较是主要证据，摘要用于离线独立重算，不把摘要无碰撞当数学证明。
正例必须TB零错误、Python零错误，空/截断/错误END/非法周期/垃圾记录非零拒收。

两行为变异只生成于新忽略output：反向signed映射、pending立即换front（撕裂）。
全部完整编译和8帧运行后再由外部checker按特定PIXEL_REFERENCE/STATE_REFERENCE拒收。
不能以编译失败、$fatal或超时算行为反例通过。

首次attempt1为TB signed/unsigned表达式上下文和checker诊断计数问题；attempt2正例通过，
坏周期字段原checker漏查；已补严格周期校验。失败输出保留，不改原日志。最终attempt3另存。

本阶段没有40→25 CDC实现、真实UART/FPGA整机、模拟音频、HDMI实屏或设备编程。
