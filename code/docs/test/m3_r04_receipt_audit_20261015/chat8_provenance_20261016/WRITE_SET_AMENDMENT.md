# chat8 测试临时目录写集偏差与修正

日期：2026-10-16。

## 偏差事实

`test_provenance.py` 原先在模块导入时计算：

```text
Path(__file__).resolve().parents[4]
    / "output/m3_r04_chat8_provenance_test_tmp_20261016"
```

按该文件的实际位置解析后，目标是：

```text
E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano\output\m3_r04_chat8_provenance_test_tmp_20261016
```

这不在本任务获准的两个 `chat8_provenance_20261016` 写集内。此前交接把它误记成 `code/output/...`，该文字也不准确。此次只读复核确认：真实越界目录当前存在，直接子项 0、递归子项 0、文件 0、子目录 0，即当前为空。按总控要求没有删除、移动或改写该目录。

因此，原交接中“只涉及本窗口测试路径”的表述不能解释为执行全过程都只写入两个授权目录；历史测试初始化曾创建上述仓库根目录下的空目录。

## 最小修正

仅修改本窗口 `test_provenance.py`：

- 临时父目录改为同一软件写集内的 `chat8_provenance_20261016/_test_tmp`；
- 新增 `require_test_path_in_write_set()`，路径经 `resolve()` 后必须能相对到本窗口软件目录，否则抛出 `AuditError(TEST_PATH_OUTSIDE_WRITE_SET:...)`；
- `mkdir` 只在守卫通过后执行。

未修改、删除或移动 `RUN_01`、`RUN_02`、A/C 原件及原越界空目录；没有重跑旧 6 例、A/C 核账、HDL、EDA 或硬件流程，也没有执行 Git 写操作。

## 定向验证原件

第一次调用系统 `python` 的 AST 命令退出 1；系统命中了不可执行的 WindowsApps 占位程序。原始命令及关键输出：

```text
python -c "import ast, pathlib; p=pathlib.Path('test_provenance.py'); ast.parse(p.read_text(encoding='utf-8')); print('AST_OK', p.resolve())"
exit=1
Program 'python.exe' failed to run ... WindowsApps\python.exe ... 系统无法访问此文件。
```

随后仅使用既有可用解释器完成必要检查：

```text
& 'C:\Users\songdongkuan\miniconda3\python.exe' -c "import ast, pathlib; p=pathlib.Path('test_provenance.py'); ast.parse(p.read_text(encoding='utf-8')); print('AST_OK', p.resolve())"
exit=0
AST_OK E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano\code\software\m3_r04_receipt_audit_20261015\chat8_provenance_20261016\test_provenance.py
```

路径守卫正负例使用一次定向 Python 调用，退出 0：

```text
POSITIVE_OK E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano\code\software\m3_r04_receipt_audit_20261015\chat8_provenance_20261016\_guard_probe\x
NEGATIVE_REJECTED True TEST_PATH_OUTSIDE_WRITE_SET:E:\FPGA\GAOYUNFPGA\team\fpga-electronic-piano\output\guard_must_reject
```

正例只解析路径，没有创建 `_guard_probe`；负例在任何写入前被拒绝。
