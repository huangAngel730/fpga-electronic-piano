# PDF 与原理图分析工具

这些脚本用于从厂商原理图 PDF 中提取引脚、频率、器件型号等硬件事实。
电力子/FPGA 项目的板级事实经常只存在于 PDF 原理图里，而原理图往往
无法用文本方式直接复制，本目录提供几种逐级深入的提取手段。

**不需要 PyMuPDF、poppler 或 Ghostscript**，只用 Python 标准库加
`Pillow` / `numpy`（多数脚本甚至不用）。

---

## 使用顺序

按成本从低到高依次尝试，前一个失败再用下一个：

```
1. extract_pdf_text.py        ← 先试这个，最简单
2. extract_pdf_table.py       ← 手册/表格类 PDF，需要保住行列关系
3. analyze_pdf_fonts.py       ← 上一步乱码时，诊断原因
4. expand_pdf_objstm.py       ← 确认文字/图片到底在哪
5. extract_schematic_text.py  ← 文字在 ObjStm 里时用这个
6. extract_pdf_images.py      ← 原理图含位图时用这个
7. render_pdf_page.py         ← 最后手段，自己光栅化
```

---

## 各脚本说明

### `extract_pdf_text.py`

最基础的文本提取。解析 PDF 的 FlateDecode 流，抓取 `Tj` / `TJ`
操作符中的字符串。

```powershell
python -X utf8 code/scripts/tools/extract_pdf_text.py <pdf> [关键字...]
```

不带关键字时输出全部文本片段；带关键字时输出匹配片段及其前后文。

**局限**：若 PDF 使用自定义编码的字体子集且无 `ToUnicode` 映射，
提取出来是乱码。这是 CAD 导出 PDF 的常见情况。

**另一个局限：它按内容流顺序输出，会打散表格。** 数据手册里的参数表
使用绝对坐标定位每个字形，内容流顺序与视觉顺序无关，结果是数值和标签
可能相隔几十行，参数表完全不可读。这种情况改用 `extract_pdf_table.py`。

### `extract_pdf_table.py`

**读数据手册参数表专用。** 按坐标把字形聚类成行，再按水平间距切成
单元格，最后用 `|` 分隔输出，保住行列关系。

```powershell
python -X utf8 code/scripts/tools/extract_pdf_table.py <pdf>
```

工作原理：

1. 解析 `Tm` / `Td` / `TD` 得到每个字形的绝对坐标
2. 按 Y 坐标聚类成行（容差 2.5 pt）
3. 行内按 X 排序，相邻字形水平间距超过 8 pt 就断开为新单元格

**为什么需要单独一个脚本**：很多数据手册把**每个字形单独定位**（不是
每次都整串定位），所以"一个字符串 = 一个单元格"的假设不成立，会把
`TIMING` 拆成 6 行单字母。本脚本按几何间距合并，不依赖字符串边界。

**判读提示**：本脚本对所有内容流生效，多栏排版（如正文与参数表并排）
会被混在同一行里，表现为 `左栏内容 | 右栏内容`。参数表本身通常仍可读，
但需要人眼分辨哪些单元格属于同一张表。

### `analyze_pdf_fonts.py`

诊断"为什么提取出来是乱码"。统计对象类型，检查是否存在
`/ToUnicode` CMap 与字体对象。

```powershell
python -X utf8 code/scripts/tools/analyze_pdf_fonts.py <pdf>
```

判读方法：

- `/ToUnicode` 存在 → 可以用 CMap 还原，改用 `extract_schematic_text.py`
- `/Font` 数为 0 且 `/ToUnicode` 为 0 → 文字是矢量图形（已转曲），
  **文本路线走不通**，只能走渲染路线
- `/Image` 数量大 → 可能含内嵌位图，试 `extract_pdf_images.py`

### `expand_pdf_objstm.py`

PDF 1.5 以后很多对象被压缩进 `ObjStm` 对象流，直接扫描未压缩区会
误判为"什么都没有"。本脚本展开所有 `ObjStm`，统计其中真正的
图片、字体、页面资源数量。

```powershell
python -X utf8 code/scripts/tools/expand_pdf_objstm.py <pdf>
```

**关键价值**：`extract_pdf_text.py` 说"没有文字"时，
本脚本可能发现字体其实在 ObjStm 里。两者结论冲突时以本脚本为准。

### `extract_schematic_text.py`

针对"字体在 ObjStm 里"的情况。展开 ObjStm 后解析 `ToUnicode` CMap，
再用映射表还原 `<hex> Tj` 形式的文本。

```powershell
python -X utf8 code/scripts/tools/extract_schematic_text.py <pdf> [关键字...]
```

支持 `beginbfchar` 与 `beginbfrange` 两种 CMap 形式。

### `extract_pdf_images.py`

导出 PDF 内嵌的位图。

```powershell
python -X utf8 code/scripts/tools/extract_pdf_images.py <pdf> <输出目录> [最小宽度]
```

按面积降序保存为 PNG，最宽的通常是原理图主体。

**局限**：只处理位图 XObject。纯矢量原理图导出 0 张图，属正常现象，
不代表脚本出错。

### `render_pdf_page.py`

最后手段：自己解释 PDF 内容流并光栅化成 PNG。

```powershell
python -X utf8 code/scripts/tools/render_pdf_page.py <pdf> <输出.png> [页号] [缩放]
```

