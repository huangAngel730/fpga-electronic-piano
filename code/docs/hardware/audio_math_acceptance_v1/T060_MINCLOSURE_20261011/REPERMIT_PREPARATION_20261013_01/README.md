# T060 A/B 新许可前静态准备（执行锁闭）

日期：2026-10-13。状态：`PASS_PREPARATION_ONLY_EXECUTION_LOCKED`。

本目录是旧 A/B 一次性许可消费后的新增后继，只完成实际机器、冻结输入、
工具文件身份、旧失败和拟议配置的静态整理。它没有恢复旧许可，没有生成新
许可，也没有运行 Yosys、Icarus、VVP、RTL、EDA 或残留 `A.vvp`。

## 查重和继承边界

- 既有 checker、runner、A/B 计划、TB、observer、RTL、ROM 和旧 seal 已完整
  存在，本后继不重写、不修改。
- 旧 config 为 143354 字节，SHA256
  `deef8bc73b6f8f2789149f3c1558bf05954919dbe05cda1d03dd2e97fefce637`；
  固定 177 个输入、621 个工具文件、A/B 合并总预算 900 秒。
- 旧 approval SHA256
  `78c251492a8003db9a573ea3c0e4b6df0ce44bc59fa01444ba49426314627131`
  已被 marker SHA256
  `97f4ccd1bdeb3dcc5c26817d971fa86a2f7bc1e038ce0c3febead81b929d3538`
  消费，禁止复用、移动、删除或换输出目录绕过。
- 旧执行收据 SHA256
  `c9cfb7ff1b1e8faaff62902201f17ac9fc23f5b5e0441a56d4589448f6bcd3fc`
  为 `FAIL_PARTIAL`：A lower 成功，A compile 非超时退出
  `3221225477 / 0xC0000005`，无 capture，B 未启动，自动重试为 0。
- 编译异常后实际留下 681033 字节 `A.vvp`，SHA256
  `9fb6a6837817bf642e33913d4ea26dcbb309a8ad05e3f7e7b2b1740804a07c74`。
  它完整性未知、从未验收，本后继明确禁止运行或复用。旧摘要中“未生成”
  的说法不作为事实来源。
- 耐久失败证据以
  `code/docs/evidence/m2_ab_failure_t052_static_review_20261013/RAW_EVIDENCE.zip`
  为准：828943 字节，SHA256
  `6a531fae9c846ad2098c26919cc063cac9df9e84f7ff89a18e4d4890c92ccf56`。

## 本次静态结果

- 实际准备机器：`LAPTOP-KSS1MRR7`，Windows build `10.0.26200`，AMD64。
- 177/177 个冻结输入逐文件字节数和 SHA256 与旧 config 相同。
- 621/621 个工具／运行时文件逐文件字节数和 SHA256 与旧 config 相同。
- A plan SHA256 `dc05bc68552b81e782db2ad0a7edf3c2e8f1278cb89728316dc7c4c3a63277e5`，
  END=4095000；B plan SHA256
  `288eff5d6d0249997adf7dd52a487d37b8d31f624695c332f77ba75bbe9ceee1`，
  END=1600。TB、observer、stimulus、source calendar 仍引用原冻结身份。
- M2 的 compile-only 准备已存在且保持锁闭：receipt SHA256
  `0afd1c24967ac27b674e87c3b3839b3e42f713f255416c18e486765138c44c7d`，
  30 个输入、20 个编译项、281 个本机依赖、实际工具调用 0；仍需要新的
  一次性 90 秒 compile-only 明确许可。
- `PROPOSED_CONFIG_NOT_AUTHORIZED.json` 只是诊断前的静态描述符，字段
  `execution_authorized=false`、`direct_runner_compatible=false`。它不是可执行
  runner config，也不是许可；M2 诊断若改变工具链，必须另生成后继。

## 复现命令与实际执行范围

仅软件单元测试：

```powershell
& 'E:\FPGA\SDKs\espressif\tools\python_env\idf5.4_py3.11_env\Scripts\python.exe' `
  -B -X utf8 `
  code/software/audio_math_acceptance_candidate/t060_minclosure_20261011/test_ab_repermit.py
```

实际结果：8 项 PASS。测试只覆盖严格 JSON、SHA 清单、漂移识别、许可锁闭
和输出写集拒绝；没有 HDL 编译或仿真。

静态准备：

```powershell
& 'E:\FPGA\SDKs\espressif\tools\python_env\idf5.4_py3.11_env\Scripts\python.exe' `
  -B -X utf8 `
  code/software/audio_math_acceptance_candidate/t060_minclosure_20261011/prepare_ab_repermit.py `
  --output code/output/m3_t060_ab_repermit_preparation_20261013_03
```

脚本只读 JSON 和文件字节并计算 SHA；生成目录被严格限制为未重定向的真实
`code/output/` 根下全新子目录，根本身是 symlink／junction 或仓库内其他
位置都会被拒绝。脚本内部外部子进程数为 0，实际 HDL/EDA 工具调用、
compile、RTL、VVP、EDA 和硬件操作均为 0。

## 下一步（当前均未获执行许可）

1. M2 使用独立的新许可完成一次 90 秒 compile-only 诊断；不得和 A/B 补采
   合并授权。
2. M2 根据诊断结果选定最终 compiler 和完整工具依赖，封存实际机器、版本、
   runner、输入、argv、cwd、输出和失败即消费语义。
3. 在全新 portable root 生成 runner-compatible 最终 config；保留旧 marker
   原样，不复制旧许可。
4. 审核员／预审员核对最终增量后，由 M2 申请只绑定该最终 config SHA256
   的全新一次性 A/B 许可。
5. 获得用户新明确许可前，继续禁止 A/B compile、VVP、RTL、EDA 和设备操作。

## 文件

- `PROPOSED_CONFIG_NOT_AUTHORIZED.json`：诊断前、不可直接执行的拟议描述符。
- `STATIC_SOURCE_RECEIPT.json`：实际机器、177 输入、621 工具、旧失败和诊断
  前置条件的只读收据。
- `PREPARATION_RECEIPT.json`：本次生成物身份和零 HDL/EDA 执行边界。
- `MANIFEST.json`：本后继源文件与交付文件 SHA256 清单。
