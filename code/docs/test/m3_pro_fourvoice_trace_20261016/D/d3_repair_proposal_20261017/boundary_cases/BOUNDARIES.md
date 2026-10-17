# D3：16例最小边界设计（仅静态预期）

源码：`code/software/m3_pro_fourvoice_trace_20261016/D/ingest/ingest.py`，SHA256 `3217f97e57daec534306a213c64566fa111e3116f15a15967ca881847c218e07`。M2原反例：`code/docs/test/m2_pro_offline_review_20261017/D3_COUNTEREXAMPLE.json`，SHA256 `4a32745969b0a4fe6b5aa7a4e880e96659ad677c9b22d790ff6ee4ce4eda0ee4`。下述诊断是**提案语义标签**，不是已运行CLI的输出，实际16例全部NOT_RUN。

原路径缺口：calendar 68–77仅列请求；96仅核cycle非递减；109–124只在收到FRAME时登记due；164–168的CANCEL只核due为空；130–132/169的END只核终态/请求集合/至少一次消费与复位；98–105的RESET可取消并清帧基准，103仅用年龄<834。缺FRAME时这些关闭路径可掩盖截止。

CASES.json是**非原V1 CLI兼容**的V2静态病例框架。共享完整req7正常消费前缀，避免首拒收被consumed=0等无关条件抢占；req8使用1677发起、四lane和合法RETURN。D833独立截止2510，D834独立截止2511。每例明确冻结FRAME日历、RESET计划、END/horizon及数组顺序，不能从观测到的FRAME/RESET/END反推时基。被审代码、适配器、manifest/ROM绑定及执行预算均未实现/运行。

| 例 | 区分输入 | 提案首拒收/合法对照 | 原源静态锚 |
| --- | --- | --- | --- |
| BC01 | 漏2510 FRAME，CANCEL2512、END2513，req8年龄835 | CANCEL处理前 `P_MISSING_SCHEDULED_FRAME` | 109–124未走；164–168/130–132可关闭 |
| BC02 | CANCEL2509、FRAME2510、END2511 | 合法早取消对照，无预期拒收 | 117–118严格早于帧；164–168 |
| BC03 | 同2510：CANCEL→FRAME | CANCEL当行 `P_CANCEL_NOT_STRICTLY_BEFORE_DEADLINE` | 旧117–118到FRAME才拒，不应迟到那时 |
| BC04 | 同2510：FRAME→CANCEL | CANCEL当行同一截止语义；精确字符串待M2 | 旧121–124登记due，166已拒 |
| BC05 | 漏2510 FRAME，未终结req8，END2511 | END终态前 `P_MISSING_SCHEDULED_FRAME` | 旧131已拒UNFINISHED，本例不声称旧误收 |
| BC06 | D833；RESET2509（deadline−1，年龄832） | 合法计划内早复位取消 | 98–105；独立reset截断旧未来帧 |
| BC07 | D833；RESET2510（deadline，年龄833），漏帧 | 修改epoch前 `P_MISSING_SCHEDULED_FRAME` | 旧103允许833<834，可能掩盖缺帧 |
| BC08 | D833；RESET2511（deadline+1，年龄834） | RESET前 `P_MISSING_SCHEDULED_FRAME` | 旧103已拒，验证精确首因 |
| BC09 | D834；RESET2510（deadline−1，年龄833） | 合法；防止“一律年龄>=833”误拒 | 103的833<834在本例恰合法 |
| BC10 | D834；RESET2511（deadline，年龄834），漏帧 | 修改epoch前 `P_MISSING_SCHEDULED_FRAME` | 旧103已拒，仍须独立日历 |
| BC11 | D834；RESET2512（deadline+1，年龄835） | RESET前 `P_MISSING_SCHEDULED_FRAME` | 98–105不可先清epoch |
| BC12 | 漏帧后PA2511合法电平，再CANCEL/END | PA分支前 `P_MISSING_SCHEDULED_FRAME` | 127–129当前只核电平 |
| BC13 | 不含RETURN1712，改RETURN2511，再CANCEL/END | RETURN写状态前 `P_MISSING_SCHEDULED_FRAME` | 151–156当前未独立核年龄；非重复RETURN |
| BC14 | CANCEL2509已合法终态，但漏FRAME2510，END2511 | END前 `P_MISSING_SCHEDULED_FRAME` | 关闭ledger不能删除独立帧覆盖义务 |
| BC15 | 同2510：FRAME→CONSUME8→REQUEST9；2511取消9 | 合法同cycle对照，无预期拒收 | 121–126/157–163/135–142 |
| BC16 | 同2510：FRAME→REQUEST9→CONSUME8→RESET；2511新epoch END | 原源允许的另一偏序及已履行截止后复位，无预期拒收 | 142 continue、157–163消费、100–104仅取消未到期9 |

**同cycle关闭规则提案**：不能在FRAME行即要求尚未读取的CONSUME已经发生，也不能在同cycle的REQUEST9前因旧req8尚未消费而误判“已经超期”。保留数组顺序，FRAME必须先于该帧CONSUME/REQUEST；旧消费与新请求是不同ID，原源没有强制二者的全序。跨到下一cycle或END/RESET关闭本cycle时再核全部到期义务；CANCEL要求严格`cycle < 独立deadline`，因此不能利用同cycle消费窗口延后取消。具体诊断字符串及更严格采样全序如需改变，交M2明确冻结。

**RESET不是按年龄全拒**：BC07/10是“缺到期FRAME/消费且先RESET”的反例；BC16先合法FRAME+CONSUME旧请求再RESET，截止已经履行，不能一概拒绝，刚发起req9可被计划内早复位取消。若真实系统规定reset优先吞掉同沿FRAME，必须由独立预签时基/相位合同明确，不从trace RESET临时生成豁免。本组提案用旧epoch要求覆盖到reset_cycle（含同沿），只允许独立计划的提前RESET取消未到期请求。BC06/09/16的新epoch首帧也已在输入中明确列为R+100、晚于END horizon；这是合成边界窗口，非真实Pro时钟相位结论。

**END覆盖不能随ledger缩短**：早取消后END<下一独立帧可形成合法短窗（BC15的req9截止3344，END2512；BC16由独立计划RESET2510截断未来旧帧）；END>=截止则须有相应FRAME（BC14）。END/horizon也必须事先冻结，不能读到任意早END就自行缩短覆盖。遗漏CANCEL后的FRAME、普通记录跳时基、RESET清epoch都由同一独立日历义务拒收。

本组不增加全面回归、真实Pro采集、音频数学/串行算法测试或N32。未运行任何病例，功能预算/消费0，`board_release_allowed=false`。M2绑定实际后继/CLI版本、V2适配/日历及首诊断后，才将这些静态输入转成获准定向验证；目前NO_ACTIONABLE_EXECUTION_PENDING_M2。
