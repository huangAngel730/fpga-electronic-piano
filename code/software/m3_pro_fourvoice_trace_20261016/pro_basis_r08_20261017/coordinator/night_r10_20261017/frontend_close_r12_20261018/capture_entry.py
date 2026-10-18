"""Strict R11 envelope through one per-call R12 streaming context."""
import argparse
import json
from pathlib import Path
import sys
import json_identity as ji
from capture_link_successor import DependencyContext


def process(envelope, output_dir, *, dependency_ref):
    ji.require(type(envelope) is dict and envelope.get("mode") == "PROCESS_CAPTURE",
               "R12_PREPARATION_PATH_NOT_ADAPTED")
    out = ji.safe_path(output_dir)
    ji.require(out != ji.OUTPUT and out.is_relative_to(ji.OUTPUT), "R12_ENTRY_OUTPUT_SCOPE")
    context = DependencyContext(dependency_ref)
    try:
        ji.require(set(envelope) == {"schema", "mode", "request"}
                   and envelope["schema"] == "N10_M3_UNIFIED_PIPELINE_REQUEST_V1",
                   "R12_CAPTURE_ENVELOPE")
        # Identity and parse use one bounded buffer before any role dispatch.
        # The old strict R11 validator still rechecks every receipt/closure.
        request = ji.read_verified(envelope["request"]).value
        ji.require(type(request) is dict and type(request.get("inputs")) is dict,
                   "R12_CAPTURE_REQUEST_INPUTS")
        context.io.bind(request["inputs"])
        # Include the controlling request and optional role descriptors in the
        # same per-call registry, never make a separate unbound helper cache.
        context.io.bind({"request": envelope["request"]})
        math_inputs = request.get("math_inputs", {})
        ji.require(type(math_inputs) is dict, "R12_CAPTURE_MATH_INPUTS")
        if math_inputs:
            context.io.bind(math_inputs)
        result = context.complete().process(envelope, out)
        ji.require(all(result.get(flag) is False for flag in
                       ("execution_allowed", "real_verified", "math_verified", "board_release_allowed")),
                   "R12_FALSE_AUTHORITY")
        result = {**result, "R12_private_call_chain": context.trace,
                  "R12_identity_read_metrics": dict(ji.READ_METRICS),
                  "R12_artifact_io_metrics": dict(context.io.metrics)}
        return result
    finally:
        context.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-ref", required=True, type=Path)
    parser.add_argument("--dependencies-ref", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    ji.require(sys.dont_write_bytecode and not sys.flags.optimize, "R12_REQUIRES_B_ASSERTIONS_ON")
    # Descriptor control documents themselves are observed from one bounded
    # buffer; the frozen controller must bind their identities before launch.
    envelope_ref = ji.read_control(args.request_ref).value
    dependency_ref = ji.read_control(args.dependencies_ref).value
    envelope = ji.read_verified(envelope_ref).value
    result = process(envelope, args.output, dependency_ref=dependency_ref)
    print(json.dumps({"status": result["status"], "real_verified": False,
                      "math_verified": False, "board_release_allowed": False}))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
