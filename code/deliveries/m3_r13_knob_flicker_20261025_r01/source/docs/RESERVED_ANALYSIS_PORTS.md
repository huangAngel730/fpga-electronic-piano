# 波形／频谱后续接合预留接口（R13 R02）

当前 page2/3 仅显示“待接入”，两种真实音色的波形和频谱算法均未接入。K4 仍按 CC74 数值0～60选择波形预留页、61～127选择频谱预留页；K3 CC71 的0～60/61～127选择音色0/1。最后有效K2/K4选择页面，K3不换页。

接合位置：`project/src/extension_visual/display/pro_score_display.sv` 的 `u_waveform_overlay` 具名端口。

| 端口／信号 | 域 | 定义 |
|---|---|---|
| analysis_sample_valid | core_clk 40MHz | 单拍有效，原I2S完整帧装载时刻的PCM，观察器输出晚一拍 |
| analysis_sample_seq | core_clk | 32位样本序号，随core复位归零，模2^32递增 |
| analysis_left/right | core_clk | signed24，真实I2S采用的主音量后立体声PCM，与valid/seq同拍 |
| analysis_selected_timbre | core_clk | 最近已被音频接受的合法音色0/1选择；不是单个采样只含该音色的标签 |
| analysis_page_select / analysis_view_selected | core_clk | 页号0/1/2/3；view_selected=1时为分析预留页，低位0波形/1频谱 |
| page_for_pixel | pixel_clk 25MHz | 原子页／音色邮箱，帧边界提交的实际页号 |
| waveform/spectrum_mask_aligned | pixel_clk | 未来算法返回，必须与原始光栅恰好五个捕获后像素一致 |
| waveform/spectrum_rgb_aligned | pixel_clk | 同一像素24位RGB；无mask时当前定义为黑 |

未来算法可以分别接同一实际PCM源，不需要复制合成器。持音换音色保持原音色，新NoteOn采用新选择；实际PCM也可能包含尚未松开的其他音色声部。不得把选择标签伪装成每个PCM帧的唯一音色身份。

当前 `WAVEFORM_ATTACHED=0`、`SPECTRUM_ATTACHED=0`，返回RGB/mask显式接0。未来模块完成验证后，接入返回端口并把对应静态参数设为1；采样源无ready/backpressure，显示复位不得传回音频生产者。若新算法有跨域，须自带双域安全复位／稳定数据握手，不读取层级私有寄存器。所有返回须对齐原五拍HS/VS/DE，blank最后黑，desync提示保持最终覆盖。

当前未连接的采样观察器可能被综合优化掉，这是未附接接口的正常资源裁剪，不代表算法已在硬件运行。原算法源码和此前候选/测试均保留，不能将其原回执当成本版已接合或上板通过。
