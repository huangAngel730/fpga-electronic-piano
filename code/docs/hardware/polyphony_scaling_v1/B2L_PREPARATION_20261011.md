# B2l：综合前输入准备，不执行综合

M3按D043/D044的B五路径继续同一复音候选。开工时B2I/J/K已发布、待M2专项复核；发布期fetch收到9240f38及V0278，B2I已限定L0/L1通过，B2J/K仍待专项复核。本轮不替代或提前签收它们。新阶段只把后续资源预检的输入准备做成可运行代码，不选择正式架构或准入档位。

**发布期最新边界优先**：M2已选择N32/R1为资源工程准备代表、N8为备选，精确工程与一次性有界工具入口由M2准备，未增综合额度。因此本轮只交可参考的prepare-only输入/wrapper资料，不并建另一份Gowin工程，也不再请求自行选择N8。四配置编译只是已完成的软件参数自检，不是四档工具构建。M2可取用或拒绝本profile，不必采用本准备目录才能继续自己的工程。

## 实现和结果

- `code/software/polyphony_scaling_candidate/b2l_prepare.py`：只提供prepare/verify，必须显式指定N/R。绑定52ad3dc5e27f499bc79bad5c1a6b8d4bbf8a4387的13份功能源、2份include、7份ROM。逐项对Git blob核LF SHA，不以自写manifest自证来源。
- `test_b2l.py`：12项软件自检。覆盖严格整数/参数边界、保留时钟保护、源身份/路径重定位、拒覆盖/越界路径，以及改wrapper后重签清单、ROM损坏/缺件、额外工具脚本、伪造许可/布尔类型等拒收。
- `b2l_run.py`：有界新目录流程，只运行新自检、准备/复验及Icarus elaboration，不执行VVP/Gowin。原stdout/stderr/命令/退出码和运行输入/56冻结输入/旧封存/八共享文件前后身份记录齐套。
- `deliver_b2l.py`：封存及转发工具。工具编译的临时.vvp不入包，只保留其SHA，原编译日志与全部生成输入入包；不把未封存的二进制写成可恢复原件。

实际最终流程：`code/output/m3_t061_b2l_prepare_20261011_01/receipt.json`，退出0，21.406秒。12项软件测试通过；N4/N8/N16/N32、R1的四个wrapper均编译退出0，14个步骤。没有运行新音频仿真、长程capture重算、综合/PnR/STA/设备。

四配置编译只是参数化准备入口的静态可用性验证，不是四个综合配置获批，不消费综合额度，不取代原限定数学L3，也不声称当前已具备可直接执行的Gowin工程。

## 拟议wrapper的精确范围

顶层`b2l_resource_probe`保留正常事件/采样/取消、PCM结果及背压、late/abort/idle/fault/publish和公开bank READ。真实结果注入关闭，注入tag/context为常量；巨大逐槽诊断bus不外引。未增加PLL、采样发生器、同步器或引脚。

本profile命名为`audio_and_public_read_no_injection`。保留READ使B1 payload bank可观测；工具仍可删除无功能影响的诊断状态，不能拿B2I声明位数作物理FF精确期望。该profile尚未获M2采用，本地生成物的`representative_configuration_approved=false`仅表示本准备物未授权工具执行，不否定M2已作N32/R1准备选择；prepare/verify不接受“批准”开关。

生成目录只有source/include/ROM、wrapper、inputs.json、plan.json和clock.sdc。只对精确ROM根字符串进行9处可逆机械重定位（backend4、Pitch3、ADSR2），不改变算术/时序/参数/ROM字节。生成SDC包含25ns单时钟、Setup 1ns/Hold 650ps保护，无false-path；未定义板级I/O或复位例外，不以此声称完整时序约束。

没有生成.gprj、工具执行Tcl、CST、码流；Gowin版本及器件是原授权候选值，明确`verified_here=false`。不调用工具，不代替M2的代表配置/工具选项/资源准入决定；后续真正工具入口另行受控实现。

## 复现

在仓库根目录，用已有Python：

```text
python -B -X utf8 code/software/polyphony_scaling_candidate/b2l_run.py --output code/output/全新ASCII目录
python -B -X utf8 code/software/polyphony_scaling_candidate/b2l_prepare.py prepare --n 8 --response 1 --output code/output/new_b2l_n8_r1
python -B -X utf8 code/software/polyphony_scaling_candidate/b2l_prepare.py verify --output code/output/new_b2l_n8_r1
```

原输出含绝对ROM staging路径。搬家后重新prepare产生新路径/SHA，不手改旧收据或声称搬家后仍是旧字节；原源LF SHA和可逆路径映射分别记录。12项unit中成员损坏测试使用缓存的Git已核参考对象以避免重复扫描，四正常prepare/verify均实际重新核Git输入。

## 交接和未验

本轮只有L0输入准备/L1软件测试与HDL编译，没有新功能L2/数学L3/综合L4/时序L5。真实Logic/FF/DSP/BSRAM/SSRAM及物理40MHz STA均UNKNOWN/NOT_RUN，完整T060/T061仍PARTIAL。

请M2继续复核B2J/K，按最新N32/R1安排准备自己的精确资源工程；本包仅供核对输入/路径和wrapper可观测性。M3本轮不再扩写工具执行入口，不消耗额度。旧RAM不重启；新RAM 5e1d13c及精确整机组合结论不外推本候选。

初封存`B2L_20261011`按生成时内容保留，含同步新回执前的说明，不回填；更新后的最终封存为`B2L_20261011_02`。两包使用同一次真实21.406秒准备日志，没有重复编译或冒称新仿真。原暂存树门禁仅保留为旧树证据，同步M2后对最终合并树重新执行发布门禁。

任务单禁止改共享八文件，本轮状态/登记建议交M2统一处理。实际九门禁、提交号和远端身份另见外层GIT_DELIVERY.json；未发布时不得声称已上传。通知待用户转发，尚未送达。
