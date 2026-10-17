# d53fcd4 补充提交：限定内容溯源

基线 `ffc8b4cc94606cdd70941d2abaee8bbd93a654c5`，目标 `d53fcd42488141f8711173f1b20df14361f19b49`，共 3520 文件。只通过 Git 对象、现有 ZIP 原件及本次 R06/R05 附件做内容身份核对；没有运行其中的 Python/RTL/EDA/硬件，没有修改源码/共享文档或 C4 文件。

## 可以复用的有据范围

`CONTENT_REUSE_AUDIT.json` 保存 3520 项的 SHA、长度、最多四个可定位原件出处、严格字节/CRLF→LF 变换标记及未决名单。

3423 项内容在以下已签历史原件或当前已核附件中命中：

- 已签 M3 两个历史总原件包，及其内 C/C2、D/D2、E1–E4 等嵌套原件；
- 已签五窗口总包及 B1/B2/E1/硬件资料等嵌套原件；
- 精确已签 `414e1a9` Git 中 `M3_PRO_PASSIVE_MONITOR_ORIGINALS_20261017.zip`，补核其中 187 项；
- 本轮 R06 证据包、此前 R05 reconciled 交接附件。

这是**载荷内容身份复用**，原验证结论仍受旧报告的来源、精确版本与等级限制；本轮 R06 载荷仍按本轮各包结论，不因展开自动获硬件/真实输入签收。SHA 命中未被当成对错误路径、伪来源声明或每个新发布收据的额外功能验收。

唯一位于 docs 外的新增文件为：

`code/tb/board/m3_pro_fourvoice_trace_20261016/pro_binding_20261017/README.md`

大小 394，SHA `b6e3b68bcae09fcff8495c4d1b4a22a572e272df98ed5b4ab00512dbae800454`，与已签五窗口包内 B1 原 ZIP 的相同路径逐字节一致。其余 3519 项位于 docs 中，但本次按内容核验，未按目录直接签收。

本次路径范围中没有新生产 `code/rtl`、`code/software`、`code/scripts` 或构建入口；docs 中有历史执行源码与测试快照，它们仍是证据文件，不据此执行。

## 未决 97 项，不升级为全部复用通过

未在所用原件载荷索引中命中的范围：

| 范围 | 项数 |
| --- | ---: |
| E1 `pro_integrate_successor_20261017` | 12 |
| E1 `pro_parallel_20261016` 的 task2 协调发布/交接 | 13 |
| D 的协调发布、R05 回执、日间边界与 monitor 交接/门禁 | 29 |
| B1 `pro_binding_20261017` 的摄取快照、日间 M1 第18批、来源和发布说明 | 36 |
| B2 日间 M1 第18批和封存回执 | 4 |
| E2 communication/seal launch/seal receipt | 3 |

其中 10 项扩展名为 Python/SV/Gowin 工程/CST，包括 E1 的 `INPUT_ORIGINALS/current_board_shell.sv`、`current_project.gprj`、`pro_cst_candidate.cst`，B1 `intake_20261017/INPUT_ORIGINALS` 中 4 件 HDL/TB/仿真模型，以及 3 个历史发布辅助 Python。完整路径与 SHA 在 JSON 的 `unmatched` 数组中。

这些项没有新生产入口修改，但不能仅凭“快照/收据”名称代签来源。M2 若要把补充提交整体标为已复核，还需核此 97 项与已签封存路径/INPUT_IDENTITIES 的对应关系，特别是 7 件 HDL/工程/约束快照的原 SHA，以及新展开的发布与 M1 第18批说明的适用版本。当前结论允许保存这些远端历史文件，不把未决范围纳入新的功能结论或执行准入。

## 工具边界

只有原件读取、SHA、ZIP 解包读取与 Git cat-file/show；未重跑旧测试。一次补充搜索用 cmd.exe 管道因引号解析失败、退出 255，未产生修改，已向父窗口说明；随后改用本窗口 Python pathlib 做只读归档清单。整个审查只写本输出目录。
