# V3 独立验证计划（主对话2）

仅写 verification / build / output / README；不得修 source 或旧版本。
开工仓库 HEAD 为 427f3d3，git status 空。旧目录各 95 个非缓存文件
（原始各 98 文件，排除 3 个 pycache）已记录 SHA256；构建后重新审计。
DESIGN_READY.json 未到前不得构建候选源码。

## 场景

- 邻音：36/37、48/49、60/61、72/73、84/85、96/97、107/108。
- 低区二度 36/38、三度 36/40；中区 60/62、60/64。
- 四音 36/37/40/43 和 60/64/67/72；单音 MIDI21..108。
- 10位力度 1/256/512/768/1023；持续、松键、重触发、复位、第5键抢占。
- Note/CC64 是否支持以复制源码链路为准；不能外推新正式音画版本。

## 验证顺序

1. 独立冻结 SHA 和 ROM 内容审计，代码及顶层/约束不变边界。
2. 模型单音频率/各分音/DC/削波/力度；V1/V2/V3同音符、力度、时间，
   同一包络的受控比较另列，不能混用旧 sqrt力度/简化ADSR作为正式黄金。
3. 保存原电平及RMS匹配WAV。RMS匹配只能控制电平，不能证明同感知响度；
   必须告知试听者先调至主观同响，再盲听，音色喜好由M3判断。
4. 频带包络报绝对起伏和相对起伏，另分起音/中段/尾段。自然衰减导致
   绝对起伏降低不等于相对拍频消失。Gaussian ERB近似诊断不是ISO粗糙度。
5. 真实RTL编译、自检和逐样本黄金比对；参数边界与混合操作回归。
6. 只在独占 build 的冻结快照综合/PnR/STA，50MHz实际报告、四种时序、
   ROM保留、引脚/电压/锁存器检查，报告缺失或任一违例则拒绝放行。
7. 仅全门禁通过才复制唯一 V3 fs + manifest/SHA 至 output/bitstream；
   不烧录、不Git提交、不改正式任务表。最后复查旧目录全哈希。

## 原理核查

Plomp/Levelt原始研究把相邻分音的拍动、频差与临界带宽联系起来：
[TNO原始论文摘要](https://repository.tno.nl/SingleDoc?docId=69747)。
因此不能仅凭全带宽RMS包络指标声称听感已改善。

Smith书籍的钢琴模型采用弦/锤/音板及耦合机制，含自然衰减及过渡交叉淡化：
[Piano Synthesis](https://www.dsprelated.com/freebooks/pasp/Piano_Synthesis.html)；
真实多弦还涉及多回路和轻微失谐：
[Coupled Piano Strings](https://www.dsprelated.com/freebooks/pasp/Coupled_Piano_Strings.html)。
这些是方案背景，不证明本V3简化RTL已经达到真实钢琴，更不证明增加失谐消拍。

等幅相邻基频在同频带内仍有物理差频拍动；相位只移动拍动时刻。
这条数学判断需通过指标自检保留，不以相位打散后的总RMS小幅下降替代验收。
