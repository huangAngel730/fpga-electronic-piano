# M2音频控制边界隔离候选

原PitchMod银行保持数学不变；新增私有identity_hold将内部retire/release登记保留但延到计算后执行。WAIT_DISPATCH/SETTLE继续排空既有dispatch，CAPTURE起独占身份至结果消费；DRAIN释放租约、frame取消优先。每lane身份比较寄存，再归约到sample_authorized_q，只有寄存授权驱动DDS/ADSR tick。正常完成多1sys拍（20ns）；不新增FIFO、不改外部PCM口、时钟、ADSR曲线或频率。

T027协作窗口文件不改，后续融合必须按功能而非覆盖文件。正式生产不写，本候选先做模型/帧/抢占/取消/退场验证，再一次同V0171原parser组合PnR，限30min。全局Setup目标+.5且至少改善.1，资源/全域/CDC门禁按manifest。功能或物理收益不达则保留原基线，不反复调种子。

新增阶段VERIFY=9；旧1..8相位编码保留仅供局部TB。不能依赖旧内部逐拍miter断言宣称新阶段失败，应按实际请求身份/样本/事件序列和帧截止比较，保护原接口语义。
