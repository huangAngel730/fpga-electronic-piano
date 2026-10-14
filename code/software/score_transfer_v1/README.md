# PC 曲谱编码与上传 v1（T057 独立候选）

合同：`code/docs/hardware/score_transfer_v1/PROTOCOL.md`。上传事件而非PCM；不自动播放。
只支持严格JSON，不自动排序，零力度NoteOn转NoteOff。编码无需第三方库。

## 曲谱来源与目标导入流程（尚未实现）

实际用户从网上下载曲谱文件，再在电脑或安卓手机上选择下载的文件导入；**不要求用户手工逐条输入音符事件**。优先对可解析的 `.mid` 文件做本地转换：按文件时间与 tempo 换算为现有 48 kHz tick 的严格 JSON，随后复用本工具的编码及既有 T057 上传协议。安卓端文件选择与 BLE 实物上传仍须另行接入和验证；不能因现有 C3 固件／APK 可构建就称这些流程已通过。其他下载格式（如 PDF、图片）当前不支持，应明确拒收，不能静默当作可播放曲谱。仓库 `example.json` 是开发／测试夹具，手写它不代表面向用户的曲谱输入方式。本阶段不开发网站爬虫、在线曲库或自动播放。

在仓库根目录执行现有 JSON 编码，输出目录必须不存在：

```powershell
python -B -X utf8 code/software/score_transfer_v1/score_transfer.py encode --score code/software/score_transfer_v1/example.json --output code/tb/input/score_transfer_candidate/runs/manual_encode_001
python -B -X utf8 code/scripts/run_m3_score_transfer_acceptance.py --repo-gate --publish
```

后一命令默认本机ModelSim，可用`--modelsim-bin`指定包含vlib/vlog/vsim的目录。
专项采用40MHz时钟和真实115200位周期，不压缩UART或协议5s超时。

**当前禁止直接接FPGA串口。** 以下仅为M2另行安排独立引脚/码流、用户授权后的工具用法：

```powershell
python -m pip install -r code/software/score_transfer_v1/requirements.txt
python -B -X utf8 code/software/score_transfer_v1/score_transfer.py upload --score code/software/score_transfer_v1/example.json --port COM_REPLACE --confirm-independent-uart --session 1 --output code/tb/input/score_transfer_candidate/runs/hardware_upload_001
python -B -X utf8 code/software/score_transfer_v1/score_transfer.py abort --port COM_REPLACE --confirm-independent-uart --output code/tb/input/score_transfer_candidate/runs/hardware_abort_001
```

COM_REPLACE不是实际COM号；不默认打开任何端口。不得使用现有MIDI R17、STAT U15或BL616 V14。
仅在协议接收方有线双向UART工程已获批准后使用，无硬件流控。
UART USB-TTL适配器输出必须3.3V且共地；不要因适配器供电5V就假设TX/RX是3.3V。

每帧ACK截止0.5s、最多重发2次、整上传含全部读回30s；NACK/超时/短写/不匹配非零退出。
成功返回已提交meta并逐条READ全部事件。编码输出records.bin/upload.bin；
硬件调用保留tx.bin/rx.bin及receipt.json/SHA；目录存在拒绝覆盖。
`--ack-timeout`/`--total-timeout`可调整至有限正值，`--retries`为非负整数。
只同一上传事务串行操作，不在停等DATA的ACK重试中插STATUS/READ。
当前软件超时夹具与实际RTL响应的离线PC重放，不等于实时PC↔板卡验收。
