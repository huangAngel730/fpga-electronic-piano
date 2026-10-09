# T060 独立音频黄金候选：真实 DDS 局部回放

当前不是 A1/A2 完整交付，也不是完整音频验收 PASS。仅 Python 离线组件已实现；
原 capture2 封存双文件及 56 反例已经收到，原 bytes／SHA 不变。
接受事件／控制快照／LFO 到 DDS 的独立时间线已接通；整体仍明确 PARTIAL。
T061 尚未实施。旧 M1 checker、原 RTL／ROM、共享状态和旧证据均只读。

## 已有实现

- `strict_capture.py`：JSONL 严格字段／类型／代次／请求／STATE lane 组；
  F 全部 16 个合法 tag 的词法和参数个数；按原序比较 R/J/M，绑定 D 与 STATE。
  不把左右 PCM 运输一致当作 PCM 数学正确。
- `dds_model.py`：冻结整数 note FCW、PitchMod 算术，以及独立 DDS phase／
  480/960/1440 亮度窗／pending 换表模型。先比较 pre-NBA，再推进事件。
  `replay_states` 必须由调用方提供独立 FCW 输入；没有从观测 FCW 推导 expected 的默认回退。
- `test_candidates.py`：明确标记 SYNTHETIC 的组件正常／错误用例。
  两文件自洽的末条 FCW 错误仍由独立常量输入拒收；它不是原 capture 的数学验证。
- `timeline.py`：从 E 接受事件独立算 note FCW，从控制历史重建 S，按 C 推进
  每 lane 的 LFO；独立计算 F/D，再逐 STATE 比较 pre-NBA FCW／phase／table。
  Q occupancy 与 N allocation lane 只是所验证 DDS 边界的输入，不冒充调度黄金。
- `bundle_replay.py`／`check_pair.py`：核对收到的原包与全部载体 SHA、源正文／ROM，
  正例先通过局部数学检查，再逐个运行 56 原反例；每个子进程有真实退出码和原日志。

## 可复现入口

在仓库根目录，用已安装的 Python 3.11（无第三方依赖）：

```powershell
& 'E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe' -B -X utf8 code/scripts/run_m3_audio_math_acceptance.py --component-only --repo-gates --output code/output/m3_audio_math_prereq_NEW
```

必须使用不存在的新输出目录。`--component-only` 的退出 0 仅为组件自检；
receipt 的 `a1_complete/a2_complete/t060_complete` 均为 false。
不带该选项时，缺原双文件退出 2；即便双文件齐全、运输比较通过，当前实现也退出 3
并标记 `PARTIAL_TRANSPORT_ONLY_A1_INCOMPLETE`，不会误签 A1。
SHA 不符或检查失败退出 1；已有目录和非法参数退出 2。

收到的原包可通过下列入口运行（全流程结束仍退出 3，表示未完成，不是完整黄金通过）：

```powershell
& 'E:/FPGA/SDKs/espressif/tools/python_env/idf5.4_py3.11_env/Scripts/python.exe' -B -X utf8 code/scripts/run_m3_audio_math_acceptance.py --bundle-root 'E:/FPGA/GAOYUNFPGA/CallBack/M1_138K40_audio_V0208_M2复核反馈_20261009' --repo-gates --output code/output/m3_audio_math_received_dds_NEW
```

包子任务退出 0 只表示成功完成本次明确 PARTIAL 的诊断；完整 runner 退出 3。
正常双文件子 checker 退出 0 且状态 PARTIAL；负例退出 1 且必须匹配指定诊断。
导入／缺文件／ROM 等基础设施错误退出 7，不计作反例拒收。

原 observer 四个 STATE always 与计数器的 `observation_cycle++` 分属同沿活动区进程。
原始打印计数可能为旧值或新值。默认 `compare_pair` 仍要求 cycle 严格相同；
真实 replay 显式启用这一冻结 observer 的解释，按唯一 epoch/request 绑定 D 逻辑沿，
要求 `D.cycle-STATE.cycle` 只能为 0 或 1，保留原始行并输出分布。
不是数值容差、不改输入、不迁移采样沿；该口径另交 M2 复核，`a1_complete` 仍 false。

默认只运行新 Python 代码。显式 `--repo-gates` 才调用已有仓库门禁；
不重跑原 capture 音频 RTL，不运行 Gowin，不安装工具、不打开串口或设备。
总时限不超过 1800 秒，单步不超过 900 秒，保存原 stdout/stderr 和退出码。

## 输入和已知边界

原双文件的 raw SHA 来自已登记 `platform_preparation_20261005.json`，不是拿当前输入自签。
本地 H40 源／7 ROM／原 TB 模板／observer 模板等与任务提交 `6f3e813` 的 Git blob
按 LF 比较，另记磁盘原字节 SHA。这个核验不替代原 capture2 生成 TB 和观测清单。

F END 的 total/nonzero-left/normal-push/synthetic-push 四项可由 F 重算；
其余五个计数涉及未观测 TB 条件，目前明确列为 unobservable，而不是假称已全验。
envelope 字段目前只检查语法和枚举；同步 ROM 延迟、增益、混音、PCM 数学仍未验收。
三个实际 envelope 反例明确未拒收，不签完整 56/56。
fixture_select 在原 TB 的 sample_edge→accepted_only 段有未记录的切换；
仅该段外能由冻结刺激顺序证明为 0，段内不伪造 expected。
exact generated capture2 TB／observer 尚未包含在收到的包里，目前只能核模板及原 capture SHA。

之前的缺原包状态已被本次接收核对取代，旧 DELIVERY 和旧失败输出保留。
继续 A1 尚未闭合的观察口径和 A2 数学，不用旧 50 MHz F-only capture 冒充当前正例。
