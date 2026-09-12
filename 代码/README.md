# 正式工程入口

`代码/` 是 Tang Mega 60K 正式竞赛工程的唯一开发目录。早期八键原型已经冻结在 `legacy-prototype/`，不得在两处并行发展正式功能。

## 开工入口

1. 阅读根目录 `AGENTS.md`。
2. 阅读本目录 `AGENTS.md`。
3. 阅读 `docs/协作入口.md` 并确认岗位、任务编号、授权目录和验收条件。
4. 从最新 `develop` 创建任务分支。

## 当前目录

- `docs/`：项目事实、接口、决策、任务、风险、验证和协作制度。
- `rtl/`：正式可综合 RTL；更具体的岗位规则见局部 `AGENTS.md`。
- `model/`：Python 黄金模型和数值验证。
- `scripts/`：环境、检查、构建、烧录和自动测试脚本。

以下目录在真正有内容时再创建：`tb/`、`constraints/`、`sim/`、`software/`、`output/`。不要批量创建空目录。

## 常用命令

```powershell
. .\代码\scripts\enter_fpga_env.ps1
.\代码\scripts\check_fpga_env.ps1
.\代码\scripts\check_repo.ps1
```

`check_repo.ps1` 检查目录入口、Python 脚本、DOCX 结构、禁止提交文件和早期原型冒烟测试。它只证明当前环境可执行的静态检查与 L2 原型仿真，不代表正式工程已综合或上板。

> **已知问题（2026-09-12）**：`check_repo.ps1` 在当前环境**无法运行**。
> 它含 10 处中文路径字面量，而本机 `pwsh` 实为 Windows PowerShell 5.1，
> 会把无 BOM 的 UTF-8 源文件按 ANSI 解码，导致语法错误。
> 修复前请勿把它作为合并门禁。详见 `AGENTS.md` 的"脚本编写约定"。

## 模块仿真

```powershell
# T019 时钟、复位与 sample_tick 一键回归（3 个 testbench，全部 PASS 时退出码 0）
.\代码\scripts\run_t019_sim.ps1
```

该脚本只依赖仓库内源码，会先把源文件复制到 ASCII 临时目录再编译，
以规避 PowerShell 5.1 向原生程序传递非 ASCII 路径时的截断问题。

## 硬件事实核查

板载晶振频率、引脚分配等板级事实常只存在于厂商原理图 PDF 中，
无法直接复制文本。`代码/scripts/tools/` 提供逐级深入的提取脚本，
用法与实战记录见 `代码/scripts/tools/README.md`。

本项目已确认的板级事实记录在 `代码/docs/板级硬件事实.md`，
引脚参考表见 `代码/constraints/tang_mega_60k_reference.cst`。

