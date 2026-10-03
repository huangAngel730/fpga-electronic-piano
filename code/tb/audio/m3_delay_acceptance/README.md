# M3 T028 独立验收器（任务 B）

2026-10-03，任务单 `3f62a12`，仅新增自检和 runner。**验收器已准备，算法待验**。
测试框架在 M2 只改四处比较常量的诊断副本上实际完成 L2 自检；该副本不是 M1
正式修正版，不能据此关闭 T028 或记算法签收。零延迟仍待 M1/M2 合同确认。

## 文件与运行

本目录包含独立整数递推 `vectors.py`、真实 RTL 周期自检 `tb_delay_acceptance.sv`、
固定场景 manifest 和 **仅诊断用** `diagnostic_contract.json`。对应入口：
`code/scripts/run_m3_delay_acceptance.py`。不 import M1 DelayEffectFixed，也不调用
原555/2096向量测试冒充本任务成果。

仓库根目录，本机诊断副本实跑命令：

```powershell
python -X utf8 code/scripts/run_m3_delay_acceptance.py --rtl "E:/FPGA/GAOYUNFPGA/CallBack/M3_无实物并行任务_74158b6_20261003/references/T028_DIAGNOSTIC_NOT_ACCEPTED/diagnostic_limit_width_only.sv" --contract code/tb/audio/m3_delay_acceptance/diagnostic_contract.json --diagnostic-only
.\code\scripts\check_repo.ps1
```

默认 `D:/Gowin/oss-cad-suite` 的 Icarus；可用 `--cad <目录>` 指定。`--timeout` 默认
60秒，每个仿真独立超时、失败非零退出。每次新建 `code/output/m3_delay_*`，保存源
SHA-256、合同 SHA、编译/运行日志、seed、逐周期向量、正向 capture 和覆盖。
编译源是输入 RTL 的逐字节副本，**不修补输入原件**。负例只生成在忽略的 scratch。

正式修正版入口仍是明确的 `--rtl <M1修正版路径> --contract <已确认验收JSON路径>`，
不加 `--diagnostic-only`。JSON 是本验收器的机器合同适配格式，不取代 M1 原算法文档。
请 M1/M2先确认下列字段与修正文档一致，再提供该JSON，`status` 应为
`corrected_candidate`；不能只给诊断合同改名/改status而宣称已收到正式返修。

- `module=delay_effect`，既有PCM24与15位无符号增益端口不变。
- `pcm_bits=24`、`gain_bits=15`、`product_shift=15`、`rounding=arithmetic_floor`。
- `sum_policy=shift_each_product_then_add`、`feedback_policy=pcm_plus_shifted_feedback`、
  `saturation=signed_pcm24`。
- `latency_cycles=2`（E接受、E+2 NBA后valid）、`minimum_launch_spacing_cycles=4`，
  `depths=[16,1024]`。
- `reset=async_output_valid_clear_and_logical_history_zero`。
- `zero_delay_policy=pending` 时明确跳过接受delay0，不宣称通过；只有M1/M2确认现有
  modulo语义后可用 `modulo_depth_old`，再额外验证delay0多圈。旁路/清缓存等新定义
  本入口不自作决定，需另行变更验收适配。时序或算术合同不符会直接拒绝。

## 独立 oracle 与边界

对成功采样的输入锁存 PCM、delay、dry、wet、feedback；每个后续非采样周期把live
输入改为其他值。整数乘积分别做算术 floor 右移15，再用完整增长位相加并PCM24
饱和；反馈递推独立维护历史。E+2写反馈缓存并推进指针。TB逐**系统周期**核对
valid及PCM（包括间隙保值），不只比对“碰巧抓到的一拍”。

默认50MHz时钟；每次发起间隔4～8拍，不扩展成逐系统拍吞吐承诺。
两种深度分别超过3圈连续历史，覆盖delay1、depth−1、正负极值、0/最大增益、
正负输出及反馈饱和。每种深度重新使用 seed **20261003**，2048组随机参数。
在E+1/E+2/E+3前及脏长尾历史后异步复位，立即检查valid/PCM清零，恢复后
通过湿声历史递推排除脏缓存和旧事务。额外阶段退出的两次结果应被复位取消。

## 实际结果与证据

最终诊断实跑目录 `code/output/m3_delay_0gsjfgw4`，完整证据见其中 `evidence.json`；
仓库九项门禁全 PASS，日志 `code/output/m3_delay_fljiyu5c/repo_gate.log`。
本轮诊断 SHA-256 为
`ffae158bb503a331d2b4f652004a2823c07451e3f883eea4c4d86735373910de`。

| 深度 | 发起 | 有效输出 | 周期比较 | 随机参数 | 连续整圈 |
|---|---:|---:|---:|---:|---:|
| 16 | 2454 | 2452 | 13944 | 2048 | 至少12 |
| 1024 | 10518 | 10516 | 46160 | 2048 | 至少4 |

诊断输出与独立 oracle 全部匹配。每种深度5次复位；合计12968次有效输出、
60104次周期检查。三种反例均**先编译成功**，再由断言拒绝：输出1LSB错误、
valid晚一拍、写指针错误推进2。指针反例的内部定位锚点若在返修中变更，runner
会拒绝继续而非跳过反例；届时只更新测试夹具，不修改M1 RTL。

已实际验证缺RTL/合同/向量、空向量、畸形记录、数量不符、空/畸形capture、
X输出、时序合同不符和真实不结束仿真的超时拒绝。正向capture单独保存，
不会被反例覆盖。日志、版本和SHA随 evidence.json 保存在忽略目录。

原失败RTL SHA
`cb9e160dad18c644042b0913fbcf8c275c0453455d4262a0c4e8984bb5381839`
在此入口仍实际退出1：第6个周期输出−8388608，而独立参考应为8388351。
这证明没有悄悄套用诊断补丁再将原件记PASS；复现日志在
`code/output/m3_delay_9oplwidk/depth16/run.log`。

**未执行/待交接**：M1正式修正版SHA复跑、零延迟最终定义、无爆音/参数平滑、正式
接入、资源优化、Gowin/PnR/STA及实物。本任务不改算法、公共包、顶层或约束。
由M2复核并收口编号/看板；T028与T036的整体状态不因本测试框架而关闭。
