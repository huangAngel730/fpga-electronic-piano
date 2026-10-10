"""Video behavior negative with a distinct, immutable display reference."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import run_138k_score_bram_integration_sim as parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = args.project.resolve()
    parent.prepare.validate(project)
    source = project / "inputs/sources/audio_visual_display_probe.sv"
    raw = source.read_bytes()
    marker = b"module audio_visual_display_probe"
    if raw.count(marker) != 1:
        raise ValueError("REFERENCE_DISPLAY_MODULE_NOT_UNIQUE")
    reference = raw.replace(marker, b"module reference_audio_visual_display_probe", 1)
    wrapper_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    parent_sha = parent.sha(Path(parent.__file__))
    source_sha = hashlib.sha256(raw).hexdigest()
    original_syntax = parent.syntax_copy

    def isolated_reference(name, payload):
        if name != "reference_audio_visual_top.sv":
            return original_syntax(name, payload)
        token = b"audio_visual_display_probe #"
        if payload.count(token) != 1:
            raise ValueError("REFERENCE_DISPLAY_INSTANCE_NOT_UNIQUE")
        payload = payload.replace(token, b"reference_audio_visual_display_probe #", 1)
        # The unchanged reference has its own module definition. The parent's
        # mutant touches only the DUT module file, never this appended module.
        return original_syntax(name, payload) + b"\n" + original_syntax("reference_display.sv", reference)

    parent.syntax_copy = isolated_reference
    previous_args = list(sys.argv)
    sys.argv = [parent.__file__, "--project", str(project), "--output", str(args.output),
                "--negative", "video_isolation"]
    try:
        code = parent.main()
    finally:
        sys.argv = previous_args
        parent.syntax_copy = original_syntax
    receipt = args.output.resolve() / "receipt.json"
    result = json.loads(receipt.read_bytes())
    result["distinct_reference_display"] = {
        "wrapper_SHA256": wrapper_sha, "parent_runner_SHA256": parent_sha,
        "original_display_SHA256": source_sha,
        "reference_module": "reference_audio_visual_display_probe",
        "DUT_mutation_shared_with_reference": False,
        "scope": "simulation module rename only; original RTL/ROM/project unchanged"}
    result["source_SHA256"].update({str(Path(__file__).resolve()): wrapper_sha})
    if (parent.sha(Path(parent.__file__)) != parent_sha or parent.sha(source) != source_sha
            or parent.sha(Path(__file__)) != wrapper_sha):
        result.update(passed=False, error="VIDEO_REFERENCE_SOURCE_CHANGED")
        code = 1
    receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
