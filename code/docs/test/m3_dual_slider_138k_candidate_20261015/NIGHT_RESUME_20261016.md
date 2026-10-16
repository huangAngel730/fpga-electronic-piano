# 2026-10-16 夜间恢复（新的实际运行前）

当前HEAD `8b64a352464932a28df565038cafc8d623dea5c9`。
完整读取两份已发布夜间任务单，D最多两组不同源码SHA，单工具<=300秒、全包实际仿真<=900秒。
本runner继续采用更严90秒/工具、300秒/组，至多两组，未恢复任何旧专项。

只读直接核总控源对话 `01a0a0c6-5875-7432-940f-2e184e3a9c05`：
human消息 `01a1404e-fb8b-7b70-afe8-7a6597f42bf0` 明确：
“请继续 我刚刚中断了你 主对话2 主对话4的任务 请你继续开始”。
最初四包及子代理授权消息 `01a13fe0-dcad-74c3-ab15-5a8334a5b8fd` 同次只读核到。
仓库夜间已给定权限允许D隔离模块仿真；不等于平台自动接受跨线程权限。

恢复时无run_*目录，无创建保留/消费标记；Get-Process iverilog/vvp无记录，
过去两次均明确CreateProcess前拒绝，因此本任务旧真实工具调用0、回归组0。
Get-CimInstance在受限环境不能访问CIM，不能把该诊断失败写成“完整进程树核验通过”。
未杀任何进程、未代跑、未换壳/解释器/普通权限绕过。

运行前增量修runner：每组不可覆写PREFLIGHT、创建保留/实际启动标记、
异常中断保守计数组数、相同源码拒绝重试、版本原始双流、NIGHT_RUN_RECEIPT。
源RTL/TB不变；旧L0封包继续保留原SHA。
核新直接恢复授权及已发布夜间任务单后，只请求一次正式审批；若再次拒绝，停止执行并封L0原件。

## 新审批已批准；首次新预检自身缺陷（0工具）

run_night_01 的 Python 入口真实退出1；before/after identity相同。
首个 iverilog_version 进程创建参数求值时 `subprocess.CREATE_SUSPENDED` 不存在，
抛 AttributeError，Popen未调用；receipt process_created=false，所有Icarus/VVP调用0。
TOOL_CREATE_RESERVED只是提前保留，不是实际消费；下次按明确未创建收据排除，不重置任何真实组。
原RESULT/NIGHT_RUN_RECEIPT错误写固定L2标签是runner元数据缺陷，不是L2证据；真实等级仍L0。
仅修runner常量为Windows CREATE_SUSPENDED=0x00000004及无有效仿真时的等级标签；
旧run_night_01全部保留，新目录新SHA，非相同源码盲重试。

## run_night_02 首个真实工具组失败（已消费1组）

iverilog -V 创建并退出0，但stderr含无法获取ivl版本；随后vvp -V实际退出3221225595 / 0xC000007B，
stdout/stderr为空，首失败立即停止，compile及运行产物调用0。该组确有2次工具启动，计消费1组。
source/tool前后SHA一致，不把版本命令成功当编译或仿真。

只读定位原仓库 enter_fpga_env.ps1 明确要求 oss-cad-suite/bin 和 oss-cad-suite/lib 同时加入PATH。
本新runner误只加入bin，导致需要的lib目录未绑定，继承PATH还有其他MinGW/32位目录。
缺失lib是可确认的runner环境缺陷；0xC000007B与不匹配DLL相符，但未证明某个DLL唯一根因。
第二个且最后的真实工具组仅修runner的局部环境：bin;lib;System32;Windows，加入lib直属依赖文件SHA，
同一Icarus/VVP EXE和全部旧源不改、不安装、不修改系统PATH。另新目录/新runnerSHA、同90/300限制。
若第二组任何失败，停止，不能使用第三组；不恢复已消费版本工具组。

## run_night_03 第二且最后真实工具组

同一版本及EXE字节，加入正确局部lib闭包后，iverilog -V=0、vvp -V=0、compile=0。
随后positive运行本次新编译产物，退出1，t=0 FATAL invalid visual_scene_renderer parameters。
原renderer要求 JUDGE_Y < KEYBOARD_TOP < SCREEN_HEIGHT；新wrapper用了H-1/H违反上界。
首失败立即停止，四个negative均未启动，总真实组2/2。

只静态修本任务新wrapper占位参数为H-2/H-1；原renderer这两参数仅在初始化范围断言引用，
真实底边绘制仍用SCREEN_HEIGHT-1，因此不改原几何/曲谱合同。
修后源码未编译/未仿真，不使用第三组；原失败wrapper字节在run_night_03/stage/s08.sv保存。
