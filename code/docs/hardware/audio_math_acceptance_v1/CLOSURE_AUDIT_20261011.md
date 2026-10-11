# T060 剩余缺口收口：两个诊断计数独立补核

M3，2026-10-11。仅D043 A授权区域；不编辑旧checker、原capture、RTL、ROM、TB、生产工程或八共享表。
这是限定源码审计L0／软件L1，不重新签声音数学L3，不关闭T060/T061。

## 本次实际补齐

旧报告把5个F END计数统一列为不可观测。本次重新逐项分析后发现两项已有充分输入，
新增`closure_audit.py`独立核验，**不修改旧报告、封存或原始收据**：

- `full_pop_push`：冻结FIFO深度32，无空队列同拍直通，P为真实入队握手、E为真实出队握手。
  按同拍pre-NBA队列深度判断是否满pop+push，再先弹旧head、后入新word；逐字校验队列内容、
  拒空pop/溢出/同拍多握手。R清队列，但TB累计计数不清零。
- `edge_events`：原TB在同一capture过程先记录E并比较`cycle-last_frame_cycle<64`，后记录K
  并更新last_frame_cycle。严格保留此顺序，R把last_frame_cycle清0；**不是**把同沿K先更新，
  也不是把窗宽误作`<=64`。计数根据E/K原时序得出，不用END作期望生成器。

最终运行`code/output/m3_t060_closure_20261011_02/receipt.json`退出0、1.359秒，4步骤；
实现开发的首轮1.438秒记录保留，不拿它替代最终新增源码锚点后的运行。
本次两个独立重算值为1／19，与END对应字段一致；FIFO峰值32，68入队／68出队、末尾为空。
新checker只针对上述两个计数和双文件运输一致性，旧主入口保持原状。
需要使用本次补核结论时必须同时执行新入口，不能把旧parser单独运行描述为已新增检查。

12项合成软件测试覆盖63/64边界、E/K同沿旧值、复位累计、满pop+push旧head、非直通、
溢出/重复握手/错payload、重叠窗口边界及fixture不反填。两个新完整反例仅分别将END的
full_pop_push／edge_events加1，原交易和JSONL不变；指定非零诊断为
`CLOSURE_END_FULL_POP_PUSH`／`CLOSURE_END_EDGE_EVENTS`，不是截断、缺文件或超时。
这些是Python模型与输入反例，不是新RTL行为变异。

## 原件与来源

原JSONL raw SHA `d17cf87952ac0c663e681e0b47051e9412af4a2979fb509aaa5d7114d5b32cc5`；
原F raw SHA `bd0035de464cb8c757c7e29a132073181e9e8179aa8303ab1ec110c6990042d6`。
audit模式必须匹配原始身份，check模式可检查新反例但不为其授予原capture身份。
TB与H冻结FIFO按旧manifest内6f3e813 LF身份核对；输出列出具体源码路径、行号和SHA。
当前capture2真实生成TB／observer来源已有M2确认，不重复索要或重跑。

旧ROUTER载体、container、绑定receipt均核SHA后只读引用；该receipt中的PCM、退休及其他
模型统计属于**旧执行结果重用**，本轮未再执行原路由／包络／声音数学回放。
旧退休日志没有计数键，结合旧已签报告只说明原轨迹未覆盖退休，不当作本轮独立退休验证。

## 最小剩余清单（交M2决定，不是新增执行授权）

| 缺口 | 当前事实 | 最小补证或排除决定 |
|---|---|---|
| 真实retirement／panic | 原E无type5；旧签收轨迹无退休，合成模型测试不代真实capture | M2决定是否补同源释放→Idle→回收→重分配及已接受panic；保留generation/身份/占用/触发、R/E/K/J及声音输出。复位清槽不算退休 |
| frame/math重叠 | 现oracle明确报`ROUTER_OVERLAPPING_FRAME_MATH_UNCOVERED`；当前Q到Q+20筛查无重叠 | 先明确所需取消/非回滚合同，再决定最小补capture及参考FSM范围；零命中筛查不证明通用无重叠或实现正确 |
| END control_stalls | E只记录接受，无法表示未接受的FIFO head控制类型与停顿每拍 | 连续valid/ready/head event_type+control_id及复位沿，或M2排除该TB诊断计数 |
| END center_samples | H可见，但center_compare精确使能变化未记录 | 记录center_compare精确变化沿并绑定H；T场景标志不代使能沿，或M2排除 |
| END checks | check任务包括逐拍、过程与#1后调用，稀疏音频轨迹不包含全部调用 | M2排除TB自检调用次数，或提供每次调用记录；不硬编码原6228000 |
| 两条fixture flag | epoch1/cycle1744211/request2094与cycle1745045/request2095，观测均1、独立期望仍null | 精确fixture_select变化沿和采样region，或M2排除flag数学验收；不从M flag或PCM反填 |

本阶段将原5项未重算END细化为2项已补核、3项仍未知；未修改旧主入口的PARTIAL／退出3。
完整数学范围是否排除诊断、是否需要最小补capture及其执行权限均归M2；本轮不生成新TB、
不启动原RTL或Gowin，不碰设备，不借T061的N32数据代替T060冻结四声部覆盖。

## 复现与交接

仓库根目录，用已有Python3.11：

```text
python -B -X utf8 code/software/audio_math_acceptance_candidate/closure_run.py --bundle-root <原M2_V0208反馈包根目录> --output code/output/全新目录
```

总300秒／每步90秒，正常退出0仅表示本专项完成，`t060_complete=false`；缺输入/源漂移失败。
同一对象生成audit.json，含剩余清单、源码锚点、原输入及历史结果身份；原命令/stdout/stderr/
退出码/elapsed和受保护输入前后SHA另有receipt。只写新输出，拒覆盖。

封存正常恢复及4项篡改拒收另有日志：载体损坏、缺成员、重签完整通过假收据、重签损坏audit。
首封存`CLOSURE_20261011`保留；最终封存`CLOSURE_20261011_02`使用同一次1.359秒审计，
只补交付文档/封存与转发工具，不冒称再次跑原模型或RTL。
发布沿用普通develop与真实九门禁；最终提交／远端状态见转发包GIT_DELIVERY，不倒填旧收据。
八共享表按任务单禁写，由M2统一登记。B2K已新获V0280限定签收，B2L仍待专项复核；
N32/R1资源工程与实际综合额度仍由M2准备，本次无综合/PnR/STA或设备操作。

给M2（待用户转发，尚未送达）：本次T060两个END诊断已独立补核、其余最小缺口见上表。
请决定诊断字段排除范围及真实退休/panic/重叠是否最小补采；本包不作为重跑原RTL的许可。
