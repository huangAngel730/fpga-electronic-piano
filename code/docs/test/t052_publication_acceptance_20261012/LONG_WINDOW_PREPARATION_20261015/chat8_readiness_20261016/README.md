# chat8：T052 R02 现机预检材料

本件严格对应总控`coordinator/chat8_20261016/DISPATCH.txt`第2项，工作基线`57ad4aeb8ef0a1dad3fcfaf68f83aad6d08b0af3`。仅写本目录和对应software的新`chat8_readiness_20261016/`目录，不修改父目录旧文件、提案或封存。未提交/未推送，Git写及最终门禁由总控统一处理。

M2执行决定原件SHA `01c9bda6c78dffa573a68c8eaeb13aead259e8c87fd3713bd810e9b6fcb6c075`：动态限额语义已接受，但真实一次compile/run/check尚未批准。本批只提供L0来源/环境/资源材料，不把metadata成功写成HDL L1；旧4207仍UNKNOWN，完整T052 PARTIAL。

## 新增实质检查

- 当前逐字节重算完整controls、预期事务账本、M1确认、冻结DUT/DDS/mixer/ROM。固定摘要来自旧冻结输入，不从DUT输出或新proposal反推。
- 当前TB、observer、父目录Python闭包逐个与M2核过的R02 ZIP manifest核同；该ZIP本体固定SHA`3776ea3d85f09099e7b33f5705d79300c4475697b5a0f1cfaed3dcfd603d54ee`。新增预检源单独列SHA，不能靠源码/proposal一起变化求绿。
- 当前Icarus/VVP EXE、bin/lib DLL、ivl辅助程序、Python EXE/DLL/pyd及Windows核心DLL静态库存前后重算。只做两次`-V`实时版本查询，不调用旧29/34测试或旧static_bundle；动态加载闭包仍UNKNOWN。
- 明确记录PATH、IVERILOG_ROOT、COMPUTERNAME及完整环境SHA（其他环境值不导出，避免泄露凭据）。两次`-V`和两个Python探针均复用原Windows Job实现，父进程暂时设置同一组显式环境，结束恢复；Job的CreateProcessW仍用`lpEnvironment=None`，故由实际Python子进程再独立回报继承值和完整环境SHA。
- 首轮保留了完整环境摘要不一致的失败：逐变量摘要定位仅为空字符串的COLORTERM在Windows CRT更新环境时消失。新组合明确列出并删除原本为空的键，再设置PATH/ROOT；这是显式环境构造，不是忽略差异或放宽完整摘要检查。未来启动也必须执行同样构造，不能只设置两个覆盖值。实际差异诊断原流保留，不导出敏感值。
- 一个正常环境正例；一个只在Python子进程内故意改IVERILOG_ROOT的负例。子进程退出0也必须被环境比较拒收。此两项是新增必要的软件增量，不重跑已签进程树29例/静态绑定34例，不属于RTL行为反例。
- 两次实际采样记录E盘可用字节（≥2GiB）、实际输出和额度的唯一绝对路径、lexists/父目录/ASCII状态。路径不创建，额度不消费；空间不是预留，命名检查不是锁，M2签发和实际启动前必须再核。
- 新`UNAPPROVED_UNIQUE_COMBINATION.json`绑定现机源、工具、显式环境SHA、具体compile/run/check argv、cwd和额度目录及既定预算，始终`approved=false`。只调用旧runner的只读`verify_identities`核当前组合，不调用`execute`、真实checker或编译/运行入口。

## 已明确的唯一写集缺口

总控本轮回复要求保持两个新目录，不允许在`code/output`另写探针。故实际旧runner拒收路径的可写性**没有验证**，必须标`WRITE_PROBE_SCOPE_NOT_GRANTED`，不能以本目录能写JSON代替。旧`bounded_runner.py`的`main()`明确要求`--refusal-receipt`位于仓库`code/output`，并由`write_json`独占写入；具体行号在最终交接报告中列出。

最小未执行方案：只新增`code/output/m3_t052_chat8_refusal_probe_20261016_01/`，Python独占写一份明确标注合成的`synthetic_refusal.json`，读回/哈希并保留原件；不调用execute，不创建实际长窗输出或额度目录，0HDL、0checker、0消费。需要另获明确写集许可才可做。本工具没有这个写入开关，不绕过总控决定。

额度目录当前不存在，不冒称已有可执行额度；M2若批准唯一组合，还须明确批准在固定位置准备空额度目录以及独立拒收路径，然后保持原独占消费规则。不得沿用128沿/T060或夜间R05额度。

## 可重复命令（只软件/metadata）

在仓库根目录，用已有Python：

```powershell
& 'C:\Users\songdongkuan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -B -X utf8 code/software/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015/chat8_readiness_20261016/run_readiness.py --prepared code/output/m3_t052_long_preparation_20261015_03/prepared --output code/docs/test/t052_publication_acceptance_20261012/long_window_preparation_20261015/chat8_readiness_20261016/R01
```

输出必须全新。外层保存执行前源码ZIP、实际argv/cwd、原stdout/stderr、子步骤退出/耗时、源码前后身份。正常预期：收集器exit3，表示材料含明确授权缺口；外层exit0仅表示本轮授权的软件工作正确完成并如实保留此缺口，绝不将其改成可执行许可。遇实际错误返回1并保留首份原件，不原样自动重试。

## 交付与局限

最终原件、精确组合、报告、文件SHA及新封存包均在本目录；输出中只保存两次真实版本查询和两次Python Job探针，不生成新T052真实capture。现机证据有采样时刻，之后磁盘、环境、文件/源、工具或命名空间变化必须重新核身份；静态库存不证明动态DLL闭包，软件检查不签HDL、声音/PCM数学或实物。基础四声部关键路径由其它已分工窗口继续，本窗口不抢写其目录。
