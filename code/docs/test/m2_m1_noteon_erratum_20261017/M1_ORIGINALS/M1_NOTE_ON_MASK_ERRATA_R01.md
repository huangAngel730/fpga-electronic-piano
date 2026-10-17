# M1 对 M2 第20批 note_on_mask 时序勘误的确认

M1 确认原 `字段语义_R06.json:338` 中 “Allocation commit happened on the preceding edge” 不正确。原文件、四份 RTL、原封包与已签 19 项测试全部保留；本后继只修订 `note_on_mask.definition` 的文字定义。

原封包 SHA256：`019d50298c171b4359c7882a092f11f5b582033a8d81cb318f22b817a6c3e287`。原语义文件 SHA256：`11b037b2c0ed57683bf56413b8caced025d8468cde29406ff2e932376be484bc`。本次依据为本地冻结源静态阅读，等级 L0；没有新增软件测试组、HDL 编译/仿真、EDA 或板测。

## 确认后的时序定义

采样口径仍是 `posedge clk / pre-NBA`，位宽 4、无符号、`CONSUMED_NOTE_ON_PULSE` 与全部既有字段、端口不变。

- E 是 `ALLOC_APPLY && slot_valid` 成功沿。该沿 NBA 更新 lane 的 source/channel/note/generation，并令状态进入 `CTRL_ON`；该沿不产生 Note On 消费。
- H 是 E 之后第一个 `CTRL_ON && cmd_ready` 成功握手沿，最早 H=E+1。该沿 NBA 才把 `slot_note_on[target_slot]` 置 1。
- 若中间没有复位取消，消费沿 C=H+1，最早 C=E+2。C 沿 pre-NBA 采到注册脉冲，voice 与 ADSR 的 Note On 输入在该沿消费；随后默认清零。
- `CTRL_ON` 背压推迟 H 和 C，不能写成固定的 E+1 或固定延迟。复位可能中止交易，不能从 allocation 单独推定一定发生消费。
- Note On 脉冲不等于 `sample_tick` / `advance_mask`，不额外声称 DDS 相位复位；音频推进沿和原算法保持原定义。

下面是由源码推导的边沿例子，**不是新仿真结果**：

| 场景 | allocation E | CTRL_ON 握手 H | Note On 消费 C |
| --- | --- | --- | --- |
| 无背压 | 100 | 101 | 102 |
| 101、102 沿 cmd_ready=0 | 100 | 103 | 104 |
| H 前复位 | 100 | 无成功握手 | 不保证消费 |

无背压时，101 沿 pre-NBA 仍见脉冲 0，101 沿 NBA 后置 1；102 沿 pre-NBA 才见 1。所谓“前一沿”只适用于握手 H 相对消费 C，不能用于 allocation E 相对 C。

## 可核出处

- [router 冻结源](inputs/router.sv)：129 行默认清零；156–163 行 allocation 与身份/世代提交、转 CTRL_ON；165 行握手注册脉冲；215、232 行消费观察。
- [bank 冻结源](inputs/bank.sv)：69 行直接导出脉冲；167、171 行直接送 voice/ADSR。
- [原语义 JSON](inputs/original_semantics.json)：338 行错误原句保留。
- [带 SHA 前置条件的单字段补丁](NOTE_ON_MASK_ERRATA_R01.json)：仅替换 `/fields/4/definition`。采用时先核原文件完整 SHA，并生成新的后继版本；不要回写原文件或原 ZIP。

## 给 M2 / M3 的接手说明

请把本确认与原语义文件一起引用，在后继定义中采用该单字段勘误。M3 的独立事件日历按真实 H/C 消费沿关联 lane 与 generation；不得由 allocation 固定加一推算，也不能把内部 router seq 当独立 plan seq。

本确认没有重验 C9。M2 转发称 C9 为 67 口/74 字段、config 62 位位段已接受、clip 分开、独立 plan seq 仍 PENDING；这些仅记录为 M2 已报告状态，不冒称 M1 独立核过新 C9。R6-2/3 继续等待真实同版输入，`board_release_allowed=false`。

## 到件与发布边界

已收到 [M2/20 原消息](inputs/m2_forward_original.md)。Git 远端引用本轮成功更新到 `30d4591ce4e8c8551c4a14c7990e1de7aff2a2a1`，当前 M1 任务单与 R07 已取得；7 个所需 blob（含 M2 详细勘误、C9 复核文件、最新总览和看板）未取回。指定对象下载先遇 DNS 失败，DNS 恢复后再次请求遇低速超时；无全局网络配置更改。M2 提供的 D:\17 外包路径在本机不存在，SHA `60fd5d6e440b18e4657cb4bdcd3e00913108fde371151d7fc4af40b5884d4b60` 尚未由 M1 复验。

本后继只在本地交付目录形成，未写入原 Git 工作树、未暂存/提交/推送；缺发布前置文件，不执行新精确树九门禁，也不把 M2 的 V0399 9/9 当作本后继门禁。原 q 工作树已有内容和未发布提交保持原样。完整来源、读取失败、原包及静态核对结果在 ZIP 中。

待用户转发，尚未送达。
