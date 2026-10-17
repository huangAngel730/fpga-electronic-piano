# R7-A C9 静态后继（L0，未运行）

基线16ac226552f6fb65347b229b8fad42146ed45644。只新增本包SW/TB/DOC的c9_binding；旧R7-A源码、原件和既有测试结论不变。C9不是对旧R7-A的测试升级，没有新增/恢复任何组、HDL、EDA或设备额度。

实际新源为r7a_c9_public_observer.sv、tb_r7a_c9_public_capture.sv，采用M2 C9同版顶层，复用原R6-2 driver。driver event_ready仍为输出，接driver_ready_not_connected；真实event接受观察来自DUT公开event_valid&&event_ready。没有私有层级、force、内部ready驱动或第二FRAME生产者。

旧38个obs口增加29个：C9的28口加旧采集未接的raw cancel reason，现67个obs加5个外部pins，共72个raw bit-string字段。posedge obs_core_clk PRE_NBA无延迟采样；X/Z按原位宽保留。复位异步快照和正常END逻辑沿用旧采集器，不预填epoch。六个捕获窗口参数仍须责任方独立冻结。

PORT_MAP_C9.json把69个normalized字段映射到实际公开量，cycle/epoch/finish单独记录或由独立RESET_EDGES绑定，余下apply_event_seq/audio_stable保持null。完整72→74矩阵位于R8-02 c9_binding/C9_COMPLETE_CAPTURE_MATRIX.json；67个obs口全部直接接入，core clock/polyphonic资格与uart_tx原量保留且明确不占normalized数据列。不得仅凭旧端口解析器允许output留空就宣称完整采样。

后继CLI：`c9_capture.py --raw RAW --resets RESET --end END --stdout STDOUT --output NEW_DIR`，只记录入口，当前禁止执行。它按固定旧assemble SHA选取未改写纯函数，复用43口投影的时基/reset/finish校验，再从完整72口构造74字段；原raw SHA及原始bit-string完整保留，内部投影SHA另列。纯AST派生证据进入未来收据；不import旧prepare/runner/main。

kind/mask/router_apply_seq/valid、config_take及upstream/effect/feedback三clip均独立保留。kind3/4/8的零data/seq+valid0标为无效原因哨兵，不是全零输入事件；kind1/2同seq的多阶段逐行保留、不去重。kind0空闲持有值不作事件解释。config_payload仅在实际config_take且已知时按62位既定拼接解释。advance_frame_req_id是请求tag，FRAME F仅来自frame_tick；advance_mask使用M1真实lane_tick公开路由，不由接受请求推造。

SOURCE_APPLICATION_C9.zip含M2 C9原源体、追加唯一driver/observer/TB（72+3=75单元）、两头、9 ROM及两个逐字节裸ROM别名、四份原R6-2输入。解包inputs为未来cwd，明确使用compile_c9_capture.f及tb_r7a_c9_public_capture；保留的compile.f/旧清单仍只描述M2基包，不能混用。源体归档不是准入。参数/运行时readmem仍未elaboration，工具/argv/timeout、真实窗口和执行收尾未冻结。

新增八例及七行合成输入仅为待运行原件，NOT_RUN、未分配新预算。合成kind1/2所在行只测同序号多阶段保留，不定义NoteOn固定延迟。M1“前一沿”文字仍待勘误；独立输入计划到真实接受映射、audio_stable规则、真实trace/FRAME_PLAN/数学/完整HDL与硬件仍PENDING。

实现限制：当前C9 codec为≤64MiB的有界批量转换，未继承旧CLI的大文件流式能力；大规模真实窗口需后续流式接入及独立许可，不能据本代码签完整捕获就绪。当前只执行源/JSON/文件身份静态读取与源体封装，没有Python AST检查、候选导入、功能测试或HDL编译。board_release_allowed=false。
