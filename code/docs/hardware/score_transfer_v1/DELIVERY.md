# T057 有线独立候选与蓝牙采购准备交付

日期2026-10-07；基线develop `c85889c898f3ab64cf6aa374cc8affd7460ccdb7`。
任务单SHA256 `16ca6cb14a007c545121a703959bcf46fb8fd0feec1ee14a2c043f39bff8c3e7`。
原UART RX SHA256 `9a614ece9e02f3c1876ddb256511e1eb1cf3949cdd4251d24afdef07b2e9e4cd`；
原UART TX SHA256 `fcf088f455cfb52d0cd89ed45c7e78ac95ba87f6fc7399a1c150f04cf63f0925`。
两原件只读引用；本轮没有原RTL/top/pkg/MIDI/STAT/PLL/CST/SDC/封存L/BL616或看板改动。

## 实现

- PC：严格JSON/8bytes事件编码、CRC16、115200停等上传、有限ACK重试/总截止、逐条READ、ABORT、原字节/SHA收据。
- RTL：帧同步/CRC/版本/容量/会话/序号/offset、双银行暂存、逐字节完整CRC和事件校验、原子COMMIT、幂等末包ACK、公开同步读口、20ms/真实5s超时恢复。
- TB：原UART RX/TX+40MHz系统时钟，115200物理位流，TX独立引脚解码，公开读口捕获；不读私有存储作真值。
- Checker：原JSON独立期望，不导入PC编码器；严格字节身份/回复CRC/错误码/meta/全部事件/结束标记。
- 2个可编译行为变异、23个损坏捕获拒收（含缩短超时拍号）、7个真实CLI非法输入/端口保护及明确标注的软件超时/实际RTL响应离线重放。

一键：

```powershell
python -B -X utf8 code/scripts/run_m3_score_transfer_acceptance.py --repo-gate --publish
```

本机Python实际使用`C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`，
ModelSim SE-64 2020.4位于`E:/FPGA/Bpan/modelsim/modelsim1/win64`。
不同机器可用`--modelsim-bin`指定工具；脚本不启动Gowin/Programmer。

## 本轮证据与状态

最终完整入口：`code/tb/input/score_transfer_candidate/runs/run_j_v22g6p/`，总收据PASS。
原始证据的可提交版本：`evidence/run_j_v22g6p/`，raw_manifest记录每份原字节的长度和SHA。
正常完整串行自检PASS：685场景、666实际响应、32错误事务、540条UART READ、1206条公开读口事件比较；
512上限全部逐条串行与公开读回，COMMIT重复ACK无重复发布。实际5s会话超时/NACK恢复通过，
物理响应间隔199999650个40MHz系统拍（含前一ACK结束位置影响）；20ms帧间超时亦独立核对。
两个行为变异均编译exit0、完整仿真exit0，检查器exit1：
错offset在score1_public_read_all因公开读回不匹配拒收；漏整曲CRC在bad_score_crc_commit因错误发布拒收。
23/23损坏capture（含缩短超时拍号）、7/7真实CLI拒绝测试、6项软件自检均通过。
实际RTL响应离线重放比较540条事件，故意丢3次ACK触发3次有限重试；两条实际NACK立即拒绝且不重试。
本次3740个逐字节一致输入的九项仓库门禁PASS，check_repo实际exit0；未改变原门禁。
此前失败运行保留在忽略目录，不作为最终PASS证据；长路径修正仅作用于隔离副本Git入索引命令。
完整入口后安全快进到develop `fd2b414eede5767f3c7e487c4355a4fb073a5547`，新增远端改动不涉及候选/原UART。
同步后及交付资料补齐后另跑最终文件树门禁，收据见同目录FINAL_GATE.md。功能提交号以实际Git记录和转发消息为准。

关键源码SHA256：

- 候选RTL：`551fc393621d2f4b014e0d19f8c5d47ce39b594f040d4ed273929805f63fc537`。
- PC工具：`8e2a065dcea4fef997da2b0fda7e16a314c65c436b654903ca388be407ddfc07`。
- TB：`12723a3876e0ce162800f0ef44b13f080456a2aeeede76cb6d434af80adaaa12`。
- 独立checker：`56364d615c203433d0c28f1d719894c5e34e64c97011549db9c6d32c2c1fd3b9`。
- 正例capture：`c6ed14c912ebd40db72e3ffe04691deb1006fab77ef538ac0050ec5db1c7ce28`。
- 错offset capture：`66e0648596f53c202457488914a44f6172343278f3753537a4f1552d2c2c100c`。
- 漏CRC capture：`ed65f19b7bc0802bac7e92081fee17829448042ed2e0d808ca8cf4696b2dc793`。

完整12份执行源SHA见证据source_manifest.json.b64，原文件可按raw_manifest逐字节解码恢复；
恢复到新目录后使用同一runner的--check-capture/--expected离线重算，不能修改日志后沿用旧SHA。

每次运行source_manifest记录实际候选/工具/TB/checker和原UART源码SHA，receipt保存命令/实际退出码/原日志及捕获SHA。
`--publish`只在全验收PASS后保存原字节Base64、raw_manifest与SHA；可逐字节恢复原始日志/捕获/plan/期望。
一次一目录、拒绝覆盖；历史失败运行留在runs忽略目录，不与交付成功证据混用。
仓库门禁在内容逐字节一致并复验SHA的隔离snapshot跑未修改check_repo.ps1，避免原工作区越界产物。

## 等级及未完成项

实际仅L2自检/L3限定PC规范编码、独立JSON参考与实际串行RTL比较；不是真实板级传输L6。
PC的脚本超时夹具仅软件测试；实际RTL响应的Client离线重放不是在线PC↔RTL协同仿真或真实USB-TTL。
尚未执行：Gowin综合/资源/存储映射/40MHz STA/PnR、实际电平/USB-TTL↔FPGA、FPGA下载、播放/视觉调度、BLE/App。
当前不放行任何硬件下载。实际球位/Bank/独立工程以及正式播放接入由M2受控冻结。
公开读接口的COMMIT同拍旧银行语义写在合同；生产消费者必须绑定一份发布，不得跨提交拼接。
双银行8KB逻辑存储、8路拼读和ACK CRC构造仍需M2综合检查/安排优化，不能假设已推断BSRAM或满足整机余量。

蓝牙：推荐询价微雪ESP32-C3-Zero-M/SKU25532带排针2块（主用/备件），
用户含运费100元以内、优先50元内；详情及官方链接见BLE_SELECTION.md。
国内实际报价、运费、平台/城市/付款安排未落实，**未下单/未付款/未到货**；不把选型写成采购完成。
模块后续BLE↔UART桥需要独立固件，不是即插即用透传，不改板载BL616或FPGA配置。
M3继续负责采购跟踪，M2负责有线合同复核和后续接入/共享登记。

交接状态：待用户转发M2，尚未送达。
