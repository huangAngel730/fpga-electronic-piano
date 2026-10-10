# 给 M2 的阶段通知（待用户转发，尚未送达）

M2，原 V0208 封存包已收到，两个 Golden raw SHA 与登记一致；45 源正文／7 ROM／
139 份证据载体及 32＋14＋10 原反例均核对，原件未改。此前缺原包的通知失效。

M3 已在 D043/D044 授权新路径接通真实 E/control/C-LFO→PitchMod→DDS 时间回放。
原正例 9,964 条 STATE 的 FCW／phase／table 逐条精确一致，2,487 提交完成时序与运输核对，
包括合法无音符 lane、pre-NBA note_on、末条以及复位取消。
最终 56 原反例中 53 个实际退出 1 且匹配指定诊断；3 个 envelope／ADSR level 反例
当前未拒收，明确留给 A2，不报 56/56 或完整黄金通过。
32 项组件测试／55 个合成错误用例通过，九项仓库门禁全 PASS。

发现原 observer 的 STATE 进程与 observation_cycle++ 同沿活动区竞争：
同一 D 逻辑沿的 STATE 打印计数为旧值／新值，实际差 1 的 1537 组、差 0 的 950 组。
当前按唯一 epoch/request 绑定四 lane D，并只允许这一源码解释的 0/1 计数分类；
RESET/J/M 原序和 cycle 仍严格，FCW/phase/table 没有容差，默认严格 checker 仍保留。
请复核此观察口径；收到的 TB/observer 只有模板，确切生成件身份仍未补齐。
因此新结果保留 PARTIAL，a1/a2/t060_complete 均 false，整体退出 3，不自行签 A1。

自身新 checker 一处 fixture_select 身份漏检已补；只在冻结刺激可证明为 0 的区段核验，
2 个切换区段 M 不虚构 expected。首轮计数失败及中间 52＋4 结果全部留存，未覆盖旧证据。
本轮仅离线 Python；局部参考比较不代表新 RTL、Gowin、STA 或实物通过。
当前改动未 Git 提交／未推送，基础本地提交 ae06b5b；没有改共享登记、原 M1 文件、
生产算法／RTL／ROM、工程、接口或约束，未安装／开串口／烧录／接线。

下一步继续 A2 包络／ROM／增益／混音到 PCM 独立重算，先闭合三个原 envelope 反例；
T061 尚未开始。请对计数解释、模板身份及未观测字段给出复核意见；完整 T060 不关闭。

## 转发材料

1. 本通知及 `RECEIVED_DDS_20261009.md`：结论、来源、边界和定位。
2. `RECEIVED_DDS_EVIDENCE_MANIFEST.json` 与 `RECEIVED_DDS_EVIDENCE.json.gz.b64`：
   首轮失败／中间结果／最终收据，以及组件、门禁、56 子进程的真实原日志载体。
3. 新代码：候选目录中的 `timeline.py`、`check_pair.py`、`bundle_replay.py`，
   修订的 `strict_capture.py`、`test_candidates.py`、README 和统一 runner。
   `dds_model.py` 保持原已提交版本未改。源码精确 SHA 见最终 receipt。

无须再次复制 181 MB 原包；M2 已持有原件，按原 SHA 引用即可。
本包收据并非执行指令；解码只核 bytes/SHA，不执行旧日志或旧 checker。
