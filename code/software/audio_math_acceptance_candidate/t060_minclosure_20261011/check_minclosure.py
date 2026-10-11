"""Future capture checker, never executes RTL or expands the fixture domain."""
import argparse
import gzip
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from fixtures import cancel_plan, compare, lifecycle_plan  # noqa: E402
from fsm_oracle import require  # noqa: E402
from prepare import check_import_origins, load_roms  # noqa: E402
from strict_capture import object_pairs  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--software-fixture', action='store_true')
    args = parser.parse_args()
    check_import_origins()
    plan = json.loads(args.plan.read_text(encoding='utf-8'), object_pairs_hook=object_pairs)
    roms = load_roms()
    require(plan == (lifecycle_plan() if plan.get('group') == 1 else cancel_plan(roms)),
            'MINCLOSURE_PLAN_NOT_EXACT')
    opener = gzip.open if args.capture.suffix == '.gz' else open
    with opener(args.capture, 'rt', encoding='utf-8') as stream:
        result = compare(stream, plan, roms, args.software_fixture)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
