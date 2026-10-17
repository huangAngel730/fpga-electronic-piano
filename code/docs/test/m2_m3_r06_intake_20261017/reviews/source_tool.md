# M2 限定只读复核：M3-R6-1 / M3-R6-4

范围：用户本批外包 `M3_R06_EVIDENCE_BUNDLE_20261017.zip` 与本机 Git 对象 `ffc8b4cc94606cdd70941d2abaee8bbd93a654c5` 中两包源码。没有阅读 d53fcd4 新增范围，没有运行任何被审程序、CLI、测试、HDL、EDA 或设备。仅在本 output 目录保存 Git 原字节、解包原件和 SHA/CRC 核验脚本及结论。没有修改正式源、M3 源、M2 C4 十项本地成果或共享状态。

## 结论

- R6-1 可按 L1 纯文件工具历史和 L0 真实原包词法装配接受，不能签 source closure READY。冻结 69 项列表没有 `dds_oscillator`，但不能直接追加整份原文件；会新增重复定义 `sine_wavetable_1024`。
- R6-4 原七类软件用例及三个固定 Python 进程历史可接受 L1；安全执行器采纳为 REWORK_REQUIRED。`audit` / `run-fixture` 未重验 assemble 的固定 argv 和输出等约束，手工变更 plan 后自算 SHA 可绕过固定 worker 限定。未执行反例。
- 两包均不构成 RTL 仿真、Pro 物理、板测或实际执行准入，`board_release_allowed=false` 保持。

## R6-1 原件核同和历史

生产 `audit.py` SHA `b6b4415c365ca3f5040d2b769fa8b1187c1faf2cc86b67582c71c5810d602cd3` 与 RUN_02/frozen 完全一致。配置、run_once、两个测试文件也逐字节一致。

- RUN_01 原 audit SHA `a0a95f0dd7436593f92fe581cab9835dceeb00263b1c3fdd6335d536499937e2`；15 个软件例全通过，exit 0，1.328 秒。真实装配出现词法误报，首轮原件保留；不能转称最终版已跑原 15 例。
- RUN_02 唯一定向修复：7 个新例通过、exit 0、0.843 秒。修改紧贴位宽的端口解析、宏端口 PENDING、function 错认实例、参数 ROM 默认路径；没有重跑原 15 例。
- 本次核验 RUN_01 338 个、RUN_02 122 个收据产物，大小/SHA 全一致；两个纯 Python 子进程，HDL 0。嵌套 ZIP 472 成员、CRC 正常，SHA `2616fe325821ad5e9ca6762d8c32177abaab15f0c887d01f6c0cce90a9296697`。
- RUN_02 实际结果 70 单元、72 模块、82 词法实例；唯一 errors 为 `MISSING_MODULE:dds_oscillator`。宏/generate/动态 ROM/参数尚未 elaboration，物理身份 PENDING；config 的 candidates 为空，尚未装入新 M2 C3/C4 或后续 M1 出口。

## 正式 source list 的具体风险与最小建议

冻结 ZIP SHA 为 `931b7d2bbfd7ac056707542931101ff844b125936762748e344536d9be6c1ba2`，原 `source_closure/inputs/compile.f` SHA `99279bbab257786467495ba95ee311b969ed72f94ffe458e1e935a5f29bfd2bb`。

1. `sources/polyphonic_envelope_bank.sv:130` 的 `g_sine` 分支实例化 `dds_oscillator`。原列表没有 `sources/dds_oscillator.sv`，但同版原字节已在 ZIP，2746 字节，SHA `9588637c20348c7df8eda5ab5bca780de4468aec607fc9d4b918df63f746c556`。
2. 原列表第 45 行已列 `sources/m1td_dds_oscillator.sv`，SHA `b6e7ab7e33442fd288ea95c407a76033b822e7b4ffdf3fab791429629b26308b`。其第 45 行仍定义无前缀的 `sine_wavetable_1024`；缺列文件第 45 行也定义同名模块。两个 `module sine_wavetable_1024` 起至 EOF 的原字节完全相同，尾段 SHA `4b1d526758efd05c2780d24b8116bc3660620aa98f639b3a2813e633c17d216f`。
3. **不能将整份 `dds_oscillator.sv` 直接补入列表**。这会让已列 ROM 模块重复定义，产生新的装配阻断；不能用编译顺序或不同文件名解决模块同名。
4. 推荐 M2 冻结新的模拟装配差异：保留原 ZIP/69 列表，增加一个新派生源，其内容只取同版缺列原文件开头至首个 `endmodule`，保留 `dds_oscillator` 顶层并引用现有同字节 `sine_wavetable_1024`。不动算法/ROM 数学，也不覆盖旧冻结源。若按“前 1240 字节 + 单个 LF”精确派生，所得 1241 字节 SHA 为 `303e3a9927e743d4149ceae4bb8754ebb8abdfb14638d407254b8e555dfcd3bd`；本轮仅计算身份，未写候选源或 list。
5. 新装配须把派生规则/原件 SHA/新文件 SHA/唯一模块检查纳入 binding；原 69+wrapper 的 70 单元基础上加此单元为 71。M2 新 observer 替换列表也需显式纳入，不能继承旧 C3 装配计数或旧测试结果。最终含 TB 的闭包以新精确 manifest 为准。

