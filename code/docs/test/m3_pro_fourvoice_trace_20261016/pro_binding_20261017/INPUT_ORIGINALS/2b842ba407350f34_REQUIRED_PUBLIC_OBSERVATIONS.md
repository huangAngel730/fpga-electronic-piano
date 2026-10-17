# B2需要的公开观察及B1对接差额

上午pro_monitor_20261017原CSV共29列，pre-NBA，同一40MHz逐沿cycle/epoch，ID十六进制，PCM signed24十进制。现有result元组和commit元组不能证明TX何帧实际采纳。

本包仅要求新只读接入记录，不变更正式公共端口：

- 与每个CSV frame_tick同一cycle/epoch的公开TX采样记录：帧ID、采样有效位、实际采纳请求ID（0合法）、TX实际左/右PCM24和clip；启动/无新数据的静音、HOLD身份语义必须明确。
- B1的独立接受/取消及返回/提交账本，供(域/epoch/帧级ID)核身份与严格<833拍、下一真实frame期限；lane级ID与帧级ID不能直接互换。
- M1同源只读PCM/clip期待与source/ROM/input/trace SHA；不能从观测result/commit生成黄金。
- 观测采样合同与source/ROM清单，CSV原件SHA及成功退出/完整MONITOR_END日志；实际串行bclk/ws/din必须逐沿原值，不能补零或从PCM反造。

适配层保留原行号/cycle/epoch和来源，不把commit投射为TX采样、不迁用D3不同事件语义。若缺采样记录或独立黄金，入口拒收/PENDING；现有上午监视器自检串行引脚人工0只作新拒收适配测试，不作真实或诊断串行正例。缺新Pro到件不等待沉默授权、不伪造映射。
