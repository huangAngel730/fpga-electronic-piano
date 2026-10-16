"""Read public trace only; no claim that caller's bytes came from R05."""
import argparse
import json
from pathlib import Path
import sys
from common import Refusal, sha
from public_ledger import analyze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    try:
        data = args.capture.read_bytes()
        result = analyze(data)
        result.update({"capture_sha256": sha(data), "scope": "SOFTWARE_PUBLIC_LEDGER_ONLY_NO_SOURCE_ATTESTATION"})
        print(json.dumps(result))
        return 0
    except (Refusal, OSError, ValueError, TypeError, AttributeError) as exc:
        print(json.dumps({"status": "REJECTED", "diagnostic": getattr(exc, "code", "CAPTURE_PARSE"), "detail": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
