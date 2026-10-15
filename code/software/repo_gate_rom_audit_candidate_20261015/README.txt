独立 ROM 依赖闭包与严格门禁入口

范围
本目录新增严格入口，不修改正式 check_repo.ps1、run_t007_sim.ps1、
run_t025_top_stat.py、GPRJ、DUT、TB 或原 ROM。不替代 M2 最终复核。
支持原三顶层 tb_electronic_piano_top、tb_key_to_tone、
tb_midi_top_integration。结果仅限隔离自检仿真；不是 Gowin 资源、
布局布线、STA 或实体上板/发声通过。

操作顺序（仓库根目录，Python 3.11+）
1. 主操作窗口用 freeze_expected.py 明确冻结独立 expected.json。
   freeze 是显式一次性操作；prepare/verify 从不更新期望值。
   不得在拒收后不经定位便重新 freeze 来掩盖不同 ROM/源码/工具。
2. python -X utf8 code/software/repo_gate_rom_audit_candidate_20261015/rom_gate.py prepare
     --repo <仓库绝对路径> --tool-root D:/Gowin/oss-cad-suite
     --expected <独立冻结expected.json绝对路径>
     --output <仓库>/code/output/repo_gate_rom_audit_<全新独占名称>
     --top tb_key_to_tone
3. python -X utf8 code/software/repo_gate_rom_audit_candidate_20261015/rom_gate.py verify
     --config <全新输出目录>/config.json
   prepare/verify 均为零 HDL 工具调用，检查原件 SHA、闭包、命令和环境绑定。
4. 确认本次执行在有效任务授权内，再执行：
   python -X utf8 code/software/repo_gate_rom_audit_candidate_20261015/rom_gate.py run
     --config <全新输出目录>/config.json
   Windows 私有 Job 监督每个子进程树；不运行旧 .vvp，不执行批处理环境脚本，
   不读取进程继承 PATH，而是显式构造已冻结 PATH/IVERILOG_ROOT 和系统路径。

预算与失败处理
每个 top 独立总限 300 秒，包括预检、lower、compile、simulate 和后验。
原 allocator 的 Yosys read_slang lower 只是原入口兼容转换，不作资源验收。
lower/compile 分别最多 90 秒，simulate 使用总预算剩余量（预留后验收据时间）。
任何阶段失败/超时/错误日志即停止，不重试、不提高预算、不更换工具。
consumed.json 原子独占创建；同目录二次执行拒收。旧产物仅留 SHA，永不续跑。
receipt.json 记录实际 argv/cwd/显式环境、逐阶段退出/超时/秒数、日志 SHA、
实际调用次数、源码/工具前后 SHA、产物 SHA 和最终 runner_exit。

严格日志独立审计
python -X utf8 code/software/repo_gate_rom_audit_candidate_20261015/rom_gate.py audit
  --stdout <原stdout.log> --stderr <原stderr.log> --exit-code <实际退出码>
  --pass-token "PASS tb_key_to_tone checks="
必须退出 0、存在指定顶层 PASS、随后有 Icarus $finish called 行、日志尾完整，
且 stdout/stderr 都没有 ERROR/FATAL/[FAIL]/readmem 短表或多表等诊断。
--no-finish 仅供诊断，不能代表正式模拟完成；run 不使用此选项。
命令成功退出 0，实际拒收退出 1，参数/原件/配置异常退出 2。

ROM 路径合同详见 FACTS.txt 和每份 config.json 的 rom_contract。
include 闭包仅从 GPRJ enabled 源及三个 TB 的实际 literal include 递归解析，
不把忽略的历史实验头文件当必要依赖；查找为 stage cwd、-Iboard、-Icommon，
动态/缺件/越root/循环/同名歧义拒收，config 保留父子映射图供独立核验。
测试及实际验证范围以本批次主窗口封存收据为准；本说明不预写实测通过。
