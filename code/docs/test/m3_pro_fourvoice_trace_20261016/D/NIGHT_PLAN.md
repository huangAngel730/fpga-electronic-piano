# 夜间任务3 D/D2（10/17；独立夹具）

基线`ca4859abc28e3a5f7fdd0250e9f2cd43de39a8c0`；按总控当晚单，T0北京时间00:21、五小时上限。仅写software/tb/board/docs/test的`m3_pro_fourvoice_trace_20261016/D/`，排除`coordinator/`与`ingest/`。原文件只读；无Git写、门禁、编号、共享状态变更。总控后续调整：D/D2最多4轮（当时本窗口0轮已用），Python每轮≤90秒、可选Icarus≤240秒、D/D2实际≤2000秒；D3占2轮，共享合计6轮，不擅用其额度。

Pro精确source/ROM/top/trace和M1已发布黄金未取得；只做手算PCM边界及独立串行夹具。只读旧i2s_tx协议事实，不重跑旧86/303专项。PA_EN高有效及稳定等待8拍是本夹具数字策略参数，不代表Pro实物等待时间已确认。40MHz与48k是夹具时基，833/834统计从同一逐沿frame字段计算，不签Pro实采。

本轮选Python，Icarus不需要。预检冻结实际EXE、Python DLL/标准库依赖SHA、机器、版本和输入文档。固定输入plan、源码后才开消费轮，原始双流/命令/退出/时间/输出SHA齐全。正例覆盖左右不同、正负端点/半LSB、两复位寿命；坏例须在指定首差异实际拒收。成功即停，失败保留原件，仅在剩余轮内修确认的本包缺陷。

C日历到件只读核身份；缺件不等待、不造lane实测。结果只签L0/L1软件夹具，Pro DUT、同版STA、模拟≤10ms、Bank/PA电平和板测UNKNOWN，board_release_allowed=false。最终交总控一份回执/封包，由总控统一发布并交M2/M1，未授权其它窗口通信。

## 当夜输入刷新（保留上文T0事实）

总控已同步至`b6f289110a0b7341f1f9234c945bcb8d31d95aff`，其中`edcd090856895f56ede66e961f2bbf5d2bfdcf57`恢复M1旧R05五目录；现在不能再笼统写“M1黄金未发布”。新Pro精确工程/source/ROM/top/trace仍未到件，旧R05黄金不自动成为本夹具或新Pro输入。本窗口未因同步重跑旧组，也未修改他人目录。

C最终日历已冻结，round_3只读其LATEST_RECEIPT、CALENDAR和CONTRACT，按epoch内被消费帧的顺序映射到既有D诊断PCM请求。保留每lane的五字段身份及取消状态；这只是显式身份crosswalk，不签共同执行时基或C音符到PCM数学。用户在总控明确允许本夜四窗口回传，最终回执可直接发总控一次。
