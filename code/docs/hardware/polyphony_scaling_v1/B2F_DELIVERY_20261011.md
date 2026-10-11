# T061 B2f：N8 身份共享控制返修交付

实际收据：code/output/m3_t061_b2f_dev_20261011_01/receipt.json。
状态 B2F_N8_IDENTITY_SUCCESSOR_PASS_T061_PARTIAL，exit0，420.70秒。
全部新证据本轮真实运行，无 capture/RTL 步骤复用；单步<=900/总<=1800秒。
最长真实 RTL 仿真341.34秒、对应独立复算55.09秒。
候选源、L冻结56输入、旧封存/共享表前后 SHA 全等。
原收据 repo_gates_passed=null 保持，发布另交精确索引树九门禁，不回填原收据。

| N8后继 | 发布P | 逐槽L（含取消前部分槽） | 首次F | 真实退休 | 计算年龄/拍 | late |
|---|---:|---:|---:|---:|---:|---:|
| R1原长程 | 10366 | 82945 | 10368 | 8 | 107–129 | 0 |
| R3原短程 | 100 | 816 | 102 | 0 | 123–145 | 0 |
| R64原短程 | 100 | 816 | 102 | 0 | 611–633 | 0 |

合计10566完整发布/84577逐槽结果/10572首次F，均由原独立路由与声音数学逐项复算。
原N8激励字节经Git核同（仅TB与实例名称替换）。
原长程完整ADSR/真实release回收、八槽满占用/逐槽非零、256身份、CC64、
窃取/重触发、取消非回滚/身份作废、背压/复位和公开全槽提交读回保持。
R64在N8本夹具内仍符合833拍；不沿用N16/N32慢档的未准入分类或外推全局事件服务上界。

## 身份边界专项

13次快照、104次真实B1全槽公开读回通过；具体场景与接口见IMPLEMENTATION。
两种同身份先退次序由外部slot占用/身份输入驱动，不伪称该小TB有ADSR；
真实ADSR退休由上述原长程独立验证。两类证据分列，不冒整机自由演奏已完验。
同沿控制请求、busy背压、held输出事件更新、reset忙态/held态及默认恢复均自动断言。
恢复旧掩码变异compile0/sim1，case2/lane3真实银行读回02000000，
指定B2F_BANK_CONTROL_CLOBBER；正例同接口/同夹具全部通过。

另两项真实可编译RTL行为反例：忽略generation compile0/sim1指定
B2B_STALE_GENERATION_ACCEPTED；gain0 compile0/sim0/独立checker1指定MATH_GAIN_PCM。
4项新软件自测、11项完整capture错例与40项原自测均通过。
完整错例保留END计数，A/F及最后槽双向错沿、tag代次/slot混叠、bit7占用、
PCM/公开bank错误逐项按指定原因拒收，不把结构缺失/超时当数学拒收。

## 新文件与身份

新增b2f_check/run/tests、tb_b2f_event_audio、tb_b2f_identity_control，统一runner仅追加b2f。
没有新功能RTL；实际N8实例固定0ca4515的b2d控制/声音wrapper，
原b2c RTL/TB固定33c8b70、原b2c Python固定f2cc0a8、B1/B2a三源固定1c73e8d。
新checker显式采用身份共享控制，原b2c_check/Oracle文件不改。
原源/原capture/原封存与共享表保留；原N8夹具签收不回填成一般无缺陷结论。
源码/工具/配置/原stdout-stderr/退出码、输入及产物SHA齐套；交付脚本核CRC/成员/SHA及receipt绑定。

## 等级、发布与下一步

本轮独立功能L2/数学L3候选通过，待M2专项复核；不签生产N8或物理40MHzSTA。
没有Gowin/综合/PnR/设备/串口/安装/接线/下载/烧录，未动新RAM或重启旧RAM。
正式架构/档位/资源/整机接入/新STA由M2决定；完整T060/T061不关闭。
N16/N32及其已有未验边界不因本返修自动签收。
按任务明确禁改共享表，当前状态/看板/验证登记提议交M2统一登记本返修范围。
本生成时尚未提交/推送；最终Git/远端/索引九门禁以新转发包GIT_DELIVERY.json为准，本文不回填。
待用户转发，尚未送达。
