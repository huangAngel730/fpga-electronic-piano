# A失败原件与权限沿革

- `RUN_01`：旧10.7静态门槛下版本探查E/D各一次vlib-version启动链均WinError623，空双流，Python合同exit2。
  本轮无R05功能命令、无真实消费标记；中断未恢复此旧失败为成功。
- 新HEAD8b64a35授权2020.4后，`PREFLIGHT_2020_01`只做E同EXE局部PATH前置/Unicode子环境预检；
  `PREFLIGHT_2020_02`在沙盒外对照同命令、同EXE与依赖，均WinError623，未取得版本/退出码，仍BLOCKED_TOOL。
  没有更换版本、安装工具、改系统/缓解/许可或继续实际编译。空流不是漏保存。
- `JOB_SMOKE_01`：独立Python假进程正常退出0，说明监督器并非对全部进程都无法启动；不能据此断言ModelSim错误根因。
- 启动器后继记录CreateProcess之后AssignJob/Resume等失败位置和创建事实，消除“进程已建但构造失败记0”的潜在计数漏洞；
  只用Python正常／非零／进程树超时／限量自检，没有再次ModelSim探查。
- 主控指出`Errors: 01`原正则漏拒，在A写集改成`0*[1-9][0-9]*`，并补原始合成完整正负例；
  不改已签R04旧checker，也不把诊断发现写为实际RTL失败。
- `SOFTWARE_01`：34个外层纯软件子进程，最后合成ledger正例被CAPTURE_PARSE拒收；原因是夹具编码器用了缩进JSON而非JSONL。
  修正软件夹具逐行编码（无业务变化），新目录`SOFTWARE_02`退出0，36外层调用和20测试通过；首失败/坏JSON原件保留。

旧预检保留SOURCE SHA与原receipt，但未同期复制旧runner/checker源码本体；后续变更后不伪称旧代码已齐套封存，
不逆造同期源码。最终软件执行源本体和对应SOFTWARE_02的SHA均齐套；新增说明/封存脚本为后置静态文件，
不冒称经过此前20项测试。库/已知静态DLL有库存SHA，动态实际加载闭包、成功version/license仍UNKNOWN。
