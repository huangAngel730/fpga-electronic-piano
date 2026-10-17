# C9 B19 大伴随流转换

本包为 task-day4、夜间任务3的独占后继，**READY / L0，NOT_RUN**。仅新增后继，不改旧c9_binding。总控统一执行新软件组；成员未导入/编译/运行候选。

convert_files(csv_path, output_dir, max_input_bytes=16GiB, max_output_bytes=64GiB, max_line_bytes=4096)逐行读取原cycle,time_ps加固定19字段CSV，返回artifacts.diagnostic_rows/report。输入可为路径或描述符，输出新目录必须位于仓库内。

逐行保留物理行号、原CSV整行（包括X/Z与行尾）、原输入SHA、nullable值/原因、同seq多阶段、实际config_take的62位拆包及三路clip。kind3/4/8有效原因哨兵约束维持；无效不造输入事件。时间/cycle连续；不推断epoch、独立apply_event_seq或audio_stable。该流只作伴随诊断，不生产canonical74或FRAME_PLAN。

输入限额16GiB、输出限额64GiB，均可向下调；单行默认4096、可设128..65536字节。无64MiB整窗上限。被解析原字节增量SHA和大小比对，再做读后身份核同。失败保留DIAGNOSTIC_ROWS.jsonl部分与FAILURE.json。

selftest.run_case(id, output_dir)定义3个新例，见tb/board同名c9_completion_r01/CASES.json：总控执行时实际流式生成>64MiB+4096的CSV及最后X行，验证同seq双阶段/config/clip/末物理行/原行；另测截断末行和输出预算失败保留。大文件当前尚未生成或运行，不能将用例定义当成实测通过。原C9 B13仍按原manifest由总控精确选择。

CLI：companions.py --csv <file> --output <new-dir> [--max-input-bytes N] [--max-output-bytes N]。完成诊断转换仍保留独立映射PENDING，返回3；拒收保留原件并抛出。CLI不授予执行权。

源码与依赖SHA见DEPENDENCIES、FILE_SHA、READY；固定common和旧COMPANION_WIDTHS按源码字节读取，不用pyc。只读自审未发现本范围具体阻断，未执行测试。实际等级仅L0，real_pass/board_release_allowed始终false，真实同输入双路HDL/STAT/串行/数学与硬件验证仍待。未暂存/提交/推送，由总控统一处理。
