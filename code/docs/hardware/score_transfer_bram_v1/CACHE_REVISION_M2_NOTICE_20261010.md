# 给M2：T062新结构独立40MHz通过，待正式接入复核

待用户转发给项目M2，尚未送达。向主对话2的调度进度通知不代替本项目交付通知。
本文形成时源未提交/未推送。用户后续已明确要求上传GitHub，本次仅发布RAM范围，
实际提交号以最终交付消息为准，不夹带T061 N8改动；共享登记仍请M2收口。

T062已按用户更换方案要求实施：138byte current/last并行FF缓存改为同步ping-pong请求RAM，
保留24byte BEGIN字段；COPY发起/消费分拍、重复比较同步结果消费，公开一拍读及COMMIT同沿旧bank不变。
完整40MHz/115200真实UART731场景/710CRC回复、574串行事件/1240公开快照，
约8908万公开逐拍检查、三个编译成功行为反例指定拒收、八阶段24复位沿恢复全部通过。

新03真实Gowin综合11.032s/exit0、隔离PnR32.797s/exit0，40MHz/25ns，
Setup1ns/Hold650ps保护原报告Actived。实际Setup+7.654ns/Hold+0.001ns，TNS/违例0/0；
Fmax57.651MHz仅该环境，不改系统频率。PnR1316FF/2437Logic/9DPB、SSRAM0、Latch0。
正文8DPB+请求1DPB已核原生层级，旧综合3392FF降至1316FF。
Recovery/Removal本同步reset模块不适用，slack=null；工具无未约束count栏，
用131native端口+所有虚拟max/min延迟+唯一受约束clk/无派生clock和例外做明确分类，不造原生0。

旧05主动终止/FAIL_INPUT_CHANGED原件保留；新01约束语法错误、新02真实12Hold违例都保留。
仅根据新02的CRC同步reset/BSRAM地址端点，增加立即断言/一拍核心释放围栏及两口可逆地址编码，
不减保护/不加宽假路径/多周期/降频、不靠换seed重跑。新03才是通过源。

本次GitHub发布源码/TB/验收工具/说明；原始capture、原生STA及失败证据在本机ignored
code/output目录保留，收据SHA见CACHE_PUBLICATION_20261010.md。单一T062_M2_HANDOFF.zip
尚未生成，不能声称已交付证据包。隔离.fs/.bin/.binx禁止下载；本轮只有独立模块L5，
不是整机/实体UART/BLE/播放/上板通过。
请M2复核接口/释放围栏/地址映射与虚拟约束覆盖，建立新精确整机副本并跑新整机功能/STA，
正式登记和采用由M2完成，保留原L-v3/60K回退，不因本模块通过关闭T057/T059/T060/T061总体。
