# -*- coding: utf-8 -*-
"""M1 模型层全部自检的统一入口。

在仓库根目录执行：

.. code-block:: powershell

    python -X utf8 code/model/tests/run_all.py

退出码 0 表示全部 PASS，非 0 表示有 FAIL 或 ERROR，可直接用于 CI 与
``code/docs/验证记录.md`` 的登记。``-X utf8`` 用于避免 Windows 默认 GBK
控制台把中文输出打成乱码。
"""

import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
MODEL_DIR = TESTS_DIR.parent
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(str(TESTS_DIR), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    total = result.testsRun
    failed = len(result.failures)
    errored = len(result.errors)
    skipped = len(result.skipped)
    print()
    print("=" * 68)
    if result.wasSuccessful():
        print(f"[PASS] M1 模型自检全部通过：{total} 项，跳过 {skipped} 项")
        print("       验证等级 L1（Python 参考模型自检），未涉及 RTL 与上板")
        return 0
    print(f"[FAIL] M1 模型自检未通过：{total} 项中失败 {failed}，错误 {errored}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
