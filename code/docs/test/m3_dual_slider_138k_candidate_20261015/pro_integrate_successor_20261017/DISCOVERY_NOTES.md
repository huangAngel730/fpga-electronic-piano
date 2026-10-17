# 静态读取边界与原件说明

read_thread已核总控userMessage 01a14797-672a-7462-a629-9845497d8ee2的1–5通信/自审授权，只读总控用于核授权，没有读取审核员或其它实现窗口。

42个具名输入原字节按INPUT_SPEC.json冻结，105项范围库存见DISCOVERY_INVENTORY.json。原件复制耗时约0.4s，命令退出0，没有编译仿真或软件功能自测，未消费验证轮。FREEZE_RECEIPT_ORIGINAL.json/freeze.stdout保留初始元数据；原脚本把可复现的pwsh -File写作argv，已在FREEZE_RECEIPT.json澄清为实际shell命令及脚本SHA，原件/原输出未删除。该复制脚本没有启动外部进程。

一次资料定位组合命令退出1：`rg -n 'frame_start|H_TOTAL|V_TOTAL|H_ACTIVE|V_ACTIVE|rst_n' code/rtl/hdmi/video_scan_timing.sv code/rtl/input/visualizer/visual_score_tracker.sv`，前一个猜测路径不存在（os error 3）；后一个文件有结果。另同组给rg传`.../REWORK_WATCHDOG_RUN_02/*.json`字面路径，Windows报os error123。未据错误路径得出源码事实，也没有重复失败命令凑次数；改用`rg --files code/rtl/board code/rtl/common code/rtl/input`定位真实scanner为code/rtl/common/video_scan_timing.sv，已原字节冻结。实际源锚仅引用真实文件，不引用猜测路径。资料定位错误不是RTL坏例、不是验证失败消费，也不是任何PASS。

旧L2 zip本体只在本地冻结保留，按总控最新收尾要求不入最终新zip/发布清单，仅引用原文件位置；其SHA/129成员/CRC与历史收据仅作来源一致性核查，不重跑487/4或软件几何审计。历史DELIVERY的未提交标志保留原样，不回填今天状态。当前新静态包的提交/推送由总控另行处理。

本轮只需docs/test新目录，未创建空RTL/TB目录、未复制RTL做新仿真，输入副本只属于证据封存。旧50MHz当前外壳/40MHz封存外壳之间的差异是现场版本差异，不自动把任一方称为缺陷或替其修复。新Pro闭包未到，源/ROM/top/trace、producer与物理/实屏缺项保持UNKNOWN。
