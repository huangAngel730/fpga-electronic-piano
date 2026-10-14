# T061 N32-C 压力与恢复候选

本目录只准备 N32-C 的独立输入、严格事务账本、capture 检查器和行为反例。
当前没有运行 lower、compile、RTL 仿真、Gowin 或设备操作，也不宣称 C 已通过。

## 当前边界

- 任务表指定的原路径
  `code/build/138k_polyphony_resource/prepared/N32_R1_20261011_01/`
  在本机缺失，且从未进入 Git。
- 只读别名
  `code/rtl/common/polyphony_scaling_candidate/b2c_voice_allocator.sv`
  的 SHA-256 为
  `9fec9f838a9ef333d01d1b79ecf77d137e41bc0c5e78a40d2820c37739506061`，
  与任务表指定原件逐字节身份一致；这是一条显式映射，不表示原目录存在。
- 真实 C 组合验证必须等待 N32-B 的精确 Review-Key、Fingerprint、源码闭包、
  公开端口合同和 PASS 证据。不得从活动工作树猜测 B 身份。
- `expected_skeleton.jsonl` 的 PCM/clipped 状态固定为
  `WAIT_B_FROZEN_MATH`，因此正式 checker 会 fail closed；只有绑定冻结独立数学后
  才能生成可执行的 expected ledger。

## 数据合同

`generate_plan.py` 生成 v3 合同：

- `plan.jsonl`：固定输入计划；覆盖 32 槽、33号窃取、快速/Release重触发、
  跨 source/channel 同音、CC64 四槽 `await_release_done` 观察/空闲读回/重新分配、
  经真实 64 位 event 发送的 pitch bend/modulation/pitch range 控制变化、
  READ/HOLD、取消、复位和高密度事件。`release_done` 只允许观察真实后端输出，
  不得作为 C 驱动端口；控制也只允许经真实 64 位 event 输入。
- `expected_skeleton.jsonl`：从输入和本目录独立状态规则按原计划时序生成的事件与
  事务账本，不再按记录类型重排。
  每个事务使用 `(reset_lifetime, accept_serial)` 唯一标识。
- `receipt.json`：仅说明软件计划生成结果；RTL 保持 `NOT_RUN_WAIT_B`。

未来 B/C observer 必须在每个真实时钟沿的 `PRE_NBA_PUBLIC_PORTS` 相位写一条
`CYCLE`（`t061-n32c-capture-v3`）：完整计划索引、reset lifetime、
cancel/reset、event/sample/result/read 的
驱动和握手，control snapshot/control release/backend release_done 的观察值，
`audio_state/router_state/publish/aborted/idle/fault`，以及 32 个公开槽身份/状态快照。
检查器按单一时间线重放，直接从这些沿导出 EVENT/ACCEPT/HOLD/
RESULT/READ；不接受先分类再拼接的事后账本。`END` 必须独立统计并覆盖完整正文 SHA。

事件是多拍路由事务：输入握手后必须等真实 `router_state` 返回稳定 IDLE，再推进
下一计划并比较最终槽状态；不得把握手沿等同于槽状态提交沿。cancel 后的 DRAIN
同样必须由真实 `idle` 结束，checker 不会因为软件账本为空就制造 idle。异步复位
沿要求 `aborted=0/abort_reason=0`，reset lifetime 从实际断言边界递增。

正式检查拒收缺数据、零比较、超时、END 自述不一致、丢失/重复事务、错身份、
错 result ID、左右 PCM 错接/错拍、clipped 损坏，以及 cancel/reset 后陈旧发布。

## 当前可运行的软件自检

```powershell
python -X utf8 .\code\software\t061_n32_stress_plan_candidate_20261013\selftest.py
python -X utf8 .\code\software\t061_n32_stress_plan_candidate_20261013\generate_plan.py --output .\code\output\<new-unique-dir>
```

`selftest.py` 的 PCM 只是明确标记的 `SELFTEST_FIXTURE_ONLY`，用于证明当前 WAIT_B
软件合同和检查器骨架
能接受完整正例并拒收二十一类完整反例，含结果先于接受、READ移出请求窗口、
同沿伪响应、HOLD不连续/不稳定、cancel未驱动、cancel/reset 后陈旧结果、
错槽身份/错窃取对象；它不是 DUT capture、
不是音频黄金结果。B 草案接口仍未封存，因此此 PASS 不能升级为 RTL 验证。

## 后续实际 C 运行前置

1. B 精确版本通过并冻结；显式证明新 allocator 已绑定，不能误链接同名旧模块。
2. 将 B 源、ROM、include、独立数学、外部工具及 SHA 写入新的机器可读 manifest；
   正式 checker 同时读取并验 SHA 的独立双审 approval 文件和 run receipt，核对
   Review-Key/Fingerprint/PASS evidence、命令/cwd/日志/预算/尝试次数及前后闭包。
   expected 或 manifest 内的字符串自述不能自行解除门禁。
3. 同一不可变快照同时交审核员和预审员核对。
4. 单工具最多 300 秒、runner 总计最多 900 秒；每步一次，失败立即停止，
   不重试、不换工具、不换机器、不加时。
5. 新输出目录拒绝覆盖；保存 stdout/stderr、退出码、前后 SHA 和未验证项。

综合、PnR、STA、正式接入、串口、下载、烧录和实物均不在本目录授权内。
