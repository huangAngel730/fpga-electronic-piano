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

