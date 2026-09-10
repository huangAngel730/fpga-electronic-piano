# Git协作规范

## 分支

- `main`：可演示、可复现的稳定版本。
- `develop`：通过模块测试的集成版本。
- `feature/<name>`：单一功能开发。
- `fix/<name>`：缺陷修复。
- `docs/<name>`：仅文档与规范。

## 工作流程

1. 从最新 `develop` 创建功能分支。
2. 只修改任务授权范围。
3. 小步提交，每次提交保持含义单一。
4. 运行模块测试并更新文档。
5. 提交合并请求，由至少一名非作者复核。
6. 合并到 `develop` 后运行全回归。
7. 达到阶段同步点后合并到 `main` 并打标签。

## 提交信息

```text
feat(dds): add 32-bit phase accumulator
test(adsr): cover release boundary
fix(i2s): align msb one bclk after lrclk edge
docs(interface): freeze performance event v0.1
```

## 禁止

- 直接在 `main` 开发。
- 提交厂商缓存和无关大型文件。
- 使用强制推送覆盖队友提交。
- 未经沟通同时重写同一公共文件。
- 把没有通过测试的码流标记为稳定版。