实现了一个简化的 PDF 图形解释器，支持路径构造（`m l c v y re h`）、
描边填充（`S s f F B b n`）、图形状态（`q Q cm w J j d`）和颜色
操作符。

**重要局限，使用前务必了解**：

- **贝塞尔曲线用直线近似**。原理图里曲线用得少（多为直角连线），
  一般够用；但圆弧、器件外形会失真。
- **文本不渲染**。PDF 的文字绘制需要嵌入字体的字形轮廓程序，
  本脚本不实现。**渲染结果里没有文字标注**，只有线条。
- **多页归属不判断**。所有内容流叠在一张画布上，多页 PDF 会重叠。
- **MediaBox 取最大者**。多页尺寸不同时可能选错，需手动指定缩放。

因此本脚本的定位是"看线条走向和器件位置"，**不适合用来读标注文字**。
若需要读文字，正确做法是用有图形界面的 PDF 阅读器打开，
或安装 `PyMuPDF`（`pip install pymupdf`）后渲染。

---

## 实战记录：Tang Mega 60K 原理图（2026-09-12）

这是本目录脚本的第一次实际使用，结论如下，供后续参考。

**目标**：查明板载晶振频率。

**过程与结果**：

| 步骤 | 脚本 | 结果 |
|---|---|---|
| 1 | `extract_pdf_text.py` | 提取出 4343 个片段，**全部乱码** |
| 2 | `analyze_pdf_fonts.py` | `/ToUnicode` = 0，`/Font` = 0，判定为矢量图形 |
| 3 | `expand_pdf_objstm.py` | 推翻上一步：ObjStm 中 `/Font` = 210，文字其实存在 |
| 4 | `extract_schematic_text.py` | 找到 0 个 CMap，**字体无 ToUnicode 映射，无法还原** |
| 5 | `extract_pdf_images.py` | 仅 1 个图片对象，原理图为纯矢量 |
| 6 | `render_pdf_page.py` | 成功渲染 33807 段路径，但**无文字**，且当时模型不支持读图 |

**最终结论**：该 PDF 的文字使用**无 ToUnicode 映射的自定义编码字体**，
文本提取与自建渲染两条路都走不通。

**实际解决方式**：查板卡丝印。用户查看后确认为 **50 MHz**。

**经验教训**：

1. **`/Font` 数为 0 不代表没有文字**，必须先用 `expand_pdf_objstm.py`
   展开对象流再判断。本目录的脚本顺序就是为这个教训设计的。
2. **CAD 导出的原理图 PDF 大概率无法文本提取**。Silkscreen（丝印）
   和官方例程仓库往往比原理图 PDF 更快得到答案。
3. **性价比最高的办法常常是问有实物的人看一眼**，而不是花大量
   时间在 PDF 逆向提取上。本次在 PDF 上投入的时间远超收益。

**交叉验证来源**：官方例程的 `.cst` 文件给出了引脚分配与电平标准
（`sys_clk` = V22 / LVCMOS33，`sys_rst_n` = AA13 / LVCMOS15），
这比原理图 PDF 更直接可靠。该文件已入库为
`code/constraints/tang_mega_60k_reference.cst`。

---

## 实战记录二：PT8211 数据手册（2026-09-12）

**目标**：查明板载 DAC 的数据格式与时序参数，判断能否用标准 I2S 驱动。

**过程与结果**：

| 步骤 | 脚本 | 结果 |
|---|---|---|
| 1 | `extract_pdf_text.py` | 提取 987 个片段，**文字完整可读**，无乱码 |
| 2 | 同上（关键字检索） | 找到 `TIMING CHARACTERISTI`，但数值与标签错位 |
| 3 | `extract_pdf_table.py`（新写） | **成功还原参数表行列关系**，取得全部参数 |

**结论**：该手册文字层完整，与 Sipeed 原理图的情况**完全相反**。所以
"CAD 导出 PDF 读不出字"这个教训**不能推广到数据手册**——芯片厂商的
手册通常用标准排版工具生成，文字层是好的。

**关键教训**：

1. **先试最简单的脚本，不要预设失败。** 上次原理图失败的经历很容易
   让人以为"PDF 都读不出来"，从而放弃手册这条最可靠的路。
2. **表格必须按坐标提取。** 内容流顺序对表格无效，这是本目录新增
   `extract_pdf_table.py` 的直接原因。
3. **数据手册的一手参数无法替代。** 本次先拿到的是商城参数页的二手
   转录（只够判断格式），原版手册随后补齐了全部时序、电平和模拟指标，
   并暴露出二手来源没提到的 THD 上限。

**取得的参数**：`Fbck ≤ 18.4 MHz`、`Fws ≤ 384 kHz`、`tH ≥ 25 ns`、
`VIH ≥ 1.8 V`、THD 典型 0.13%。手册已入库为
`code/docs/PT8211_V1.7_E_数据手册.pdf`，结论见
`code/docs/板级硬件事实.md` §3.7。

**仍未解决**：手册**不含时序波形图的文字描述**——图是矢量绘制的，
`extract_pdf_table.py` 只能取到图上的标注文字，取不到波形本身的
几何关系。因此 BCK/WS 的精确相位关系需靠手册正文的文字描述
（"WS 低电平时 DIN 右移入寄存器"）推断，或上板实测确认。

---

## 依赖

```powershell
python -m pip install Pillow numpy
```

`analyze_pdf_fonts.py`、`expand_pdf_objstm.py`、`extract_schematic_text.py`
仅用标准库，无需安装任何东西。
