# R8-03 消费端纯校验准备

状态：PREPARED_NOT_RUN。本窗口不运行候选；总控统一消费 S 组。旧 R6-4 的 25 例及原件保持冻结，新增七例只核本 facade 的新边界。

入口为同名 software 目录的 `m3r08_03.py --request REQUEST.json --output NEW_OUTPUT_DIR`；当前只记录入口，不授权执行。selftest 提供无副作用导入及 `run_case(case_id, output_dir)`。参数输出目录必须不存在。

请求包含 schema=M3_R08_GUARD_REQUEST_V1、validation_root、spec/plan 文件身份及 requested_action=VALIDATE_ONLY。validation_root 限本项 docs/test 或总控独占目录。返回完整规范计划、逐字段 audit、纯 AST 提取收据；permission 恒 NOT_GRANTED，process_route 恒 ABSENT。

为避免旧 adapter 顶层 ctypes 初始化，按固定原 SHA 选取原 normalize/rebuild/audit 函数及其必需常量、标准库导入，函数 AST 不改写；原件和每个函数 AST SHA、源码行号、派生 AST/source SHA 均进入机器产物。只重定位纯证据域；worker、解释器/DLL、cwd 及输入约束保留。不是任意执行计划的准入器。

`R6_4_MINIMAL_INTEGRATION.diff` 是新增独立 validate-only 调用入口的完整提案，尚未应用，旧 consumer 和 adapter 字节不变。禁止直接改被固定 SHA 的旧 consumer 后继续使用原 pin；后续集成若需改原文件，须保留原件并由责任方重新冻结精确版本。该补丁不会把验证成功接到 Job/worker/Popen；真实执行仍需独立准入。

CLI 通用退出码：ACCEPT=0、PENDING_UNKNOWN=3、REJECT=2。ACTUAL/INPUT 与机器产物只能证明其报告的静态或合成范围。当前未验证 Python 执行、进程生命周期、HDL、EDA 或硬件。
