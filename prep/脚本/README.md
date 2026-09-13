# Word 文档生成脚本

本目录中的 Python 文件用于生成或更新 `prep/` 与 `prep/文档/` 下的 Word 报告。脚本依赖 `python-docx`，运行时显式使用 UTF-8。

## 运行方式

建议从仓库根目录执行：

```powershell
python -m pip install python-docx
python .\prep\脚本\build_team_roles_resource_plan.py
```

部分旧脚本使用相对输出路径。运行前先检查文件顶部的 `OUTPUT`、`OUT` 或 `Path(...)` 定义；若脚本按 `prep/` 为工作目录设计，则执行：

```powershell
Set-Location 准备
python .\脚本\脚本名.py
```

## 脚本与主要输出

| 脚本 | 主要用途或输出 |
|---|---|
| `build_team_roles_resource_plan.py` | 生成 `文档/06 三人分工与软硬件资源管理方案.docx` |
| `build_modular_main_plan.py` | 生成模块化主方案 |
| `build_gaoyun_topic2_report.py` | 生成高云选题二完整分析 |
| `build_gaoyun_topic2_purchase_guide.py` | 生成购买与准备清单 |
| `build_ai_tang_mega_workflow_report.py` | 生成 AI 全程开发协作方案 |
| `build_simple_peripheral_list.py` | 生成外设模块清单 |
| `build_board_team_plan.py` | 生成开发板配置与团队协作原稿 |
| `build_fpga_award_report.py` | 生成赛题对比报告 |
| `add_costs_to_fpga_report.py` | 为报告补充成本信息 |
| `rebuild_compatible_docx.py` | 重构兼容版 OOXML 文档 |

## 修改规则

- 生成型 Word 优先改脚本，不只改 `.docx`。
- 覆盖已有输出前检查是否存在人工补充；不确定时先备份。
- 新增脚本时在本文件和 `prep/文档/00_README.txt` 登记输出。
- 生成后至少检查 DOCX ZIP 结构，并进行页面渲染检查。

