# B2公开CSV串行适配：限定准备完成，真实Pro待件

状态 **DONE_LIMITED_ADAPTER_PREPARATION__PENDING_PRO_SOURCE_OR_TRACE**。已完成当日单允许的无真实源软件准备；整体B2验收未完成。实际等级仅L1新适配器自检，无新增RTL、仿真、综合、STA、设备操作或上板结果。

新增common.py、preflight.py、adapt_serial.py、selftest.py、run_round.py及seal/seal.py，仅位于授权的新software/docs/test写集。只读调用已固定SHA的既有PinDecoder，不复制解码核心/D3来源工具，不执行旧套件。原始CSV行号、cycle、epoch及帧请求ID保留，ID=0合法；独立公开TX采样sidecar和独立PCM对照分开摄取。29列入口采用显式ALL_COLUMNS_KNOWN_FAIL_CLOSED，闲置X也拒收，比原监视器更严格。

| 实际执行 | 结果与限制 |
| --- | --- |
| ROUND_01 | 19项符合预期：1个合成运输正例exit0，18项拒收exit1；组exit0，8.453秒。12000拍、两epoch、14请求，10请求串行完整、2复位截断、2观察尾UNKNOWN，ID0两笔完整。仅该轮源码成立。 |
| 静态自审 | 发现额外cancel未清在途状态的缺口；保留R1原源码，未在旧版本追加执行误收试验。 |
| ROUND_02 | 最小修复后仅3项新用例：合法取消无发布exit0、额外取消exit1、commit同沿cancel exit1；组exit0，2.734秒。取消正例9请求完整、1取消、2复位截断、2尾UNKNOWN。首差异定位原CSV850行/cycle849/epoch0/IDffffffff。 |
| 版本边界 | 首轮19项未重跑，不宣称最终源码22项全量通过。自身只读子智能体复查新修复及结果，未发现具体阻断；没有额外运行。 |

新功能消费 **2/6轮、11.187秒**；Python组均≤90秒。无意外功能进程失败/崩溃/超时；预期拒收不是进程故障。原输入、两版源码、命令/cwd/PID/UTC/双流/退出码和逐产物SHA保留。预检枚举873个Python运行时文件身份，不能据此声称独立证明了动态加载闭包。封包工具只核已有文件/收据与CRC/SHA，不消耗新的功能轮数。

现有上午监视器原CSV串行pins为0，本轮只用作新入口拒收，不能作为串行正例。当前合成输入及其sidecar仅验证运输适配，不能代替真实DUT观察、M1算法黄金或真实延迟证明。声明capture末拍不等于实际finish/END/MONITOR_END完整闭合。

B1的61字段合同已只读链接，SHA d89076836f8c60dd6544bbf2d9a5e8fa2f645ef49c8860458210562adf12d716；公开映射仍待M2。真实HOLD/启动、clip归并、采样点和结束记录映射尚未实现/验证，当前测试视图不是61字段生产trace的直接入口。新Pro源码/ROM/top/真实trace、独立帧账本、同版M1黄金和成功结束原件未齐。**Pro、PCM算法、物理48k/PT8211、板测均PENDING，board_release_allowed=false。**

后续由M2提供精确源及公开映射/真实采样与结束原件，B1固定来源与独立真实日历，M1提供同源PCM/clip黄金；M3在后续有效任务和预算内接入。当前不扩大写集、启动EDA或重复已签测试。

交付入口为NIGHT_RUN_RECEIPT.json、SOURCE_LINK.json、FILE_LIST.json及LATEST_RECEIPT.json指向的ZIP本体。按总控最新收尾安排，仅封本轮新增内容；旧依赖/已签案例保留原位置和SHA只读引用。此窗口未提交/未推送、未操作Git index、未运行仓库门禁；总控只读领取后统一汇合/发布。未主动发送最终回传，未冒称总控或真人M2已签收。
