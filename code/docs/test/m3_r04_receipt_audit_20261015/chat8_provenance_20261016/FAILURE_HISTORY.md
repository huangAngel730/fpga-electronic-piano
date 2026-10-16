# 失败历史

首次软件测试在 2026-10-16 使用 Python `tempfile.TemporaryDirectory()` 的系统沙盒临时目录，六例均因该目录拒绝创建测试文件而报 `PermissionError`，测试逻辑没有开始，退出码 1。修法只把测试临时父目录改到仓库的 `code/output/m3_r04_chat8_provenance_test_tmp_20261016/`；没有提高时限、换解释器或改待核 A/C 原件。

该失败属于执行环境路径权限，不是 A/C 来源链判定失败。原控制台双流由当前对话工具回执保留；后续正式运行另存独立双流和退出码。

首次真实原件核验读到 A 的封存收据后，以 `KeyError: archive`、退出码 1 停止。原因是 A 收据把 ZIP 字段命名为 `package`，C 收据使用 `archive`；两者都带路径、字节数和 SHA。最小修法是明确接受这两个既有字段名，后续仍以实际 ZIP 和 manifest 内容核验，不放宽身份或结果判据。失败时尚未创建最终结果文件。
