# T060 独立音频黄金候选：组件准备阶段

当前不是 A1/A2 完整交付，也不是完整音频验收 PASS。仅 Python 离线组件已实现；
真实 capture2 在本机缺失，接受事件／控制快照／LFO 到 DDS 的整条独立时间线尚未接通。
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

默认只运行新 Python 代码。显式 `--repo-gates` 才调用已有仓库门禁；
不重跑原 capture 音频 RTL，不运行 Gowin，不安装工具、不打开串口或设备。
总时限不超过 1800 秒，单步不超过 900 秒，保存原 stdout/stderr 和退出码。

## 输入和已知边界

原双文件的 raw SHA 来自已登记 `platform_preparation_20261005.json`，不是拿当前输入自签。
本地 H40 源／7 ROM／原 TB 模板／observer 模板等与任务提交 `6f3e813` 的 Git blob
按 LF 比较，另记磁盘原字节 SHA。这个核验不替代原 capture2 生成 TB 和观测清单。

F END 的 total/nonzero-left/normal-push/synthetic-push 四项可由 F 重算；
其余五个计数涉及未观测 TB 条件，目前明确列为 unobservable，而不是假称已全验。
envelope 字段目前只检查语法和枚举；同步 ROM 延迟、增益、混音、PCM 数学、
原 56 反例及真实控制／LFO 时间线尚未验收。

需要 M2 提供原 `capture2` 封存包及其 56 反例清单；收到后继续 A1，再 A2，
不使用旧 50 MHz F-only capture 冒充当前 40 MHz 正例。
