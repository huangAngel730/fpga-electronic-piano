# B2j 本轮交付

实现：新短程公开接口TB、独立完成日历checker、10项新自检、统一runner的b2j分派及新封存脚本。
功能RTL仍与52ad3dc LF字节一致；原56冻结输入/7ROM、旧证据和8共享文件未改。
最新M2 N8后继/B2G饱和签收提交9811698/78f6781已快进纳入，不用本轮结果覆盖其边界。

最终实际执行：

```powershell
& 'E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe' -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --stage b2j --output code/output/m3_t061_b2j_full_20261011_03
```

退出0，状态 B2J_PUBLIC_COMPLETION_PASS_T061_PARTIAL，8.250秒、96步骤。
单步900/流程1800秒，未复用上轮长程放宽额度。三个正例1072/4712/7624连续观察沿，
合计39请求/39首次valid/30发布；8完整坏capture和2编译行为变异按指定诊断拒收。
实际周期和各SHA见收据和逐配置JSON，不把软件日历当40MHz物理STA。

历史保留：

- `_01` 失败：初始rst_n=0使首个PRE-NBA观察沿尚有X，checker严格退出1。
  新TB改为首次时钟前真实异步拉低；随后还补工具正常$finish脚注的严格识别。没有过滤X凑通过。
- `_02` 通过但仅9项新单测、尚未加入完整冻结Git pin和同源局部II字段，是中间状态。
- `_03` 最终源码新运行通过；历史日志/收据/编译镜像原样保留，其源SHA按生成时状态，不回填。

本阶段限定独立功能L2/源码周期参考核验，不新增声音数学签收或L4/L5。
原反压、取消、身份失效及非回滚合同保持。无长程重跑、Gowin、布局布线或设备动作。

发布前独立精确index snapshot执行check_repo九门禁。提交号/最终tree/原gate输出和
远端develop核验放外层GIT_DELIVERY.json，不回填本轮源运行收据。
共享表禁止写入按D043执行，交M2统一登记。

转发一个外层 `M3_T061_公开握手与排空周期_B2J_交M2_20261011.zip` 即可，
含通知、实现/交付说明、内层原证据/源码、manifest、seal receipt及实际发布门禁。
M2需复核后决定下一项正式准入，不自动关闭完整T060/T061。
