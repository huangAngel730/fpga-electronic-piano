# C 恢复 R01：PARTIAL／真实来源失败回执已明确拒收

仅写 C 原隔离目录的 `RESUME_R01/`；原86项软件、旧源码、封包、已暂存文件均未修改或重跑，无EDA/硬件/Git写入。基线仍`c12636c034be62e10c564217298564422a533b9c`。

新入口：`code/software/m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R01/consume_real.py`，保留原主窗消费者，新增严格扁平快照映射与分段原始startup适配。机器字段严格采用A冻结`STARTUP_SCHEMA.json`，SHA`c27d2956431a3b0c6a5cb5f74ecf651457bf716467e43754c94579f917809302`。startup二进制X/Z保留原位宽，不补0；逐绝对沿/25000ps/RESET/END与主cycle1边界检查，首个全known且reset低、64沿内及真实业务前的选择检查独立于A。后置boundary的原始侧车/主文件身份必须同时匹配真实run receipt；startup始终UNKNOWN，不作初始化通过。

最终有用软件结果：扁平映射8/8（`mapping_R01`）；机器侧车/选择/来源链接19/19（`startup_adapter_R03`）；均exit0，原双流、命令、耗时、执行源本体与前后SHA保存。`startup_guards_R01`12项是早期规范化守卫版本的合成自测，不当成最终完整适配验收；真实成功全分支仍未执行。`startup_adapter_R01`14/15且exit1：漏首沿时RESET位置守卫先拒收，测试最初误期望后续序列诊断，检查器拒收行为正确；只修该测试预期，R02=15/15。R03因补充侧车→生产者receipt身份链接新增4反例而重跑该窄组。全部历史原件保留。

总控给出A最后真实失败原件：`code/docs/test/m3_r05_functional_integration_20261015/night_20261016/RESUME_R01/RUN_04/RUN_RECEIPT.json`，SHA`96f07239ee7f755865989cf9068fa33f62c28cfa907dbf96308d4f87d4133d2f`。C对该原文件运行新真实入口**一次**，exit1、`PRODUCER_RUN_NOT_SUCCESSFUL`，见`real_failed_receipt_R01/REAL_REJECTION_RESULT.json`与`RUN_RECEIPT.json`。这是预期拒收，通过失败来源门禁；不是C真实R05数字验收PASS。未生成的boundary以明确的`UNAVAILABLE_FAILED_PRODUCER_NO_BOUNDARY`参数标识，入口在读取它之前即因真实producer失败而退出，未补写或伪造boundary/capture。该次实际入口与当前入口源码相同；后加的raw链接guard仅位于当次未导入的startup_adapter分支。

A功能批次已消费3组并停止：末组`R05_STARTUP_OVER_64_EDGES`，主capture cycle0，`clipped=z`观察问题由A只读定位，C不跨写、不代跑、不扩大额度。无成功receipt/READY可消费，真实PT8211逐样本、逐请求deadline、数字≤10ms仍UNKNOWN；first-valid、模拟端到端≤10ms/PLL/STA/硬件未验，board_release_allowed=false。

封存入口`SEAL_R02/C_RESUME_PARTIAL_R02.zip`，逐成员身份/CRC见同目录`MANIFEST.json`和`SEAL_RECEIPT.json`；主回执`NIGHT_RUN_RECEIPT.json`。首次封存因Windows复制目的路径过长失败，保留`SEAL_R01`部分副本与`SEAL_START_FAILURE_01.json`；新R02只用扁平SHA标签文件名，`INPUT_COPY_MAP.json`保留原路径/目标/字节/SHA并逐项核同。包含本轮源/所有新软件双流与案例/失败来源receipt和相关原日志/原始startup、主文件的只读副本及冻结合同。未提交、未推送，交夜间总控统一门禁与串行发布。恢复真实采集需要新的有效许可，不恢复已消费额度；届时新成功原件到件还需跑完整分段来源成功路径，不能借本轮软件PASS签L2。
