<p align="center">
  <img src="logo.png" alt="BlocSimPy logo" width="120">
</p>

<h1 align="center">BlocSimPy</h1>

<p align="center">
  A desktop block-diagram simulator built with Python and Qt — drag blocks onto a canvas,
  wire them together, and run continuous/discrete-time simulations.
</p>

## What it is

BlocSimPy is a PySide6 (Qt) desktop application: a `QGraphicsScene`-based canvas where you place
blocks, connect their ports with wires, group parts of a diagram into reusable subsystems, and run
a simulation over the resulting graph. The engine (`engine/`) is a plain Python/NumPy package with
no GUI dependency, so it can also be driven headlessly/programmatically or tested in isolation.

## Features

- **43 block types** across Math, Signal (dynamics), Discontinuities, Signal Routing, Logic,
  Sources, Sinks, I/O, and Structure — see the full list below.
- **Two solvers**: fixed-step forward Euler and classic 4th-order Runge-Kutta.
- **Algebraic-loop detection**: a real `AlgebraicLoopError` naming the blocks involved, instead of
  silently guessing an order — computed per (input, output) port pair, so it correctly recognizes
  loops broken by state (Integrator, Delay, a strictly-proper TransferFunction) instead of flagging
  every feedback loop as unresolvable.
- **Subsystems (SubGraph)**: group a diagram into a reusable block with its own named ports, a
  custom icon, and either synchronous ("Standard") or independently-clocked
  ("Threaded"/"Audio") execution.
- **Vector/bus signals**: `Mux`/`Demux` and named `BusCreator`/`BusSelector` blocks for grouping
  and splitting related signals.
- **Live audio I/O**: `AudioInput`/`AudioOutput`/`AudioRecord`/`AudioRead` blocks for real-time,
  hardware-clocked signal processing via `sounddevice`.
- **A Python Function block**: arbitrary per-timestep Python code with persistent state, for logic
  that doesn't fit an existing block.
- **"Update Diagram" pre-flight check**, a Data Inspector for viewing every Scope from the last run
  at once, CSV export, canvas annotations, undo/redo, and a searchable block palette.

### Block library

| Category | Blocks |
|---|---|
| Math | Abs, Divide, Gain, LookupTable, MathFunction, Max, Min, Modulo, Product, Saturation, Sum, Switch |
| Signal (dynamics) | Delay, Derivative, DiscreteTransferFunction, Integrator, PID, StateSpace, TransferFunction |
| Discontinuities | Backlash, DeadZone, Quantizer, RateLimiter |
| Signal Routing | BusCreator, BusSelector, Demux, Mux |
| Logic | IfElse, LogicalOperator, RelationalOperator |
| Sources | Clock, Constant, Ramp, SineWave |
| Sinks | Scope |
| I/O (audio) | AudioInput, AudioOutput, AudioRead, AudioRecord |
| Structure | InputPort, OutputPort, PythonFunction, SubGraph |

## Installation

Requires Python 3.8+.

```bash
git clone https://github.com/L-Gress/BlocSimPy.git
cd BlocSimPy
pip install -r requirements.txt
python main.py
```

## Development

```bash
pip install -r requirements-dev.txt
pytest tests/
```

The test suite runs against `engine/` (pure Python, no display needed) plus a small number of
Qt-backed tests for GUI-only logic; both run headlessly in CI-style environments.

## Building a standalone executable

```bash
pip install -r requirements-dev.txt
python build_exe_fast.py
```

Produces a one-file executable via PyInstaller (see `build_exe_fast.py` for the exact flags).

## Project layout

```
engine/       Pure-Python simulation core: block models, solvers, execution
              ordering, serialization -- no Qt dependency.
  blocks/     One file per block "kind", registered in engine/blocks/__init__.py.
  simulation/ SimulationEngine, solvers (Euler/RK4), topological sort +
              algebraic-loop detection, realtime audio/timer processors.
gui/          PySide6 UI: canvas, block/port/connection graphics items,
              dialogs, menus, and manager classes wiring it all together.
config/       Static UI/simulation configuration (colors, sizes, paths).
tests/        pytest test suite.
```

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE).
