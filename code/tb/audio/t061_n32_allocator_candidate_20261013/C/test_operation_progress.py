"""Software-only regression: held-output log growth is not driver progress."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("c_process", Path(__file__).with_name("c_process.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ProgressTests(unittest.TestCase):
    def test_hold_spam_is_not_progress(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[4]/"output") as folder:
            path = Path(folder)/"trace.log"
            path.write_bytes(b"OP 10 2 BEGIN sample\n")
            monitor = module.OperationProgress()
            self.assertTrue(monitor.poll(path))
            with path.open("ab") as stream:
                stream.write(b"K 11 00001500 -6912 -6912 0 0 0\n"*100)
            self.assertFalse(monitor.poll(path))
            with path.open("ab") as stream:
                stream.write(b"OP 12 2 END sample\n")
            self.assertTrue(monitor.poll(path))
            self.assertFalse(monitor.poll(path))

    def test_partial_row_is_not_a_transition(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[4]/"output") as folder:
            path = Path(folder)/"trace.log"
            path.write_bytes(b"OP 10 2 BEGIN")
            monitor = module.OperationProgress()
            self.assertFalse(monitor.poll(path))
            with path.open("ab") as stream:
                stream.write(b" sample\n")
            self.assertTrue(monitor.poll(path))
            with path.open("ab") as stream:
                stream.write(b"OP 10 2 BEGIN sample\n")
            self.assertFalse(monitor.poll(path))


if __name__ == "__main__":
    unittest.main()
