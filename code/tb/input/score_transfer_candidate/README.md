# T057 自检与捕获

vectors.py真实执行PC编码器，生成115200串行请求/明确响应错误合同；
tb_score_transfer.sv在40MHz系统域跑原UART RX/TX及候选RTL。
TX从实际串行输出的起始位/数据位/停止位独立解码；EVENT仅来自公开同步读口。
check_capture.py不引用PC编码器或DUT私有存储，以原JSON独立生成每条期望记录，
核对输入字节身份、帧CRC/头部/ACK/NACK/meta/READ/全部公开事件/END，禁止零比较。

正例含512条满容量、13/7字节跨事件分包、尾包、同tick Off/On及重复音、
channel15/note127/tick0xffffffff、逐包ACK重放、旧→新发布。
错误含30余项真实串行损坏事务、旧曲谱保持、复位/ABORT/新BEGIN恢复及生产5秒超时。
另运行两个可编译的行为变异，必须仿真完成且非零行为拒收，编译失败/超时不作成功。
test_capture.py以真实正例capture生成23种损坏，并逐一执行外部检查器拒收。
CASE/TX记录真实40MHz系统拍号，独立检查物理响应的20ms/5s超时，不只等够时间再查错误码。
test_software.py的ScriptedTransport只用于软件时间/错误测试；RTLReplay使用实际UART解码
响应并检查每次PC写字节完全等于实际RTL输入，丢3次ACK、读取全部四份曲谱。
离线重放不是在线协同仿真或实际板卡，不冒称硬件闭环。

所有运行写runs/run_*唯一忽略目录，不覆盖旧日志。`--publish`把原字节Base64和SHA保存
到专用hardware证据目录；无波形提交。运行中源码SHA变化判FAIL。

```powershell
python -B -X utf8 code/scripts/run_m3_score_transfer_acceptance.py --repo-gate --publish
python -B -X utf8 code/scripts/run_m3_score_transfer_acceptance.py --check-capture code/tb/input/score_transfer_candidate/runs/RUN_REPLACE/normal/capture.txt --expected code/tb/input/score_transfer_candidate/runs/RUN_REPLACE/expected.json
```

ModelSim默认`E:/FPGA/Bpan/modelsim/modelsim1/win64`，可用--modelsim-bin替换。
仓库门禁在逐字节SHA一致的隔离副本跑未修改check_repo.ps1，避免在原工作区产生越界文件。
本轮不做实际电气、FPGA引脚/下载、正式播放、BLE/App或Gowin综合与布局验收。
