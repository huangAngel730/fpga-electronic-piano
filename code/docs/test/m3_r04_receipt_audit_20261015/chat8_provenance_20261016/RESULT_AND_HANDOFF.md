# chat8 RESUME_R02 A/C 来源核账结果

日期：2026-10-16。主对话5按白天总控分工，只读核夜间 A 生产者与 C 消费者的来源、工具、命令、双流、消费标记和 SHA 绑定；没有审 PCM 数学，没有运行 ModelSim／Icarus／Gowin／硬件，也没有修改 A/C 原件。审核员制度未启用。

## 结论

结果为 `PROVENANCE_BYTE_CHAIN_CONSISTENT_LIMITED`：现存 A/C 原件在字节、命令和消费关系上闭合，未发现互相矛盾的 SHA、命令、退出码、沿数或结果绑定。正确等级是 **L0 静态身份＋软件核验（6 例通过），未执行 HDL L1**；它不是第三方执行认证，也不代替 M2 最终复核。原 `RUN_02` 结果误写软件核验为 L1，按 `LEVEL_AMENDMENT.md` 更正，原件不覆写。

### A 生产者

- `RUN_01/RUN_RECEIPT.json`：83197 bytes，SHA-256 `1516a35e6a5852164866aa729f8897ca5a668a4308f8e1ce60e91fa994211dbc`；记录基线 `c12636c034be62e10c564217298564422a533b9c`，该对象在本仓库可解析为 commit。
- 25 份运行源码、90 份 staged 输入和 23 份工具／安装身份在回执前后相等，实际现存字节也逐项匹配。动态加载依赖仍按原回执为 `UNKNOWN_NOT_MEASURED`。
- 三次工具探测的 6 份流和 vlib／vlog／vsim 三个功能步骤的 6 份流都实际存在且 SHA 匹配；功能三步均创建进程、退出 0、未超时。vlog／vsim 显示 ModelSim SE-64 2020.4；功能日志为 `Errors: 0`，vsim 含精确 `PASS M2_M1TD_REAL_CHAIN_BOARD_FUNCTIONAL_ONLY`。
- `RUN_01_CONSUMED.json` 的 round=1、输出目录、授权及 preflight 身份正确；其 pid=1976 与首个 vlib 功能进程 created_pid 相同，证明额度在首次功能进程创建时标记消费。
- `REAL_CAPTURE.jsonl` SHA-256 `a2509a2b5555437ff8ee1da4799e8210ad80e95a058881a5d26111a935e5b5d3`，逐行严格 JSON 核得 253456 个连续 TICK、HEADER/END 各一；`REAL_INPUTS.jsonl` SHA-256 `d001cac94d1520c42b43bcb33ca079c2f1d815c1205deb4a2d87005fe143038b`，同样是 253456 个连续 TICK。
- A 封存 ZIP SHA-256 `e0e1d77840c353256bbbea18178a198367f234a19bc86f3cbe3fde2688938645`，161 个 manifest payload 逐成员大小／SHA／CRC 匹配，另有 manifest 本身，共 162 项。

### C 消费者

- `CONSUME_R01/RUN_RECEIPT.json` SHA-256 `273bb3b1ccd566b2992d7d4ea7727e195878c705c9d5208dfbae51797f958deb`；命令参数精确绑定上述 A 回执 SHA、startup boundary 与 schema，执行类型为 software-only，EDA 调用 0，耗时 8.094 秒、退出 0、未超时。
- C 六份执行源码前后 SHA 相等，实际字节匹配；stdout SHA `d04f33d8b549ba33dea52be0041009b93b3f9924aeaad057c3c434dd2ae64d65`，stderr 为空文件 SHA `e3b0c442…b855`。
- `REAL_RESULT.json` SHA-256 `ec8e03710c18ce6eda50cece7689578bd2ec58bbbddb212b87b68866621eaf98`；其 producer receipt SHA、capture SHA 与 A 精确相等，消费沿数也是 253456。夜间总回执和 C 封存 manifest 均绑定该结果。
- C 封存 ZIP SHA-256 `e894e81afa9fae37b71b52c245a11cfbe1fc4c617720728d23bc6acbf7952dd9`，235 个 manifest payload 逐成员大小／SHA／CRC 匹配，另有 manifest 本身，共 236 项。

