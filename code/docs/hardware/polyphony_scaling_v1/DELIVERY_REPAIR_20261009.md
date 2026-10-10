# M2 回执返修交付：T061 B0 软件边界

本轮针对 `CallBack/M2_B0_REVIEW.md` 的最小软件问题，不是完整 B1/B2 或 T060 收口。
原 B0_20261009、原三阶段证据、M2 回执、生产源/ROM/公共接口/共享表不回填、不修改。
修改和新增文件均在 D043/D044 新 B 软件、指定 runner、hardware 文档路径。

## 实现

- `inventory.py`：N 必须是严格 int 且为4/8/16/32；4.0 可控 ValueError，不再 AttributeError。
- `protocol_oracle.py`：构造、replace、pedal、全部 Tag 字段先严格类型/范围检查。
  bool/float 不能利用 Python 与整数的相等关系冒充身份；非法结果明确返回 False，状态不变。
- 显式排空合同：调用者必须传正整数 drain_limit。已 issue 的 cancel/reset/commit 都隔离旧工作，
  同步收到 ROM/engine/result 三路 empty 确认前禁止 begin/换身份/踏板更新。
  超时锁闭、取消和局部 reset 不延期或绕过，32位回绕同样必须先排空。
- `test_candidate.py`：40项 unittest，含 N4/8/16/32、取消各完成点、换身份/回绕/复位、
  三路 empty 分别未就绪、非法确认、超时锁闭、正常合法全槽提交等。
- `review_regression.py`：原封读取 Git41d2871 的旧两源，在内存编译后复现8组 M2 问题；
  同组检查在修版全部满足。两个内存 Python 变异分别由 strict_tag_types 和 cancel_same_request 指定拒收。
  历史 probe 的 exit0 表示“缺陷按预期复现”，不是旧代码正确；两个变异按合同返回 exit2。
  这些均不能代替要求的两项可编译 RTL 行为反例。
- runner：保存上述实际命令/原 stdout-stderr/退出码/耗时/SHA，补 post-wait 的 elapsed 限时检查。
  即使子进程最终 exit0，返回时超过分配限时也不签 PASS。封存工具用真实 exit0 子进程及注入时钟
  演示901>900被指定拒收，不实际等待901秒。

## 真实证据及首轮处置

首轮 `code/output/m3_t061_b0_repair_20261009_01/`：40自检、8组修版probe及九门禁实际通过，
但门禁步骤 elapsed=1293.484s 超过900s，旧版 runner 只检查 wait 超时，最终错误输出 scope PASS。
**该轮不作合规终验**。原 receipt/原日志保持，`repair_checks.json` 单列失效原因及原 SHA，
不通过手改旧 status、elapsed 或日志消除此事实。

资格终验只使用全新 `code/output/m3_t061_b0_repair_20261009_02/receipt.json`：
封存工具要求 scope PASS/exit0、九门禁通过、每命令实际耗时不超过单步限额、总体不超过1800s，
全部执行源、原日志、56冻结输入、旧封存和8共享文件前后 SHA 一致。具体实际耗时见收据。
运行期间无候选源变更；封存后再核全部 bound file SHA，避免把后改源码冒充已测源码。
新终验总耗时169.530s，仓库门禁165.219s（实际精度以原receipt为准），均在规定范围。
首轮封存的相对/绝对路径处理错误另记 SEAL_FAILURE_20261009.md，旧不完整目录保持，
最终载体只使用 REPAIR_20261009_02，不把首轮封存失败计作行为负例。

旧 B0 内层 ZIP 543209 bytes / 279 members / SHA
`3c7d63eddfed73423faf6cd39c9504af75eb73a846b2698566fa6b64bda0bc6e` 逐 member 再核通过。
原最终 B0 与本轮预算 JSON 逐对象完全相同，仍为117/205/381/733条件拍数；不是新排空的已证成本。
原冻结清单三份特定 CRLF-ROM 内存恢复规则保持，不编辑原ROM。

## 不能扩大解释的边界

新 empty 是**环境保证输入**：确认以前的所有工作/重复结果此后不能再出现，不是暂时 valid=0。
若外部谎报 empty 后仍送完全相同的旧 Tag，新旧无法分辨；测试明确演示此限制，
不是宣称无条件 ABA 安全。B1 必须实际实现/证明阻止新issue、旧返回消费/丢弃、有限排空、
每阶段 reset/recovery、端口/II/latency/冲突及至少两项可编译 RTL 反例。
测试 drain_limit=8或2并非硬件实测上界，不能塞进生产833拍预算。
真实 fence、事件排队/CC64扫描/backpressure服务上界和新控制成本仍 UNKNOWN。
不以超时锁死证明 MIDI 服务有界；ADSR持续流水/ROM预取/LFO非回滚仍待 B1/B2。

T060：M2已确认0/1观察分类与生成TB/observer来源；三个旧包络漏检和同源PCM反例已由A2闭合，
本轮不重复旧音频/波形/桌面压力。尚缺 E/RESET/真实采样/独立release_done 驱动的四声部
router/allocator/CC64/retirement参考层，不能把观测N/Q/off反喂期望。
两个精确off边沿的可观测性、5项END计数、2条fixture标志继续明确限制，必要补采由M2另定。
该后续实现不因本轮 T061 软件问题修好而算完成，完整 T060/T061 均保持未关闭。

本轮等级仅新软件 L0/L1；九门禁中的原 T007/T019 RTL 仿真不是新 B1 RTL 验证。
无Gowin/综合/PnR/STA/设备/安装/串口/烧录/接线操作，一次模块综合额度未使用。
共享状态/任务/验证/决策表因本单禁止而保持，由M2复核后统一登记。

## 复现与转发

仓库根目录，已有Python3.11，不安装依赖；每次指定新目录：

```powershell
python -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --output code/output/m3_t061_b0_repair_reproduce_NEW --repo-gates
python -B -X utf8 code/docs/hardware/polyphony_scaling_v1/seal_repair.py --package code/docs/hardware/polyphony_scaling_v1/REPAIR_20261009_02 --verify
```

转发 `M2_HANDOFF_REPAIR_20261009.md` 和 `M3_T061_B0_REPAIR_20261009.zip`。
ZIP含新源/合同/原日志/两轮收据/manifest/封存检查；Base64载体可校验并解码，旧包不重复打大包。
本轮未提交、未推送，收据 HEAD3a0f28c只是开工基线，不是返修提交号。
通知待用户私发M2，尚未送达。上传后另行说明真实提交号，不回改本交付的历史身份。
