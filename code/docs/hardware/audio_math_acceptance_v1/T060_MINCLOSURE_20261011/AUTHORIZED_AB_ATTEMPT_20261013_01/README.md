# T060 精确 A/B 唯一许可执行结果

本记录对应 M2 V0304 对 config `deef8bc73b6f8f2789149f3c1558bf05954919dbe05cda1d03dd2e97fefce637` 的一次组合 A/B 许可。执行机器为 `LAPTOP-KSS1MRR7`，未换工具、未提高超时、未重试。

## 结果

- 默认锁闭预检：`PRECHECK_ONLY_EXECUTION_LOCKED`，退出 0，2.890 秒。
- 唯一授权执行：`FAIL_PARTIAL`，退出 1，10.906 秒。
- `A_lower`：退出 0，0.219 秒；stdout 40462 字节，SHA256 `52b7c123d04cb18de98ba008eb2053dae97ec41c4613b306706c1744e2b24a22`。
- `A_compile`：未超时，5.390 秒，进程退出 `3221225477`（Windows `0xC0000005` 访问异常）。stdout 为空；stderr 3490 字节，SHA256 `9f779e1341d8c62cd595d215ac84cb084a7ba958209e42a3dd9eff4eb2aed3c3`，内容只有 Icarus `constant selects in always_*` 提示，没有正常 fatal 诊断。
- `A.vvp` 未生成；A capture 未开始；B 未开始；没有 T060 新 capture。
- 源和工具执行前后身份相同，自动重试为 0；产物收集和失败收尾完成。
- `ONE_SHOT_ATTEMPT.json` 已写入并绑定原输出目录，许可已消费。不得通过删除 marker、迁移输出、替换工具或改变参数来重试。

## 原始证据身份

| 文件 | 字节 | SHA256 |
|---|---:|---|
| 锁闭预检 `receipt.json` | 276630 | `e80067d25521253791b58a3511877185a64b13b0debd8b6c409a9caff1c55124` |
| 授权执行 `receipt.json` | 310162 | `c9cfb7ff1b1e8faaff62902201f17ac9fc23f5b5e0441a56d4589448f6bcd3fc` |
| `A_lower.receipt.json` | 830 | `29820a5788a99f170a62d37fff178878a30260f0c09c969393259acac3ea693c` |
| `A_compile.receipt.json` | 1914 | `a38009c6146f8ecb2e6981d0dc95cc1e3ff4a37d72a4dc45953d947517ba0fca` |
| `A_compile.stderr.txt` | 3490 | `9f779e1341d8c62cd595d215ac84cb084a7ba958209e42a3dd9eff4eb2aed3c3` |
| `ONE_SHOT_ATTEMPT.json` | 1505 | `97f4ccd1bdeb3dcc5c26817d971fa86a2f7bc1e038ce0c3febead81b929d3538` |
| M2 `approval.json` | 1179 | `78c251492a8003db9a573ea3c0e4b6df0ce44bc59fa01444ba49426314627131` |

完整原始目录保存在本机 `code/output/m3_t060_AB_authorized_preflight_20261013_01/` 与 `code/output/m3_t060_AB_authorized_20261012_01/`，并进入本轮转发 ZIP。它们不因本摘要而回填或替换。

本次不证明 A/B 功能、T060 收口或 T061 收口；若需再执行，必须由 M2 根据本失败证据另给新的精确许可。
