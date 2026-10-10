# T062：主对话4同步请求缓存结构修版

发布授权补充：用户在本对话明确要求“请你上传GitHub”，因此本次可在核对远端、
精确暂存范围和九门禁后普通提交并推送develop。以下“不提交或推送”是此前阶段边界，
仅该发布限制被新授权替代；原RAM五路径、不改共享登记/生产/N8、不操作设备等限制仍有效。

用户在主对话2明确要求终止旧布线和定时任务、更换方案并使用流水线等方法，
授权主对话2调度、主对话4全权实施 RAM 独立候选。已只读核到该用户原话；
不把旧138K B/C任务或音响历史问题当作当前任务。

只写原RAM五路径及新code/output。主对话2负责T061 N8，其目录和runner不可改。
不改共享登记、正式top/pkg/PLL/CST/SDC、旧T057/T059源/协议/公开一拍读/COMMIT。
不提交或推送，待主对话2协调发布；不抢索引、不安装、不操作设备/串口/烧录。
隔离工具自动.fs只作为未放行证据，不进入M2转发ZIP。

## build05历史终态（另记，不回填原件）

原code/output/m3_score_bram_timing_build_20261010_05及_05_launch/job保留。
主对话2核对PID43312、启动2026-10-10 14:09:32和完整pnr.tcl后按用户请求终止。
原receipt实际记录native exit4294967295、elapsed13787.109s、timed_out=false、timeout=null。
后台completion exit1/status FAIL_INPUT_CHANGED是运行结束后的共享登记身份检查，
与M2正常更新四登记表有关，不是新的RTL编译错误。旧Routing Phase 1标记既不证明
收敛也不证明死锁；无最终STA，不能写40MHz通过。本轮不恢复05或其heartbeat。

## 实质新结构和判断边界

旧原生XML：总3392 Register/3624 LUT等价/271 ALU/8 BSRAM，顶层3302 Register；
正文八lane各1 BSRAM。旧SDC只有25ns与虚拟I/O delay0，未带本轮工程保护。
旧源码current/last_body各138byte，成功回复结束沿并行复制1104bit，
动态读取last_body[pos]及body[10+copy_pos]。这是可确认的结构风险，
不是已被物理细粒度路由报告确诊的唯一根因。旧报告未提供完整高扇出/拥塞全局统计；
综合路径时钟扇出3408不能当作业务控制高扇出诊断。正文无reset清RAM循环，
CRC已分FETCH/STEP/FINISH，本轮不再用同方案重跑或换seed消耗时间。

新结构：512×8同步双端口请求history，地址{request_bank,byte_index}，
当前/最后成功请求ping-pong，仅24byte BEGIN字段保留并行寄存器。
缓存发布只交换bank位，消除138byte并行copy；重复比较RAM结果后一拍消费；
COPY_FETCH发起、COPY消费，使请求RAM的同步读真实参与功能。
DATA最多额外128拍（3.2us@40MHz），没有改变20ms/5s超时或线上协议。
raw request RAM无reset；valid/缓存元数据屏蔽不可用内容，复位清待消费比较。
公开A口仍独享八正文lane，rd_valid及COMMIT同沿旧bank合同不变。
实际BSRAM推断、资源下降和物理时序仍须工具报告，不由数组声明提前认定。

## 新构建准入

新输出目录，真实40MHz/115200 UART正负/复位完整回归后才综合。
综合上限600s；新结构首次PnR上限900s，失败原样保留，不自动同配置/seed追加。
25ns、Setup uncertainty1.000ns、Hold uncertainty0.650ns；Setup最差>=0.5ns，
期望>=1ns，Hold/Recovery/Removal/pulse非负，TNS/违例0，无宽例外/多周期/降频。
同步reset设计若原生Recovery/Removal表为空，必须结合实际时序原语/源明确分类，
不得伪造0ns或跳过其他时序门禁。虚拟I/O只证明模块环境，不是板级UART/整机CDC。

新执行所有功能/只读协议/接口输入继续逐件SHA绑定，保存runner快照/工具身份/
命令/stdout/stderr/exit/产物SHA。共享四登记独立保存运行前后SHA和变更列表，
不作为RTL仿真/构建功能输入；这不删除接口或功能身份检查，也不回填历史SHA。
最终独立可复现证据、单一ZIP及L等级/未验边界交M2；正式整机STA仍M2负责。

首个新build_01综合通过，1315Register/2137LUT等价/266ALU/9BSRAM，
但PnR尚未进入放置布线就被TA2000/TA1030拒绝：Gowin uncertainty必须用-from/-to。
已有冻结SDC明确载有这一工具语法。本轮修正生成器的作用对象写法，1ns/650ps不变，
旧失败目录/runner快照原样保留，另build_02同RTL重新综合/首次有效PnR；
不是同配置routing超时后的seed/算法盲重试，不沿用01失败为时序判据。

build_02首次有效PnR在约42秒内完成，实际Setup+7.428ns；但Hold12端点，
TNS-7.826ns、最差-0.797ns，故不通过。11条为rst_n虚拟输入到CRC同步SET/RESET，
另1条rd_index到正文BSRAM地址-0.003ns。由实报告触发两处RTL定点修复：
core_rst_n = rst_n && reset_ready（reset_ready逐沿采rst_n），断言仍同沿立即，
核心释放额外围栏一拍；原UART reset不变。正文两端口用同一可逆映射
{bank,index XOR {bank,index[8:1]}}，增加真实地址译码而不增加公开读拍。
这不是无意义delay链、时序例外或约束放宽；新版本重新完整仿真，再build_03验证。
同期修正审核器对原生不提供未约束count栏的分类：明确count未知，另核131真实虚拟端口/
所有max-min delay生效/单clk顺序拓扑/无派生clock与例外，禁止以缺栏默认为原生0。
