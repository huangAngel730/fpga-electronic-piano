# T061 B2f：N8 身份共享控制独立后继

按 M2《夜间整机与两项复核回执_给M3_2026-10-11》最小返修。
只写 D043/D044 B 五路径及全新 output，不修改共享表，登记提议由 M2 统一处理。
正式四声部、新 RAM、其整机 L5、旧失败记录与本声音候选互不替代。

## 修复和旧源保护

旧 N8 33c8b70 的 b2c 五份 RTL/TB 原样保存；原 b2c Python 文件固定 f2cc0a8。
新 N8 入口直接实例化已交 0ca4515 的 b2d_control_snapshot/b2d_event_audio，
没有复制重写另一声音架构或修改现有功能 RTL。
控制按完整 source4/channel4 共享；即使 slot 空闲也读取对应身份真实控制。
occupied 只屏蔽发声，不能用空槽默认值覆盖同身份活动槽的控制。
未初始化身份由 initialized 位屏蔽旧 RAM 数据，逻辑默认 range2/mod0/bend0。
B1/B2a 算法三源仍固定 1c73e8d，冻结 L56 输入/7 ROM 固定 6f3e813。
原 B0/B1/B2a/B2b/B2c/时间返修/N16/N32 封存保持。

新 tb_b2f_event_audio 来自原 N8 TB，仅替换 TB 模块名和 DUT 实例名。
runner 将两替换后的字节与 33c8b70 Git 原件逐字核同；原长短程激励无改动。
新 b2f_check 使用原独立 Oracle(identity_controls=True)；解析驱动从原 check 逐句继承，
仅显式选择 N8/R1,3,64 与后继 TB 的 finish 文件名。
原 checker/Oracle 不编辑，原入口空槽语义和已签旧 capture 结论不回填。
新期望只由 R/I/J/X、只读 ROM 与源码日历推导，输出不反填期望。

## 公开端口定向测试

tb_b2f_identity_control 在 40MHz 单 clk 下实例化真实控制快照和 B1 statebank。
rst_n 异步断言，在下降沿释放；无 CDC、无新公共端口/引脚/约束。
独立事件 scoreboard 按接受事件更新 source/channel 字典，接受请求时冻结全部 N 槽期望。
将实际快照逐槽写入真实 B1 银行，通过公开 rd_* 核完整身份、occupied 与控制值，
不 force、不读取 DUT 内部信号、不用实际控制输出构造期望。

13 次快照/104 次全槽公开读回覆盖：

- 同 f/f 身份双活跃、slot7 先退、双活跃恢复、slot3 先退。
- 同 source 不同 channel、不同 source 同 channel、未初始化 f/e 默认。
- 非法 range25 不覆盖旧值，同沿控制事件/请求看到新值。
- busy 时事件背压，输出未握手时保持旧快照且拒绝覆盖；后继请求看到新事件。
- busy 中复位、held 输出中复位、旧 RAM 物理内容保留时逻辑默认恢复。

恢复 B2D_MUTANT_MASK_IDLE_CONTROL 的真实编译变异运行同一 TB；
变异只跳过快照控制值的提前断言，让错误走完真实银行写入/公开读回，
须 compile0/sim1 且指定 B2F_BANK_CONTROL_CLOBBER，不以 watchdog/编译失败当拒收。
此外实际 N8 忽略 generation 和 gain0 两个原行为反例仍须指定拒收。

## 时间、声音和未验范围

所有声音/舍入/饱和/包络、CC64、生命周期、取消不回滚语义及全 tag 保持。
Q=W+8；G(i)=Q+3N+5+3i；C=Q+6N+3；A=C+8；
L(i)=C+15+R+(3+R)i；首次 F=C+16+N(R+3)。
late 按首次 F-J-1>=833，F 与 P 握手分开，不用观察范围硬编码时限。
原长例要求全 ADSR 状态、至少 N 次真实 release→Idle 退休、全部 N 槽非零、256 控制身份；
短例覆盖取消/身份作废/背压/复位/全槽银行读回。11 完整 capture 反例保留 END 和总数。
本修复只交独立功能 L2/数学 L3，待 M2 复核，不证明生产 N8/整机资源/物理 STA。
两种先退次序为公开快照占用生命周期定向测试；原长程另证明真实 ADSR 退休，
不冒称该定向 TB 自身含 ADSR 或两种先退都由真实 DSP 驱动。
完整高 N 多样演奏、正饱和 RTL、冻结 L 全 top 逐时钟等价及全局服务界限仍未闭合。
不运行 Gowin/综合/PnR/串口/安装/接线/下载/烧录，完整 T060/T061 不关闭。

## 复现

仓库根目录，现有 Python/Icarus 工具，选择从未使用过的输出路径：

```powershell
& E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --stage b2f --output code/output/m3_t061_b2f_reproduce_NEW
```

单步骤<=900秒、总<=1800秒，原 stdout/stderr/实际命令/cwd/退出码/工具与源 SHA 记录。
验收源及冻结/旧证据/共享表前后字节必须一致；发布另跑精确索引树九门禁。
