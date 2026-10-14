"""New real-seal drift guards using software-only verification fixtures."""
import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import a_delivery as delivery


RELATIVE = "code/software/t061_allocator_reference_candidate_20261013"
QUALIFIER = RELATIVE + "/a_qualify_diagnostic.py"
REPO = Path(__file__).resolve().parents[3]


class DeliveryBindingTests(unittest.TestCase):
    def setUp(self):
        # The test also runs from a deep, immutable qualification capsule.
        # Keep its disposable seal fixture outside that frozen source tree so
        # Windows path limits and source-member checks remain deterministic.
        qualification = Path.cwd().resolve().parent
        if Path.cwd().name == "frozen" and (qualification / "qualification_manifest.json").is_file():
            temporary_parent = qualification / "test_tmp"
        else:
            temporary_parent = REPO / "code/output"
        temporary_parent.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=temporary_parent, prefix="n32dg_")
        self.root = Path(self.temporary.name)
        self.here = self.root / RELATIVE
        self.here.mkdir(parents=True)
        self.prepared = self.root / "code/output/prepared"
        self.capsule = self.prepared / "capsule"
        self.qualification = self.root / "code/output/qualification"
        self.qualification.mkdir(parents=True)
        self.receipt = self.qualification / "child/receipt.json"
        self.receipt.parent.mkdir()
        self.receipt.write_bytes(b'{"status":"SOFTWARE_TEST_PASS"}\n')
        self.log = self.qualification / "parent/child.stderr.bin"
        self.log.parent.mkdir()
        self.log.write_bytes(b"original verified software log\n")
        self.frozen_worker = self.qualification / "frozen" / RELATIVE / "worker.py"
        self.frozen_worker.parent.mkdir(parents=True)
        self.frozen_worker.write_bytes(b"# original tested worker\n")
        self.plan_path = self.prepared / "plan.json"
        self.target = self.here / "SEALED_TEST_ONLY"
        self.poison_marker = self.root / "POISON_EXECUTED"

    def tearDown(self):
        self.temporary.cleanup()

    def make(self, drift=None):
        evidence = {str(self.receipt): self.receipt.read_bytes(),
                    str(self.log): self.log.read_bytes(),
                    str(self.frozen_worker): self.frozen_worker.read_bytes()}
        mutator = ""
        if drift is not None:
            path = {"receipt": self.receipt, "log": self.log,
                    "frozen_source": self.frozen_worker}[drift]
            mutator = f"    Path({str(path)!r}).write_bytes(b'UNVERIFIED_AFTER_VALIDATE')\n"
        verifier = (
            "import json\nfrom pathlib import Path\n"
            "def encoded(v): return (json.dumps(v,sort_keys=True)+'\\n').encode('utf-8')\n"
            "def validate_qualification(root, archived_sources):\n"
            f"    evidence={evidence!r}\n"
            + mutator +
            "    return {'receipt': {'tests_run': 20}, 'manifest': {'fixture': True},\n"
            "            'source_bytes': dict(archived_sources), 'evidence_bytes': evidence}\n"
        ).encode("utf-8")
        raws = {RELATIVE + "/README_A.md": b"fixture README\n",
                RELATIVE + "/worker.py": self.frozen_worker.read_bytes(), QUALIFIER: verifier}
        inputs, capsule_files = {}, {}
        for relative, raw in raws.items():
            live = self.root / relative
            live.parent.mkdir(parents=True, exist_ok=True)
            live.write_bytes(raw)
            frozen = self.capsule / relative
            frozen.parent.mkdir(parents=True, exist_ok=True)
            frozen.write_bytes(raw)
            inputs[str(live)] = delivery.digest(raw)
            capsule_files[relative] = {**delivery.digest(raw), "source_provenance": str(live)}
            qualified = self.qualification / "frozen" / relative
            qualified.parent.mkdir(parents=True, exist_ok=True)
            qualified.write_bytes(raw)
        self.plan = {"capsule_root": str(self.capsule), "inputs": inputs,
                     "capsule_files": capsule_files}
        self.plan_path.write_bytes(delivery.encode(self.plan))

    def seal(self, diff_side_effect=None):
        def under_output(path):
            resolved = Path(path).resolve()
            self.assertTrue(resolved.is_relative_to(self.root / "code/output"))
            return resolved

        def fake_diff(paths, expected):
            self.assertEqual(set(paths), set(expected))
            if diff_side_effect:
                diff_side_effect()
            return b"software fixture binary-safe diff placeholder\n", {"path": "NOT_RUN_SOFTWARE_FIXTURE"}

        with patch.object(delivery, "HERE", self.here), \
                patch.object(delivery.a_harness, "ROOT", self.root), \
                patch.object(delivery.a_harness, "verify", return_value=self.plan), \
                patch.object(delivery.a_harness, "under_output", side_effect=under_output), \
                patch.object(delivery, "binary_diff", side_effect=fake_diff):
            return delivery.seal(self.plan_path, self.target, "SOFTWARE-SEAL-GUARD-R01",
                                 [self.qualification], qualification=self.qualification)

    def write_execution_pair(self):
        output = str(self.root / "code/output/actual")
        config = {"plan": delivery.digest(self.plan_path.read_bytes()),
                  "execution_output": output}
        config_path = self.plan_path.parent / "compile_diagnostic.json"
        config_path.write_bytes(delivery.encode(config))
        worker = self.capsule / (RELATIVE + "/worker.py")
        source = delivery.digest(worker.read_bytes())
        launch = {
            "plan": {"path": str(self.plan_path), **delivery.digest(self.plan_path.read_bytes())},
            "config": {"path": str(config_path), **delivery.digest(config_path.read_bytes())},
            "capsule": str(self.capsule), "cwd": str(self.capsule),
            "python": {"path": "C:/Python/python.exe", "bytes": 1, "sha256": "0" * 64},
            "worker_argv": ["C:/Python/python.exe", "worker"],
            "worker": {"path": str(worker), **source},
            "launcher": {"path": str(worker), **source},
            "parent_output": output + "_parent",
        }
        launch_path = self.plan_path.parent / "diagnostic_launch.json"
        launch_path.write_bytes(delivery.encode(launch))
        return config_path, launch_path

    def test_poison_verifier_bytes_never_execute(self):
        self.make()
        poisoned = (f"from pathlib import Path\nPath({str(self.poison_marker)!r}).write_bytes(b'EXECUTED')\n").encode()
        (self.capsule / QUALIFIER).write_bytes(poisoned)
        with self.assertRaisesRegex(ValueError, "SEAL_CAPSULE_DRIFT|QUALIFIER_RAW_SHA"):
            self.seal()
        self.assertFalse(self.poison_marker.exists())
        self.assertFalse(self.target.exists())

    def test_unchanged_real_seal_archives_verified_cache(self):
        self.make()
        result = self.seal()
        self.assertEqual(result["state"], "SEALED-UNCOMMITTED")
        raw = base64.b64decode((self.target / "snapshot.zip.b64").read_bytes())
        with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
            name = "evidence/qualification/parent/child.stderr.bin"
            self.assertEqual(bundle.read(name), b"original verified software log\n")
            self.assertNotIn(b"UNVERIFIED_AFTER_VALIDATE", b"".join(
                bundle.read(name) for name in bundle.namelist()))

    def test_execution_pair_is_bound_and_archived(self):
        self.make()
        config, launch = self.write_execution_pair()
        self.seal()
        raw = base64.b64decode((self.target / "snapshot.zip.b64").read_bytes())
        with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
            self.assertEqual(bundle.read("execution/compile_diagnostic.json"), config.read_bytes())
            self.assertEqual(bundle.read("execution/diagnostic_launch.json"), launch.read_bytes())
            manifest = json.loads(bundle.read("MANIFEST.json"))
            self.assertEqual(manifest["execution_artifacts"]["config"],
                             delivery.digest(config.read_bytes()))
            self.assertEqual(manifest["execution_artifacts"]["launch"],
                             delivery.digest(launch.read_bytes()))

    def test_validate_return_then_receipt_drift_rejected(self):
        self.make("receipt")
        with self.assertRaisesRegex(ValueError, "PATCH_CACHED_BYTES_DRIFT"):
            self.seal()
        self.assertFalse(self.target.exists())

    def test_validate_return_then_log_drift_rejected(self):
        self.make("log")
        with self.assertRaisesRegex(ValueError, "PATCH_CACHED_BYTES_DRIFT"):
            self.seal()
        self.assertFalse(self.target.exists())

    def test_validate_return_then_frozen_source_drift_rejected(self):
        self.make("frozen_source")
        with self.assertRaisesRegex(ValueError, "PATCH_CACHED_BYTES_DRIFT"):
            self.seal()
        self.assertFalse(self.target.exists())

    def test_changes_patch_read_then_drift_rejected(self):
        self.make()
        with self.assertRaisesRegex(ValueError, "PATCH_CACHED_BYTES_DRIFT"):
            self.seal(lambda: self.log.write_bytes(b"changed while path diff was collected"))
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
