# M2 Pro 同版来源绑定与观察缺口（基础 P1，2026-10-17）

状态：**PARTIAL_PENDING_PRO_MAPPING_TOOL_OR_PHYSICAL**。本包完成既有来源原件身份封存及61字段逐项静态清点，只达到L0。它不是四声基础、真实Pro功能、仿真、综合、STA或板测通过；board_release_allowed=false。

source_closure/逐字节保留P10 stage_a原94件（原MANIFEST列93个payload加MANIFEST本体）；originals/包含R05原ZIP、原INPUT_BINDING和P0/P10/NIGHT收据。没有重新执行旧P0/P10、编译、RTL、EDA或设备，没有把旧正常/负例日志重新包装为新测试。三份现行候选top/CST/SDC与该闭包本体核同。原历史收据中路径仅为原始溯源；本包SOURCE_BINDING/MANIFEST引用均为相对artifact根目录路径。

R05原ZIP而非旧staged mirror是冻结输入依据；P0已记录后者3项ROM字节差异。本包直接取P10原闭包及原ZIP，并逐SHA核验。9份ROM均附本体和SHA，未重新生成或改变数学。P10 compile.f是原R05仿真列表（legacy top + TB），不包含Pro wrapper，也不是新的Pro物理source list。模型clock_plan_sim.v自生125/25/40MHz、1000ns置lock，clkin不参与产生时钟；dvi_sim_stub.v也是仿真stub。原物理PLL文件带60K PG484/工具V1.9.10.01/device B旧header，仅为离线候选，不能签Pro GUI IP、锁定/失锁或真实网表。

完整Pro料号、device version、实际4072/4071板修订、Bank电压均保持null；4072 Rev1.10与4071f Rev1.5只是参考原理图身份。CST里P16时钟、K16复位、F15/G15键、R17 MIDI、E22/F24/G24音频为静态候选；H17高有效PA和P15 UART仍缺参考CST/电气现场闭合。不得拿旧PG484码流或旧下载额度替代。

PUBLIC_OBSERVATION_MAP.json按B1的61字段全部登记既有公开模块端口、M2待受控导出连线、M1内部待其确认映射、当前不存在四类。除bclk/ws/din/pa_en外，没有字段已在Pro外层top绑定成公开观察。模块公开口不等于Pro trace已导出。静态识别真实共同lane_tick可以同沿推进四路，未来应记录一次mask1111及帧请求ID；不造四笔错开的lane请求。应用/退休和TX采纳必须另有实观，不能从accept+1、PCM、commit或slot最终状态反推。无层级私有读授权、无新RTL端口、无M1算法改动。null的cancel_reason/config_payload维持原合同；62位config拼接只是建议，尚未写入接口。

B1/B2参考文件均逐字节核自提交f32f1210d097fbe9292a3c34bbd9f50f57e1fb81，不能因为主工作区ad2未含5aa文件而捏造不存在。引用不表示B1 metadata已认证真实来源，更不表示B2已有真实串行、HOLD/startup/finish/END。旧D3返修和P7执行器停跑保持各自原状态。

可移植校验：解压本ZIP后，直接把artifact根目录传给tools/check_binding.py；必须从独立交接回执取MANIFEST SHA，不从待校文件自行相信。示例（在解压根执行，替换尖括号内容）：

```powershell
python -B -X utf8 tools/check_binding.py --artifact-root . --expected-manifest-sha256 <independently_frozen_manifest_sha256>
```

退出0仅代表本包SHA、范围、候选null身份、9 ROM及61字段清单一致；退出2为拒收。checker不解析HDL语义、不认证作者、不证明真实逐沿日历、PLL、PCM或硬件。正确原件、source改1byte、缺ROM、混scope、冒签完整料号及路径逃逸的新软件自检仅验证这个checker，原双流另放外层selftest/，不会升级DUT等级。

M1接手：按同一原ZIP/ROM确认应用、slot、advance/effect边界和独立黄金；M3接手：保留实物/电气原件及C/D独立输入，在M2落实公开出口和有效执行许可后接真实观察。以上为交接材料准备，真人消息仍待用户转发，尚未送达。

原件ZIP：M2_PRO_SAME_VERSION_STATIC_BINDING_20261017.zip

ZIP SHA256：`931b7d2bbfd7ac056707542931101ff844b125936762748e344536d9be6c1ba2`

MANIFEST SHA256：`8591e40771946c901bab569312d8c98ca8c30a362f3a39c4f9d946f59d75c265`