## 具体证据边界与最小修法

1. A 的消费标记在首个 vlib 进程创建时生成，正确绑定 pid、输出目录、preflight 和授权，但不可能同时绑定稍后形成的最终 `RUN_RECEIPT.json` SHA。现有最终回执、C 输入和封存包共同补上完成态关联，但消费标记本身不是完成回执。后续若要加强，只在新后继追加不可覆盖的 finalized receipt，写入消费标记、最终回执、六流及 capture SHA；不要改旧标记。
2. C 的子进程 `RUN_RECEIPT.json` 绑定命令、源码和 stdout/stderr，没有直接记录子进程生成的 `REAL_RESULT.json` SHA；结果由随后形成的 `NIGHT_RUN_RECEIPT.json` 和封存 manifest 精确绑定。后续 runner 可在子进程结束后把结果身份直接写入最终运行回执，旧原件保持只读。
3. ModelSim 可执行文件、安装元数据和一组静态库身份已记录，但实际动态加载 DLL 集未测。若 M2 要求更强工具溯源，应在未来获准执行中记录已加载模块清单及 SHA；当前只能保留 UNKNOWN。
4. 回执、manifest 和消费标记均由同一执行链自行生成。此次独立核账证实它们彼此及实际文件字节一致，却不能单靠这些自报材料证明历史进程一定真实发生。要升级为独立执行认证，需要 M2 对精确输入作独立运行或提供受信执行环境签名；不能靠重写旧 manifest 补证。
5. first-valid、启动初始化、clip 数学端点、四个独立频率、模拟链和板级结果均不在本核账范围，继续保持 UNKNOWN／未验，`board_release_allowed=false`。

## 本窗口软件验证

固定入口 `run_provenance.py` 的最终运行是 `RUN_02`：6 项软件测试通过；真实只读核账退出 0；核账前后本窗口源码与九个 A/C 保护原件身份完全相同。`RUN_02/RUN_RECEIPT.json` SHA-256 `cfec99220f1081ac33751b4735cc9166c393ca94b3a05db04be485f4647be53d`，最终结果 SHA-256 `ad45d1b1bb6e3b58f0a296dd15d3a1cbe2bd6cc254568f9692c76e58b6d88e27`。

首次测试因系统沙盒临时目录不可写退出 1；首次真实核验因 A/C 封存收据分别使用 `package`／`archive` 字段而在读取 A 时退出 1。两次均保留于 `FAILURE_HISTORY.md`，修法只涉及本窗口测试路径和既有字段适配，未改原件或放宽 SHA／执行判据。

## 交总控／M2

建议总控把本结论并入统一交接：A→C 的现存字节链、六流、253456 沿及精确消费绑定可以按上述限定范围接收；四项证据结构缺口和五项业务未验边界必须保留，不把“内部一致”写成“独立认证真实执行”或完整 R05／板级通过。

本窗口没有 Git 写操作；提交、门禁和发布仍由白天总控统一处理。给真人 M2 的材料待用户转发，尚未送达。

## 2026-10-16 写集增量修订

后续复核发现 `test_provenance.py` 原临时目录实际解析到仓库根的 `output/m3_r04_chat8_provenance_test_tmp_20261016`，越出本任务两个授权目录；原文把它描述为 `code/output/...` 也不准确。该真实目录现存且为空，按要求未删除或移动。测试临时目录现已改到本窗口软件写集内，并增加解析后路径越界拒绝守卫；AST 与一次路径正负例定向检查通过。没有重跑原 6 例或 A/C 核账，`RUN_01`／`RUN_02` 与 A/C 原件保持不变。完整偏差、命令和退出码见 `WRITE_SET_AMENDMENT.md`。
