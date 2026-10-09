# T060 原 capture2 输入缺口（待用户转发，尚未送达）

任务依据：D043 分工单、任务提交 `6f3e813`。
组件验收当次本机 HEAD 为 `3f5672d`，已包含任务提交；本轮未执行 fetch／pull／merge 或编辑共享文件。
已读取 D044 的成果优先收缩决定，仍只实现当前冻结版，不建历史兼容框架。
所读 H40 数学源与任务提交未见差异，新 runner 已逐文件校验身份。

本机指定目录 `code/output/platform_preparation_20261005/capture2/` 不存在。
已在当前仓库输出／证据和用户给出的 CallBack 资料中查找；只找到旧 50 MHz F-only
采集及 M2 原检查日志，未取得本单要求的原双文件。部分旧输出目录读取被拒，
不声称已穷尽扫描整块磁盘。

请 M2 转发以下原字节资料（或告知本机已有位置）：

1. `audio_observation.jsonl`，raw SHA256：
   `d17cf87952ac0c663e681e0b47051e9412af4a2979fb509aaa5d7114d5b32cc5`。
2. `midi_pcm.capture`，raw SHA256：
   `bd0035de464cb8c757c7e29a132073181e9e8179aa8303ab1ec110c6990042d6`。
3. 同次 capture2 的生成 TB、observer、实际 sources／7 ROM 清单、来源和原 SHA。
4. V0236 使用的完整 56 反例原输入及清单／变异规则，能绑定每例具体改动。

可直接提供已有 `M1_40MHz实际样本捕获补充包_20261005.zip`，已登记：
526003 bytes，16 members，SHA256
`65a05c853f212e3e45ce799c4d60320fdd0dfe39414b2be9115cceaa9a7b1eae`；
56 反例若不在该 ZIP 内需另补。

上述 SHA／计数依据仓库 `code/docs/evidence/platform_preparation_20261005.json`，
不是 M3 重新生成的输入。旧证据保留，不要求重跑 RTL 来替换正例。
当前仅完成解析／DDS 算术组件与合成单元测试，真实 A1 尚未完成，T060／T061 均未关闭。
收到输入后仍须接通独立接受事件、控制快照和 LFO 时间线，不能只凭双文件运输相等签收。
