# R6-4 消费端定向返修交付

状态：**L1_TARGETED_CONSUMER_FIX_READY / M2_REVIEW_PENDING**。当前明确授权的候选实现、定向验证和原件封存齐备；不是完整真实工具安全执行器通过，Pro仍PARTIAL，board_release_allowed=false。基线/当前HEAD为40d78131e8ed50643dd169816f7bfc7149a8ced9。

仅新增原tool_plan_adapter的software/docs `r07_fix/`，另在R7-A docs新增`c5_static_binding/`。原adapter、worker、旧七类/RUN_01、失败/历史原ZIP及A原源码/测试/封存ZIP均未覆盖；未Git写入、未跑门禁、未改共享状态，发布由总控串行汇合。

## 具体修复

消费入口`consumer.py`同时要求独立pinned spec路径/SHA及plan路径/SHA；重建规范化spec→plan，按类型保持的JSON逐字段比较全部字段，未知字段也拒绝。重算plan SHA不能替换spec或获得权限。consumer限定固定Python/DLL、原worker、原helper/adapter、夹具三类输入、候选cwd/输出根；真实工具模式直接关闭。

Popen紧前再次重建、全字段比较，检查实际argv/kwargs、固定身份、空独占输出和本进程消费声明。原adapter只在内存接候选DOCS/audit/代理，不改原文件。此候选只签本次plan消费端缺陷；M2采用时须选新入口和独立spec pin，不能沿用旧audit入口称问题已消失。

## 真实消费与结果

先核原RESULT、GROUP_RECEIPT、共享PACKAGE_STATUS、dependency_audit和M2复核，确认初组已消费1、原修复组未消费；身份本体见CONSUMPTION_AUDIT/READ_ONLY_ORIGINALS。新RUN_SPEC SHA为`3ceb47b0f1a980c8a30ffab548d41d6410b53c0606b3507f35f910949263c10d`。原R06唯一≤60秒修复组现在消费1，剩余0；不借R7-A额度，无重试。

实际外层命令（cwd仓库根）：

```powershell
& 'C:/Users/songdongkuan/miniconda3/python.exe' -s -B code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tool_plan_adapter/r07_fix/run_once.py
```

受监督实际selftest argv/cwd/PID及原双流SHA见RUN_01/PROCESS.json。UTC 2026-10-17T11:34:58.483990至11:35:06.840642（北京时间19:34:58至19:35:06），exit0，stderr空，无timeout/log overflow/error。父组连同执行后核验**9.062999999994645秒≤60秒**，前后各932身份无漂移。

**25个新定向案例：1正向控制、24负例；另2个真实CLI拒绝exit2。** 19种篡改覆盖argv参数/worker/Python、cwd、output、marker、timeout、inputs/helper/spec/runtime身份、unknown字段、mode/approved/status/authority/tool_kind/route/fixed_cwd；每份篡改plan均重算SHA，在audit及consume都拒绝且无输出/marker。另核独立spec也改写、三个Popen实际参数及初审后晚篡改。正向控制新增确认重建/紧前guard比较字段齐套，实际只启动原固定worker一次。

旧七类重跑0，真实工具/HDL/EDA/设备0。进程内负例报告拒绝码，不冒称24次独立退出码；两个CLI保存真正命令、双流、PID、UTC、耗时、exit2。晚篡改预期产生FAIL_PARTIAL/PLAN_SHA_MISMATCH，其原计划/变异计划和失败收据均保留；无意外失败。首组前自审修正晚篡改原件保留与复制冻结一致性，未用第二修复组。

## 限界与接手

- M2只需复核本候选、精确版本及新反例，决定消费端入口采纳；本窗口不代签最终复核。
- 未扩大或证明原Windows Job的孙树/timeout/溢出/异常清退能力，未测试真实工具；仍不得作为真实ModelSim/Gowin执行器使用。
- A对C5仅静态绑定：71源9ROM加3个既有采集源=74源/9ROM/76字面module，字面重名0。新增原件在A的c5_static_binding，组合ZIP SHA `2906dd137d821de49ec2674386997ef6d4dec5a99ca3a6f826f5a2d1f2a89b4f`。A原ZIP SHA仍`d24d8cb47ce589a3337c945e25bafb2f7f9b6e3112380179c7494fdf115e8dcf`，A新增软件组0、HDL0。
- C5并非编译/elaboration/等价或Pro物理结果；M2继续冻结真实工具/时钟模型/6个窗口参数及首次明确组合准入。M1语义、真实capture/finish、独立FRAME_PLAN/尾端核验和板测仍待。

原件入口：本目录RECEIPT、RUN_SPEC、RUN_01原双流和逐例结果、FILELIST/SHA清单及R6_4_R07_FIX_ORIGINALS_20261017.zip；同版C5组合ZIP也收录。未提交、未推送；给M2真人交接为“待用户转发，尚未送达”。给夜间总控仅完成后一次回传，平台拒绝则留独立通信回执、不再尝试。
