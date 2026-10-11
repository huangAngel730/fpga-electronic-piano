# B2k 本轮交付

新增短程公开TB、独立取消/排空checker、10项软件自检、b2k有界runner/统一入口分派、
本轮封存脚本及说明。所有功能RTL仍与52ad3dc的LF字节一致，56冻结输入、7ROM、旧封存、
8共享文件SHA前后不变。只读DDS参考另列执行输入，既有声音结果不重新签收。

最终命令：

```powershell
& 'E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe' -B -X utf8 code/scripts/run_m3_polyphony_scaling_acceptance.py --stage b2k --output code/output/m3_t061_b2k_full_20261011_02
```

实际退出0，B2K_INFLIGHT_CANCEL_PASS_T061_PARTIAL，44.282秒/96步骤。
单步900秒/流程1800秒，未使用旧B2h长程特例。三个配置各42请求/17取消/4在途复位/21发布，
8个坏capture及2个编译行为反例指定拒收，10单测通过。原stdout/stderr、工具身份、
输入/产物SHA、完整命令和实际退出码均在收据/manifest内。

历史 `_01` 原样保留：三正常配置及坏capture已通过，但故意删控制排空的行为副本
使立即重入后的恢复永久等待，实际B2K_WATCHDOG/simulation1；该次不算合格反例或终验。
负例驱动改为充分观察后全域复位继续，新增单测补齐占用槽Pitch前提；最终 `_02`
独立重跑完整正反例通过。旧日志/镜像/收据及源SHA为生成时状态，不回填。
关机恢复时仅新TB/checker落盘，没有遗留运行；所有本轮运行都在恢复后新建目录。

本次原证据封存不改旧包；封存verify重算三份capture并验证成员SHA、步骤时限和反例退出码。
首次封存前检发现Python场景tuple与已序列化JSON数组直接比较不等，未创建封存目录；
仅封存器改为标准JSON表示比较，原capture、checker和运行收据均不改、不放松字段检查。
发布前对最终index快照实际运行check_repo九门禁。最终commit/tree、门禁原输出与远端develop
核验只写外层GIT_DELIVERY.json，不倒填执行收据。共享状态/编号由M2统一登记。

转发一个 `M3_T061_在途取消与复位排空_B2K_交M2_20261011.zip`：通知、实现/交付说明、
原证据内包、manifest/seal receipt、实际发布九门禁及Git核验。只限独立L2/周期验证；
未验证硬件、综合、资源、PnR/STA或新接入档位，不关闭完整T060/T061。
