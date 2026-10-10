# M2同步RAM精确整机工程准备（2026-10-10）

仅M2独立适配准备/身份验证，自审；没有执行综合/PnR/STA，不下载。受用户T062 RAM范围及M2正式集成职责授权，原T057/正式top/pkg/PLL/CST/SDC/原L-v3/旧build保持。此前13UART等价属于旧RAM前身，不冒新62输入工程已仿真或L5。

以已冻结score_receive_integration_1的61输入/52项为只读基线，唯一顶层变化是同名u_score_receiver从score_transfer_candidate换为score_transfer_bram_candidate，删旧score单源工程项、增加两个精确RAM源，得到62输入/53工程项。源绑定43080a8已核CRC流水与B口no-change私有实现原SHA；没有改其业务代码或采样/协议。音频/波形/ROM/PLL全部保持，不自动把模块综合/数字预算套旧整机STA。

原RX R18/TX T18候选CST和原SDC/其CDC/reset分类完整保留（只复用，不新增/放宽例外）；公开rd_req仍0、无消费者/自动播放。板型C/Dock31005已用户确认，Bank3.3只是声明、SDRAM复用及外接电平/共地仍需实物阶段核，未授权接线。

prepare_138k_score_bram_integration.py只生成独立code/build/138k_score_bram下新目录和frozen_receipt，拒绝覆盖/隐藏多文件/源码漂移/SDC或CST修改。ready_for_PnR/physical_STA_passed/board_release_allowed均false；已有原SHA/正负/正文映射核验是接入准备条件，不是已通过该新工程工具或实物。

2026-10-10实际执行`code/tb/board/score_bram_integration_20261010/test_prepare.py`：四个测试方法通过，18个损坏子例均非零拒收，另覆盖拒绝覆盖旧结果及目录越界。真实日志和原SHA在M2专项复核载体。自测只验证工程准备/身份，不运行RTL、综合或PnR。

补充自审发现初版收据字典比较的false/0及整数/浮点漏检，已改规范字节比较，修后共23损坏子例。原失败探针与初轮证据保留，修后测试和发布门禁独立封存；不得用初包源快照代替修后脚本身份。

新模块05最终物理收据未收到，本工具不操作作者后台PnR或使用其它窗口授权。之后精确新top需上传期间音频/波形等价与相关正负/复位/CDC检查，然后受控完整新工程工具和STA；任何新增运行另以实际授权/收据执行，不自动调用run.tcl。
