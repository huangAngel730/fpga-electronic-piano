# N32-D 时钟与工程合同静态守卫

仅做 L0/L1 软件／静态预检，不调用编译、RTL 仿真、综合、布局布线或 STA。
`PASS_PREPARE_ONLY_NO_TOOL_EXECUTION` 只表示精确工程身份和约束传递正确；
实际资源仍为 `UNKNOWN`，STA 为 `NOT_RUN`，完整 T061 不关闭。

## 验证范围

- 固定 A 功能、B 声音以及 C **分段**功能／数学封存 SHA；不把 C 写成连续单次通过。
- 从固定 B 实际执行计划导出 18 份业务 HDL、2 个 include 和 5 个 ROM 的原字节身份。
  不把仿真观察 shell、变异宏、厂商仿真模型或 testbench 加入综合源列表。
- GPRJ 完整启用源顺序及唯一 SDC，与 Tcl 指定工程、顶层和 include 路径一致。
- SDC 只接受 40 MHz／25.000 ns、Setup 1.000 ns、Hold 0.650 ns。
  删除时钟、降低防护、加入 false-path／multicycle 或换错顶层即拒收，即便重新签 SHA。
- 工具与机器身份可读核对；缺工具可形成准备结果，但必须明确 `tool_ready=false`。
  `tool_ready=true` 也不是执行许可。当前 `authorized=false`，没有执行子进程入口。
- 八项关键工具身份与固定旧工具参考收据逐项相同；工具根下 `IDE/bin/**` 和
  `IDE/data/device/GW5AST-138C/**` 的成员集及全部文件 SHA 必须与静态库存一致。
  删除库存、缩小范围、漏 DLL、篡改文件或更换关键工具后重签均拒收；此检查不证明
  实际动态加载、许可证或工具执行成功。
  工具库存还固定 1201 份文件的无路径根摘要，非主要 DLL 与库存／manifest 同时恶意重签
  也不能通过；更换工具版本或库存必须形成新的明确审定身份，不能自行重建后冒旧版。
- 拒收旧资源／时序报告混入工程及把综合默认 100 MHz 冒充实际物理 40 MHz STA。

## 使用

```powershell
python -B code/software/t061_clock_contract_guard_candidate_20261013/clock_guard.py --project <精确新工程> --manifest-sha <SHA256> --output <工程外的新收据.json>
python -B -m unittest discover -s code/software/t061_clock_contract_guard_candidate_20261013 -v
```

输出已有时拒覆盖。守卫不会运行项目内的 Tcl。

自检中的项目、工具字节及替代信任锚点明确为 `SOFTWARE_ONLY`：
它们只用于检验锁闭及指定软件拒收，不能用作真实工具、仿真、资源或 STA 证据。
真实工程集成必须使用守卫固定的原 A／B／C／B-plan 信任锚点。

旧源码、旧失败、原 A／B／C 证据不改。正式综合、资源准入、接入和新整机 STA 由 M2 决定。
