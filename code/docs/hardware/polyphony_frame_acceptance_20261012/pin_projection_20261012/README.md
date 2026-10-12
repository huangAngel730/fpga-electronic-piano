# 帧事务真实端口投影软件后继

本目录是已签 `c36e58f` 抽象帧软件合同的独立后继，只解决未来真实捕获如何映射到现有隔离 adapter/hold/buffer。原模型、15 项自检、11 份正例、6 份反例及证据未修改、未重跑。本后继仅 L0/L1 软件验证。

## 投影结论

- `raw_result_credit` 是 observer 根据 `request_window`、`pcm_valid`、`frame_tick` 和 `dispatched` 得到的中间量，不是 `premixed_frame_adapter` 的公开端口。
- 公开 `candidate_result_ready` 已含当前 ID 资格；真正结果握手是 `candidate_result_valid && candidate_result_ready`。错误 ID 即使 raw credit 为 1，也必须 ready=0、握手=0。
- `pcm_frame_buffer.play_*` 在 `pending_valid=1` 时组合选择 pending，否则选择 held。commit 沿的 pre-NBA 播放仍是旧 held，post-NBA 立即显示新 pending。
- frame 沿实际发送样本按本候选定义为该沿 pre-NBA 的 `play_*`；同沿再把 pending 转入 held，post-NBA `play_*` 数值保持。该定义供未来 observer 审核，不能用 post-NBA 状态反写发送时点。
- `result_epoch`、`result_sink_ready`、`pcm_sink_ready` 仍是原软件合同的寿命/环境注记，没有映射成真实 RTL 端口。
- 原 `b2d_event_audio.sv` 没有准确 clip 公开端口。准确 clip 仅绑定新隔离 `b2d_event_audio_clipped.sv` 的精确 SHA；它尚未综合或接入生产。

## 复现

从仓库根目录使用 Python 3.11 标准库，输出目录必须全新：

```powershell
python -I -S -B -X utf8 code/software/polyphony_frame_acceptance_candidate_20261012/pin_projection_20261012/run_checks.py --output code/output/m3_pin_projection_20261013_01
python -I -S -B -X utf8 code/software/polyphony_frame_acceptance_candidate_20261012/pin_projection_20261012/deliver.py seal --run code/output/m3_pin_projection_20261013_03 --prior-failure code/output/m3_pin_projection_20261013_01 --output code/docs/hardware/polyphony_frame_acceptance_20261012/pin_projection_20261012/EVIDENCE_20261013_02
python -I -S -B -X utf8 code/software/polyphony_frame_acceptance_candidate_20261012/pin_projection_20261012/deliver.py verify --base64 code/docs/hardware/polyphony_frame_acceptance_20261012/pin_projection_20261012/EVIDENCE_20261013_02/PIN_PROJECTION_SEAL.zip.b64
```

runner 总预算 300 秒、每个子步骤最多 90 秒、失败不重试。它只执行隔离复制的 Python 源，记录源、文档、五份只读 RTL 身份和 Python 身份的前后 SHA；不运行 RTL、EDA、Gowin 或设备操作。

首次运行在执行任何子步骤前由闭包审计拒绝，原因是封存工具使用的 `base64/io/zipfile` 三个标准库模块未列入白名单。原失败收据随最终 seal 保留；修正只补标准库白名单，随后用全新输出目录执行。

固定材料包含两份完整正例和五份完整定向反例。覆盖错 ID 但 raw credit 有效、frame 与旧 result 同沿、pending PCM 与 held 不同，以及错 ready、commit 沿提前播放、commit 后仍播放旧 held、frame 发送旧 held、frame 接受旧结果。每个反例保持完整 META/EDGE/END，只改变一个观察映射并命中指定诊断。

## 验证边界

PCM 只按 signed24 payload 搬运，不重算 DDS、包络、ROM、混音或限幅数学。新 clipped 后继的 L2 结论作为字段来源身份引用，不被本软件运行升级。未验证真实 N32 长程、通用 833 拍截止、ID 实际回绕、正式接入、综合、PnR、STA、I2S/HDMI/BLE 或设备。完整 T060/T061 保持 PARTIAL。
