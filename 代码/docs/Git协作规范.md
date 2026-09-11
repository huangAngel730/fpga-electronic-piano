# Git 协作规范

更新时间：2026-09-11。对应决策：D011 AI 交接与协作设施。

远程仓库：`git@github.com:huangAngel730/fpga-electronic-piano.git`

## 分支

| 分支 | 用途 | 写入规则 |
|---|---|---|
| `main` | 可演示、可复现的稳定版本 | 只接受来自 `develop` 的合并，禁止直接提交 |
| `develop` | 通过模块测试的集成版本 | 只接受通过复核的功能分支合并 |
| `feature/<name>` | 单一功能开发 | 对应岗位负责人 |
| `fix/<name>` | 缺陷修复 | 对应岗位负责人 |
| `docs/<name>` | 仅文档与规范 | 文档发起人 |

禁止使用 `git push --force` 覆盖队友提交。需要回退时用 `git revert` 产生新提交。

## 工作流程

1. 从最新 `develop` 创建功能分支。
2. 只修改任务授权范围，见 `三人协作执行手册.md` 第四节。
3. 小步提交，每次提交保持含义单一。
4. 运行模块测试并更新文档。
5. 推送分支并创建合并请求，使用 `.github/PULL_REQUEST_TEMPLATE.md` 模板。
6. 由至少一名非作者复核。
7. 合并到 `develop` 后运行全回归。
8. 达到阶段同步点后由 M2 合并到 `main` 并打标签。

## 合并请求要求

合并请求必须填写模板中的全部条目，至少有变更摘要、运行命令、PASS 结果、验证等级、未验证的硬件项目，以及是否影响公共接口和约束。

复核结论使用通过、有条件通过或退回，并列出依据。复核人必须实际运行测试或查看报告。

## 提交信息

提交信息使用 `类型(范围): 摘要` 格式，摘要用中文或英文均可，但同一提交保持一致。

```text
feat(dds): add 32-bit phase accumulator
test(adsr): cover release boundary
fix(i2s): align msb one bclk after lrclk edge
docs(interface): freeze performance event v0.1
```

常用类型：`feat`、`fix`、`test`、`docs`、`build`、`refactor`、`chore`。

## 问题单

- 任务拆解和排期使用 `.github/ISSUE_TEMPLATE/task.yml`。
- 缺陷和异常使用 `.github/ISSUE_TEMPLATE/bug.yml`。
- 问题单编号在任务看板中引用，保持一对一或一对多关系清晰。

## 持续集成

`.github/workflows/rtl-smoke.yml` 在推送和合并请求时执行：

- 用 Icarus 编译并运行原型自检 testbench。
- 对 `准备/脚本/` 下的 Python 生成脚本做语法检查。

持续集成只能证明 L1 至 L2 级别，不能代替上板验证。

## 禁止提交的内容

- `.tools/` 目录和任何安装包。
- 波形文件、仿真数据库和临时缓存。
- 比特流、码流和厂商工程自动生成目录。
- 无必要的大型二进制文件。

具体忽略规则见根目录 `.gitignore`。新增例外时先在合并请求中说明理由。

## AI 参与规则

- AI 只能修改任务单授权的目录，需要跨目录时先停止并列出影响。
- AI 提交前必须运行任务规定的检查，并在合并请求中给出实际输出。
- AI 不得代替复核人签字，也不得把未执行的验证阶段写成已通过。
- 一个分支同时只允许一名队员及其 AI 修改，避免并发重写同一文件。
