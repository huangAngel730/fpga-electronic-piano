# 正式工程入口

`code/` 是 Tang Mega 60K 正式竞赛工程的唯一开发目录。早期八键原型归档 `legacy-prototype/` 已于 2026-09-15 删除（源码可从 Git 历史取回），不在任何位置并行发展正式功能。

## 开工入口

1. 阅读根目录 `AGENTS.md`。
2. 阅读本目录 `AGENTS.md`。
3. 阅读 `docs/协作入口.md` 并确认岗位、任务编号、授权目录和验收条件。
4. 切到最新 `develop` 并直接在上面工作，**不新建分支**（D025）；推送前先跑
   `.\code\scripts\check_repo.ps1` 并确认当前 9 项全 PASS。

## 当前目录

- `docs/`：项目事实、接口、决策、任务、风险、验证和协作制度。
- `rtl/`：正式可综合 RTL；更具体的岗位规则见局部 `AGENTS.md`。
- `model/`：Python 黄金模型和数值验证。
- `scripts/`：环境、检查、构建、烧录和自动测试脚本。

- `tb/`：可自检的模块与顶层仿真；`constraints/`：引脚与时序约束。
- `build/`：正式 Gowin 工程；`software/`：MIDI 监视器与 UART 上位机。
- `output/`：本机实验产物（大型生成文件不入库）。尚未使用的 `sim/` 按需创建。

## 常用命令

```powershell
. .\code\scripts\enter_fpga_env.ps1
.\code\scripts\check_fpga_env.ps1
.\code\scripts\setup_git_ssh.ps1   # 每个克隆执行一次
.\code\scripts\check_repo.ps1
```

`setup_git_ssh.ps1` 让 git 改用 Windows 原生 OpenSSH 客户端。Git for Windows 自带的
ssh 是 Cygwin 版本，启动时要创建命名管道，在受限环境下会直接崩溃：

```
ssh.exe: *** fatal error - couldn't create signal pipe, Win32 error 5
fatal: Could not read from remote repository.
```

改用 `C:\WINDOWS\System32\OpenSSH\ssh.exe` 即可正常 fetch/push。
该设置写入 `.git/config`，**不随仓库分发**，所以每人克隆后执行一次。

`check_repo.ps1` 检查目录入口、禁止提交文件、Python 语法、引脚一致性、DOCX 结构、外部整理稿完整性和顶层仿真回归。它只证明当前环境可执行的静态检查与 L2 仿真，不代表正式工程已综合或上板。

当前共 9 项检查，全部 PASS 时退出码 0，任一失败退出码 1 并列出失败原因。包含 T007 顶层与 T019 公共包仿真；T005 音频发送器另运行 `run_t005_sim.ps1`。

> **2026-09-15**：原有的"早期原型冒烟测试"两项检查已随 `legacy-prototype/`
> 归档删除。该检查编译的 4 个文件构成闭包（无 `include`、无 `readmem`），
> 对 `code/` 下任何改动都不可能产生结果差异，即长期假绿。检查项编号因此
> 当时由 10 项变为 8 项；后续加入 T019 仿真门禁，现为 9 项。旧文档中"第 9 项""第 10 项"应分别读作当时的第 7 项和第 8 项。

> **2026-09-12 修复**：该脚本此前含 10 处中文路径字面量，在本机
> Windows PowerShell 5.1 下被按 GBK 解码，`.\code\` 变成 `.\浠ｇ爜\`，
> 引号失配导致整个脚本无法解析——**此前所有合并检查实际从未执行**。
> 现已改为纯 ASCII 源码，中文路径由码点构造。
> 同时修复了三个连带缺陷，详见 `code/docs/验证记录.md` V0014。

## 模块仿真

```powershell
# T019 时钟、复位与 sample_tick 一键回归（3 个 testbench，全部 PASS 时退出码 0）
.\code\scripts\run_t019_sim.ps1
```

该脚本只依赖仓库内源码，会先把源文件复制到 ASCII 临时目录再编译，
以规避 PowerShell 5.1 向原生程序传递非 ASCII 路径时的截断问题。

## 硬件事实核查

板载晶振频率、引脚分配等板级事实常只存在于厂商原理图 PDF 中，
无法直接复制文本。`code/scripts/tools/` 提供逐级深入的提取脚本，
用法与实战记录见 `code/scripts/tools/README.md`。

本项目已确认的板级事实记录在 `code/docs/板级硬件事实.md`，
引脚参考表见 `code/constraints/tang_mega_60k_reference.cst`。


## 2026-09-30 本地正式四声部/STAT集成阶段

正常SOURCE_MODE=0接四路DDS/ADSR、批准的Q15截断、混音及代次PCM；SOURCE_MODE=1保留固定音DIAG诊断。Pitch/Mod/Sustain音频效果尚未接入，不能由本阶段声部实现推断支持。最新本地改动未提交推送，以阶段说明和输入哈希为准。

```powershell
python -X utf8 code/scripts/run_t024_audio_core.py
python -X utf8 code/scripts/run_t025_top_stat.py
.\code\scripts\build_electronic_piano.ps1 -Flow bitstream
```

正式构建用Git忽略的`code/build/staged_formal/`保存显式ROM路径副本，缺ROM警告会使构建失败。有效码流位于`code/build/staged_formal/impl/pnr/electronic_piano.fs`，Programmer默认SRAM路径已同步；旧`code/build/impl/`产物不是本次交付。下载前须核对阶段清单及SHA256，不以存在.fs判成功。
