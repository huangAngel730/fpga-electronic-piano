# M1 算法模型与验证目录

本目录是 M1 岗位的 Python 黄金参考模型。岗位规则见 `AGENTS.md`，
定点格式与交付说明见 `代码/docs/test/DDS参考模型与波表格式说明.md`。

对应任务：T002 Python DDS 参考模型、T003 波表和 FCW 生成脚本。

## 环境要求

Python 3.9 以上，**不需要 numpy、scipy 或任何第三方包**。
频率测量与信纳比计算全部用标准库实现，保证三个人的机器和 CI 都能直接跑。

Windows 下命令统一加 `-X utf8`，否则默认 GBK 控制台会把中文输出打成乱码。

## 常用命令

以下命令都在**仓库根目录**执行。

```powershell
# 跑全部自检，退出码 0 表示 PASS
python -X utf8 代码/model/tests/run_all.py

# 重新生成波表、FCW 表与固定 PCM 测试向量
python -X utf8 代码/model/wavetable_gen.py

# 只校验已提交的生成物与脚本是否一致，不写盘
python -X utf8 代码/model/wavetable_gen.py --check
```

改了 `wavetable_gen.py` 或它依赖的任何参数后，必须重新生成并把
`generated/` 一起提交，否则 `run_all.py` 里的
`test_committed_output_matches_script` 会 FAIL。

## 文件说明

| 文件 | 作用 |
|---|---|
| `audio_defs.py` | 全部常量与定点基元。接口 v1.0 冻结项与 M1 自定义项分开标注 |
| `dds_model.py` | DDS 黄金模型：音高换算、FCW、波表、相位累加器、PCM 转换 |
| `analysis.py` | 频率测量、信纳比、谐波失真。纯标准库，O(N) |
| `wavetable_gen.py` | 生成脚本，带 `--check` 可重复性校验 |
| `generated/` | 生成结果。**由脚本完全托管，不要手工编辑**，多放一个文件都会导致校验 FAIL |
| `tests/` | 自动判定的自检，`run_all.py` 是统一入口 |

## 给 M2 的东西在哪

`generated/` 下这几个文件是 T005 I2S 发送器自检可以直接用的：

- `pcm_ref_440hz_sine_left.hex` / `..._right.hex`：4800 个 24 位有符号 PCM
  样本，每行 6 位小写十六进制，可直接 `$readmemh`。
- `pcm_corner_left.hex` / `pcm_corner_right.hex`：14 组边界值，用来查
  符号扩展、MSB first 和 24 位有效数据加 8 位填充零这三类错位问题。

格式细节、左右声道差异的用意和判定方法见
`代码/docs/test/DDS参考模型与波表格式说明.md`。

## 改动约束

- 接口 v1.0 冻结项（48 kHz、24 位 PCM、7 位音符号等）不在本目录修改，
  流程见 `代码/docs/模块接口规范.md` 第八节。
- 改动定点格式、阈值或生成参数时，必须同步更新
  `代码/docs/test/DDS参考模型与波表格式说明.md`，并递增
  `wavetable_gen.GENERATOR_VERSION`，否则已经发给 M2 的向量无法追溯。
- 本目录不产出正式音频。正式合成通路必须在 FPGA 上，见
  `代码/docs/AI开工提示词.md` 第五节。