上面是源清单建议，不是 HDL 执行许可；M2 也可选择经证实的顶层可达性裁剪旧模块闭包。当前词法工具遍历所有列出模块、不展开 generate，因此本轮不能证明实际已选择 top 会因未列 DDS 编译失败；但直接补全文件会引入同名 ROM 的事实已确定。

## R6-4 具体阻断：消费端没有执行固定 worker 限定

文件：`code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tool_plan_adapter/plan_adapter.py`，SHA `bb29b19984c75a49a102b3481dff6d53403af14bb5671fffb9db587dd6cbbbcc`（与已测嵌套原件同字节）。

- `normalize_spec:131–202` 在 assemble 时检查 exact argv（169–171）、路径范围及 timeout。
- `audit:209–232` 只检来稿 plan SHA、schema/approved/status、spec 文件身份、input 文件身份及 argv[0] 与 executable 一致；没有验证 plan 等于从绑定 spec 重新生成的规范化计划，也没有重验 worker argv / timeout / cwd / 输出与 marker 范围。
- `run_fixture:263–318` 只再检查 mode、fixture_authority，就取 plan 的 output/marker/argv 并 Popen。
- 最小静态反例：以合法 fixture plan 为基础，保持原 spec/inputs/argv[0]/schema/approved=false/authority，改 argv[1:] 为另一个 Python 入口（如仅用于说明的 `-c pass`），选新的 output/marker，自算新 plan SHA 传给 `--sha256`。当前 audit 所有条件都仍满足，随后会调用改过的 argv。这已违反“只能固定 worker”；不需要 `approved=true`，正常 REAL_TOOL_REQUEST 拒绝用例也覆盖不到此路径。无需实际运行证明控制流。

最小修法：在 audit / run-fixture 的消费端，以绑定 spec 原件重新执行同一纯校验规范化函数，并比较 plan 全部安全相关字段；同时在 Popen 前再次断言固定 executable/argv/cwd、输出/marker范围、timeout 和 worker/helper身份。caller 提供的 SHA 只做内容一致性，不当权限。保留原七例和消费记录；只在有效修复额度内新增上述“改 plan 但自算 SHA”的定向拒例，不重跑旧组，不恢复真实工具权限。

## Windows Job 边界

原三次固定 worker（无子孙、固定各三行）收据确认 job_attached=true，root_exit=0/7/0、timed_out=false、输入同 SHA；双流及事件文件 SHA/大小全部核同。七类软件历史为 exit0、2.203 秒、3 次 worker、0 次真实工具。嵌套 ZIP 76 成员、CRC 正常，SHA `1a501d76271f1751722de464b7c0eedd223d76d4595f7fe98290a5b8182b3d7c`。README/RESULT 发布文本只按声明删尾 LF，生产 Python 未变更。

安全器仍不能据此升级：正常 root.wait 返回后先 join 读流线程，Job 到 finally 才 close；若孙进程保留 pipe 可触发线程未结束，再 close Job 后未 join/quiescence 就 hash 日志。若子进程先关双流再继续工作，则根 exit0 可以先设置 PASS，cleanup 只记录 KILL_ON_JOB_CLOSE 意图，未核整棵树退出。日志 readline 无总字节/单行上限，线程异常也未统一回传为失败。这些不是本轮七例观察到的失败，固定 worker 未创建孙进程，报告也明确未覆盖 timeout/tree/overflow；因此仅列为 M2 采纳真实执行器前的未验/需实现项，不声称已验证安全树生命周期。

## 核验入口

- `outer_inventory.json`：外包实际目录与 SHA。
- `commit/`：19 项 ffc8b4c 精确 Git 原字节。
- `outer/source_target_audit/`、`outer/tool_plan_adapter/`：原包/原 RUN 文件和嵌套解包。
- `materials_summary.json`：SHA、生产/冻结对照、实际收据摘要。
- `verified_originals.json`：338+122 产物 SHA、三原进程双流、ZIP CRC 与共享 ROM 尾段比对结果。

本报告是内部只读辅助，最终 M2 准入与 source list 决定由集成主窗口登记；没有代签整包或通知 M3 真人。
