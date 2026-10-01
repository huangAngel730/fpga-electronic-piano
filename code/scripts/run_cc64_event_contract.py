#!/usr/bin/env python3
"""Verify released v1.6 CC64 public events and M3 contract compatibility."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]

def main():
    stage = ROOT / 'code/output/cc64_event_contract'
    stage.mkdir(parents=True, exist_ok=True)
    cad = Path(os.environ.get('YOSYSHQ_ROOT', 'D:/Gowin/oss-cad-suite'))
    quote = lambda value: '"' + str(value) + '"'
    binary = stage / 'tb.vvp'
    compile_args = [cad / 'bin/iverilog.exe', '-g2012', '-s', 'tb_cc64_public', '-o', binary,
                    ROOT / 'code/rtl/common/audio_defs_pkg.sv',
                    ROOT / 'code/rtl/board/sustain_control_contract_pkg.sv',
                    ROOT / 'code/tb/common/tb_cc64_event_contract.sv']
    driver = stage / 'run.bat'
    driver.write_bytes(('@echo off\r\ncall ' + quote(cad / 'environment.bat') + ' >nul\r\n'
                        + ' '.join(map(quote, compile_args)) + '\r\nif errorlevel 1 exit /b 1\r\n'
                        + quote(cad / 'bin/vvp.exe') + ' ' + quote(binary)
                        + '\r\nexit /b %errorlevel%\r\n').encode('ascii'))
    result = subprocess.run(['cmd.exe', '/c', str(driver)], cwd=stage, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=60)
    (stage / 'run.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    print(result.stdout)
    if result.returncode or 'PASS CC64 public events=32768' not in result.stdout:
        print(result.stderr, file=sys.stderr)
        return result.returncode or 1
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, subprocess.TimeoutExpired) as error:
        print('FAIL CC64 public event contract:', error, file=sys.stderr)
        raise SystemExit(1)