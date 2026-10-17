"""New R09 lifetime/stream fixtures only, never an FPGA or general command."""
from pathlib import Path
import subprocess
import sys
import time


def spawn(mode):
    return subprocess.Popen([sys.executable, '-I', '-S', '-B', __file__, mode], creationflags=0x08000000)


def main():
    mode = sys.argv[1]
    if mode in ('normal', 'nonzero'):
        print('R09_NEW_STDOUT', flush=True)
        print('R09_NEW_STDERR', file=sys.stderr, flush=True)
        return 0 if mode == 'normal' else 7
    if mode in ('child', 'grandchild'):
        if mode == 'child':
            spawn('grandchild')
        Path(mode + '.ready').write_text('R09 owned fixture\n', encoding='ascii')
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            print('R09_LIVE_' + mode, flush=True)
            print('R09_LIVE_ERR_' + mode, file=sys.stderr, flush=True)
            time.sleep(0.02)
        Path('ESCAPED_' + mode).write_text('FAIL\n', encoding='ascii')
        time.sleep(20)
    elif mode in ('orphan', 'timeout'):
        spawn('child')
        deadline = time.monotonic() + 2
        while not Path('grandchild.ready').exists():
            if time.monotonic() > deadline:
                return 9
            time.sleep(0.01)
        print('R09_DESCENDANTS_READY', flush=True)
        if mode == 'orphan':
            return 0
        time.sleep(20)
    elif mode == 'flood':
        for _ in range(64):
            sys.stdout.write('x' * 8192)
            sys.stdout.flush()
            time.sleep(0.002)
        time.sleep(20)
    else:
        raise ValueError('FIXTURE_MODE_DENIED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
