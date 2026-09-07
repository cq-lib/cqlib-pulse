<!--
This code is part of cqlib.

Copyright (C) 2026 China Telecom Quantum Group.

This code is licensed under the Apache License, Version 2.0. You may
obtain a copy of this license in the LICENSE file in the root directory
of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.

Any modifications or derivative works of this code must retain this
copyright notice, and modified files need to carry a notice indicating
that they have been altered from the originals.
-->

# cqlib-pulse

[中文 README](README.md) | English README

[中文教程](docs/tutorial_zh_CN.md) | [English Tutorial](docs/tutorial_en.md)

`cqlib-pulse` is a standalone pulse-circuit extension for the CQLib ecosystem.
It supports Python 3.10+ and provides:

- QCIS pulse targets, waveforms, and instruction data structures;
- mixed circuit construction, QCIS serialization and parsing, and channel timelines;
- direct Tianyan submission of generated QCIS through `cqlib-tianyan`;
- cloud APIs for creating and querying pulse visualization URLs.

## Source layout

The public API is exported directly from `cqlib_pulse`:

```text
src/cqlib_pulse/
├── __init__.py          Public API exports
├── errors.py            Public exceptions
├── py.typed             PEP 561 typing marker
├── core/                Pulse domain model
│   ├── targets.py       Qubit and CouplerQubit targets
│   ├── waveforms.py     Supported waveforms
│   ├── instructions.py  PXY, PZ, PZ0, and G instructions
│   ├── operations.py    Instructions bound to targets
│   └── circuit.py       Circuit construction and scheduling
├── qcis/                QCIS protocol adapters
│   ├── parser.py        QCIS to Python objects
│   └── serializer.py    Python objects to QCIS
└── cloud/               Cloud platform adapters
    ├── auth.py          API authentication and token refresh
    └── visualization.py Cloud waveform creation and queries
```

The `qcis` and `cloud` layers depend on the structures in `core`. Network
requests are handled by the cloud layer, independently of local circuit
and QCIS operations.

## Installation and build

```bash
python -m pip install -e .
python -m pip install build
python -m build
```

Install the published package:

```bash
python -m pip install cqlib-pulse
```

Installation automatically includes the required `cqlib-tianyan` dependency
for Tianyan task submission and result retrieval. The waveform visualization
client is provided directly by this package.

## Build a circuit and generate QCIS

```python
from cqlib_pulse import CosineWaveform, CouplerQubit, PulseCircuit, Qubit

circuit = PulseCircuit()
circuit.pxy(
    Qubit(1),
    CosineWaveform(length=40, amplitude=0.2),
    frequency=5e9,
    phase=0.0,
    drag_alpha=1.0,
)
circuit.pz(
    CouplerQubit(107),
    CosineWaveform(length=20, amplitude=-0.1),
    call_mapper=True,
)
circuit.g(107, length=100, coupling_strength=-3_000_000)
circuit.delay(Qubit(1), length=20)
circuit.measure(Qubit(1))

qcis = circuit.to_qcis()
print(qcis)
```

Output:

```text
PXY Q1 0 40 0.2 5000000000 0 1
PZ G107 0 20 -0.1 1
G G107 100 -3000000
I Q1 20
M Q1
```

Parse QCIS back into a circuit with:

```python
restored = PulseCircuit.from_qcis(qcis)
# Compatibility alias: PulseCircuit.load(qcis)
```

The cloud pulse protocol uses four waveform identifiers: numeric `-1`, cosine
`0`, flattop `1`, and Slepian `2`. Frequency, phase, and DRAG are instruction
parameters of `PXY`; `call_mapper` is an instruction parameter of `PZ/PZ0`.

Circuits can also contain standard QCIS instructions:

```python
circuit.x2p(1).x2m(1).y2p(1).y2m(1)
circuit.xy2p(1, 0.25).xy2m(1, -0.25).rz(1, 1.57)
circuit.cx(1, 2).i(1, 20).b(Qubit(1), Qubit(2))
print(circuit.schedule())
print(circuit.channel_times)
```

The complete supported set is `X2P`, `X2M`, `Y2P`, `Y2M`, `XY2P`,
`XY2M`, `RZ`, `CX`, `I`, `B`, and `M`. `delay()`/`barrier()` remain as
compatibility names for `i()`/`b()`.

`PXY/PZ/G/I` advance their channel clocks, `PZ0` does not advance time, and
`B` aligns the listed channels. Machine calibration, mapping, and hardware
constraints are validated by the cloud platform.

## Submit a task and retrieve results

```python
from cqlib_tianyan import TianyanPlatform

platform = TianyanPlatform.login("...")
backend = platform.get_backend("...")
task = backend.run([circuit.to_qcis()], shots=1000)
results = task.wait(timeout_secs=3600, poll_interval_secs=10)

print(task)
print(results)
```

`PulseCircuit` is responsible only for producing QCIS. Backend selection, task
status, calibration modes, and result types come directly from
`cqlib-tianyan`, without a duplicate wrapper API.

## Cloud pulse visualization

The visualizer uses two cloud operations:

```python
create_waveform_data(circuit, circuit_name=None, is_verify=True) -> query_id
query_waveform_data(query_id) -> url | None
```

```python
from cqlib_pulse import CloudPulseVisualizer, TianyanWaveformClient

client = TianyanWaveformClient.from_api_key(
    api_key="...",
    qc_code="tianyan176",
)
visualizer = CloudPulseVisualizer(client)
url = visualizer.visualize(circuit, circuit_name="demo")
print(url)
```

The default service URL is `https://qc.zdxlz.com`. Authentication tokens are
kept in memory, and the client refreshes the token once after a 401 response.

## Contributing

The contribution process is documented in [CONTRIBUTING.md](CONTRIBUTING.md),
and the community standards are defined in
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

See [releasenotes](releasenotes/README.md) for changes in each release.

## License

Licensed under the [Apache License 2.0](LICENSE).
