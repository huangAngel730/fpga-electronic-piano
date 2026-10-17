# Local read-only discovery receipt

- Machine: `LAPTOP-KSS1MRR7`
- Scope: file existence/hash, current PATH command discovery, and read-only
  hardware enumeration only.
- No Gowin, Programmer, ModelSim, Icarus or board operation was launched.
- Windows CIM PnP/serial queries failed before enumeration with
  `无法从客户端中访问 CIM 资源`; therefore attached-board and instrument identity
  are not established.
- Current PATH lookup did not find `gw_sh`, `programmer`, `Gowin`, `vsim` or
  `iverilog`.
- The documented `gw_sh.exe` and programmer CLI locations were absent.
- A `GowinSynthesis.exe` candidate existed at the locally expected IDE `bin`
  directory: 21,800 bytes, SHA-256
  `c116ecc6bc3d66a7e9d88082fb3e128117e2488786d31f4bd3ca11024fe8cd55`.
  It was not launched, and this receipt does not prove a complete/usable install.
- `GOWIN_HOME` and `GOWIN_PROGRAMMER_HOME` were absent.
- A license-related environment variable existed, but its value was deliberately
  not read into or stored in this package. Runtime license validity is `UNKNOWN`.

This discovery is diagnostic context, not a physical-evidence source and not an
authorization to program hardware.
