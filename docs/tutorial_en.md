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

# cqlib-pulse Tutorial

This tutorial shows how to use `cqlib-pulse` to build pulse-level quantum
circuits, generate and parse QCIS instructions, manage channel timing, and
submit circuits to the Tianyan quantum cloud platform.

## Contents

1. [Installation](#1-installation)
2. [Quick start](#2-quick-start)
3. [Pulse instructions](#3-pulse-instructions)
4. [Waveforms](#4-waveforms)
5. [Timing model and channel scheduling](#5-timing-model-and-channel-scheduling)
6. [Mixing pulses with standard gates](#6-mixing-pulses-with-standard-gates)
7. [QCIS serialization and parsing](#7-qcis-serialization-and-parsing)
8. [Running on Tianyan](#8-running-on-tianyan)
9. [Cloud pulse-waveform visualization](#9-cloud-pulse-waveform-visualization)
10. [Error handling](#10-error-handling)

---

## 1. Installation

```bash
python -m pip install cqlib-pulse
```

Installation automatically includes the required `cqlib-tianyan` dependency,
which handles Tianyan task submission and result retrieval.

Editable installation from the project root (for development):

```bash
python -m pip install -e .
```

## 2. Quick start

```python
from cqlib_pulse import CosineWaveform, CouplerQubit, PulseCircuit

circuit = PulseCircuit()
circuit.pxy(
    1,
    CosineWaveform(length=40, amplitude=0.2),
    frequency=5e9,
    phase=0.0,
    drag_alpha=1.0,
)
circuit.pz(
    CouplerQubit(96),
    CosineWaveform(length=20, amplitude=-0.1),
    call_mapper=True,
)
circuit.g(96, length=100, coupling_strength=-3)
circuit.delay(1, length=20)
circuit.measure(1)

print(circuit.to_qcis())
```

Output:

```text
PXY Q1 0 40 0.2 5000000000 0 1
PZ G96 0 20 -0.1 1
G G96 100 -3
I Q1 20
M Q1
```

## 3. Pulse instructions

`cqlib-pulse` supports the four pulse-control instructions of the QCIS
instruction set:

| Instruction | Target | Channel | Timing | Description |
|-------------|--------|---------|--------|-------------|
| `PXY` | Data qubit (`Q<n>`) | XY | Serial | AC pulse with independent length, amplitude, frequency, phase and DRAG coefficient |
| `PZ` | Data qubit / coupler | Z | Serial | DC pulse; `call_mapper` toggles amplitude mapping |
| `PZ0` | Data qubit / coupler | Z | Parallel | DC pulse; does not advance the time marker and can overlap other pulses |
| `G` | Coupler (`G<n>`) | Z | Serial | Adjusts the coupling strength between adjacent data qubits |

**Serial** means a later pulse starts only after the current one ends (the
pulse owns the timeline); **parallel** means pulses overlap at the same
instant.

Targets are represented by `Qubit` (data qubit) and `CouplerQubit` (coupler).
Wherever a target is accepted you may pass a plain integer instead; it is
interpreted as a data qubit, except in `g()`, where it denotes a coupler.

### 3.1 PXY: XY-channel AC pulse

```python
circuit.pxy(
    1,                                        # data qubit Q1
    CosineWaveform(length=40, amplitude=0.2), # waveform
    frequency=5e9,                            # pulse frequency, Hz, in [4e9, 6e9]
    phase=0.0,                                # sideband mixing phase, rad, in (-pi, pi]
    drag_alpha=1.0,                           # DRAG coefficient, in [-10, 10]
)
```

### 3.2 PZ / PZ0: Z-channel DC pulses

```python
# On a data qubit
circuit.pz(1, CosineWaveform(length=20, amplitude=-0.1), call_mapper=True)

# On a coupler
circuit.pz(CouplerQubit(96), CosineWaveform(length=20, amplitude=-0.1))

# PZ0: parallel variant, does not advance the time marker
circuit.pz0(1, CosineWaveform(length=30, amplitude=0.05))
```

The meaning of `call_mapper`:

- `call_mapper=True`: you pass **frequency / coupling-strength** parameters.
  The system first generates a frequency (or coupling-strength) waveform and
  then converts it into an AWG code-value waveform through the calibrated
  mapping. The waveform is deformed by the mapping.
- `call_mapper=False`: you pass **normalized AWG code-value** parameters and
  the system generates the code-value waveform directly, with no mapping and
  no deformation.

`PZ0` takes the same parameters as `PZ`; the difference is timing. `PZ0` does
not move its channel's time marker, so the next pulse starts at the same
instant, and multiple `PZ0` pulses can stack into a composite waveform.

> **Note**: the mapping from frequency shift / coupling strength to control
> code value is nonlinear, so overlaying two signals with amplitudes `A1` and
> `A2` is not equivalent to a single signal with amplitude `A1 + A2`. Be
> careful when stacking `PZ0` pulses with `call_mapper=True`.

### 3.3 G: coupling-strength control

```python
circuit.g(96, length=100, coupling_strength=-3)
```

`G` acts on the coupler's Z channel and tunes the coupling strength between
the two adjacent data qubits to `coupling_strength` (in **MHz**). The
adjustable range differs per coupler and is determined by chip calibration;
out-of-range values are rejected by cloud-side validation.

> Coupler labels are device-specific (on tianyan176, for example, the valid
> coupler numbers are sparse and non-contiguous). Make sure the coupler you
> use exists on the target machine before submitting.

### 3.4 Meaning of `amplitude`

The interpretation of the amplitude parameter depends on the target type and
`call_mapper`:

| Target | call_mapper | Amplitude meaning |
|--------|-------------|-------------------|
| Data qubit | `True` | Qubit frequency-shift signal relative to the operating point, in Hz |
| Coupler | `True` | Coupling-strength control signal, in MHz |
| Any | `False` | Normalized AWG code value, dimensionless |

The legal amplitude range is constrained by the hardware electronics, the
current operating-point bias, and chip calibration data. This package only
performs basic checks (finite real numbers); the concrete ranges are enforced
by cloud-side validation. Platform-side calibration-range query functions
(such as the coupling-strength range and the tunable qubit-frequency range)
will be provided in a future SDK release.

## 4. Waveforms

Four waveforms are distinguished by a waveform id, which appears in the QCIS
instructions:

| Class | Id | Extra parameters | Description |
|-------|----|------------------|-------------|
| `NumericWaveform` | -1 | `data_list` | Arbitrary sample sequence |
| `CosineWaveform` | 0 | none | Cosine envelope |
| `FlattopWaveform` | 1 | `edge` (ns, non-negative) | Flat-top envelope |
| `SlepianWaveform` | 2 | `thf, thi, lam2, lam3` (each in [-1, 1]) | Slepian envelope |

Parameters shared by all waveforms:

- `length`: pulse length, integer, in ns, in [0, 49984];
- `amplitude`: pulse amplitude, see [3.4](#34-meaning-of-amplitude).

```python
from cqlib_pulse import FlattopWaveform, NumericWaveform, SlepianWaveform

FlattopWaveform(length=40, amplitude=0.2, edge=5)
SlepianWaveform(length=40, amplitude=0.2, thf=0.5, thi=-0.5, lam2=0.1, lam3=0.0)
```

### 4.1 Numeric waveforms

`NumericWaveform` describes the waveform with an explicit sample sequence:

- for `PZ`/`PZ0`, `data_list` is a single-channel time series;
- for `PXY`, `data_list` describes an I/Q dual-channel signal, with the
  **first half being the I sequence and the second half the Q sequence**, so
  the sample count must be even and at least 6.

```python
# I = [0.1, 0.2, 0.3], Q = [-0.1, -0.2, -0.3]
wf = NumericWaveform(length=3, amplitude=1, data_list=(0.1, 0.2, 0.3, -0.1, -0.2, -0.3))
circuit.pxy(0, wf, frequency=0, phase=0, drag_alpha=0)
```

In numeric mode, `frequency`/`phase`/`drag_alpha` of `PXY` and the waveform's
`length`/`amplitude` are placeholders (the time series is fully described by
`data_list`); they may hold any finite values but must be present.

### 4.2 Factory methods and deserialization

```python
from cqlib_pulse import Waveform, WaveformType

w1 = Waveform.create(WaveformType.COSINE, 20, 0.3)
w2 = Waveform.create(-1, 10, 1.0, samples=[0.1, 0.2, 0.3])  # numeric; "samples" aliases data_list
w3 = Waveform.load("1 40 0.2 5")  # parses "id length amplitude [shape parameters...]"
```

## 5. Timing model and channel scheduling

Every channel (data qubit or coupler) maintains its own **time marker**:

- `PXY`, `PZ` and `G` are appended serially: they start at the time marker,
  and the marker advances by the pulse length when they end;
- `PZ0` is appended in parallel: it starts at the time marker but does **not**
  move it;
- the `I` instruction (`circuit.delay()`) advances the marker manually by the
  given length;
- the `B` instruction (`circuit.barrier()`) aligns the markers of several
  channels to their maximum, synchronizing across channels.

```python
from cqlib_pulse import CosineWaveform, PulseCircuit

circuit = PulseCircuit()
circuit.pxy(0, CosineWaveform(length=40, amplitude=0.2), frequency=5e9)
circuit.pz0(0, CosineWaveform(length=10, amplitude=0.1))   # starts together with the next pulse
circuit.pxy(0, CosineWaveform(length=40, amplitude=0.2), frequency=5e9)
circuit.delay(0, 20)
circuit.barrier(0, 1)
circuit.measure(0)

for scheduled in circuit.schedule():
    op = scheduled.operation
    name = op.instruction.opcode if hasattr(op, "instruction") else op.opcode
    print(f"{name:4} [{scheduled.start_ns:4}, {scheduled.end_ns:4}]")

print(circuit.channel_times)
```

Output:

```text
PXY  [   0,   40]
PZ0  [  40,   50]
PXY  [  40,   80]
I    [  80,  100]
B    [ 100,  100]
M    [ 100,  100]
{Qubit(index=0): 100, Qubit(index=1): 100}
```

`schedule()` returns the start and end time of each operation
(`ScheduledOperation`); `channel_times` returns the final time of each
channel.

## 6. Mixing pulses with standard gates

Pulse instructions can be freely mixed with standard QCIS gates:

```python
circuit = PulseCircuit()
circuit.pxy(0, CosineWaveform(length=40, amplitude=0.5), frequency=5e9, phase=0, drag_alpha=0)
circuit.x2p(0)          # equivalent to append_standard("X2P", 0)
circuit.rz(0, 1.5708)
circuit.measure(0)
```

Available convenience methods: `x2p`, `x2m`, `y2p`, `y2m`, `xy2p(angle)`,
`xy2m(angle)`, `rz(angle)`, `cx(control, target)`, `delay`/`i`,
`barrier`/`b`, `measure`. Any other QCIS instruction can be appended with
`circuit.append_standard(opcode, targets, parameters)`.

Standard gates take no time (start equals end); `delay` and `barrier` advance
or align the time markers according to the timing model.

## 7. QCIS serialization and parsing

```python
qcis = circuit.to_qcis()                 # circuit -> QCIS text
restored = PulseCircuit.from_qcis(qcis)  # QCIS text -> circuit (alias: load)
assert restored.to_qcis() == qcis
```

Module-level helpers operate on operation lists:

```python
from cqlib_pulse import qcis_dumps, qcis_loads

text = qcis_dumps(list(circuit))
operations = qcis_loads(text)
```

The parser accepts `#` and `//` line comments and blank lines; scientific
notation (such as `5e9`) parses correctly. Malformed input raises
`QCISParseError` with the line number included:

```python
from cqlib_pulse import QCISParseError, PulseCircuit

try:
    PulseCircuit.from_qcis("M Q0\nPXY Q0 0 40")
except QCISParseError as exc:
    print(exc)  # Line 2: PXY requires at least 6 parameters
```

## 8. Running on Tianyan

Task submission and result retrieval are provided by `cqlib-tianyan`; the QCIS
text is used directly as the circuit format:

```python
from cqlib_tianyan import TianyanPlatform

# First login (credentials are saved to ~/.cqlib/tianyan/ by default; later
# runs can reuse them with TianyanPlatform.from_credentials())
platform = TianyanPlatform.login("your-api-key")
backend = platform.get_backend("tianyan176")

task = backend.run([circuit.to_qcis()], shots=1000)
results = task.wait(timeout=3600, poll_interval=10)  # both in seconds
for r in results:
    print(r.counts)
```

Notes:

- `backend.run()` returns a `TaskHandle` immediately while the circuits queue
  in the cloud; `wait()` polls until completion or timeout, raising
  `TimeoutError` on timeout.
- By default `wait()` applies readout error mitigation automatically for
  superconducting devices when calibration data is available;
  `task.wait_raw()` returns the raw counts.
- At most 50 circuits are accepted per request; `cqlib-tianyan` batches larger
  submissions automatically.
- For more capabilities (listing backends, device topology, calibration
  modes, and so on), see the
  [cqlib-tianyan documentation](https://pypi.org/project/cqlib-tianyan/).

## 9. Cloud pulse-waveform visualization

`cqlib-pulse` ships a client for the Tianyan waveform-diagram endpoints, so
you can preview the pulse timing diagram before submitting:

```python
from cqlib_pulse import CloudPulseVisualizer, TianyanWaveformClient

client = TianyanWaveformClient.from_api_key(
    api_key="your-api-key",
    qc_code="tianyan176",  # target machine code
)
visualizer = CloudPulseVisualizer(client)

# One call: create + poll until the waveform-diagram URL is ready
url = visualizer.visualize(circuit, circuit_name="demo")
print(url)
```

The steps can also be driven separately:

```python
job = visualizer.create(circuit)          # returns WaveformJob(query_id=...)
url = visualizer.query(job)               # None while not yet generated
url = visualizer.wait(job, timeout_secs=300, poll_interval_secs=3)
```

Pass `is_verify=False` to skip cloud-side circuit-constraint validation. The
access token is kept in memory only; if an endpoint returns 401, the client
logs in again and retries once.

## 10. Error handling

All exceptions derive from `PulseError`:

| Exception | Raised when |
|-----------|-------------|
| `PulseValidationError` | A target or parameter is invalid (out of range, wrong type, ...); also a `ValueError` |
| `QCISParseError` | QCIS text cannot be parsed; also a `ValueError` |
| `WaveformAPIError` | A waveform-API request fails or returns an invalid response; also a `RuntimeError` |
| `TianyanAuthenticationError` | The API key cannot be exchanged for a token |

```python
from cqlib_pulse import PulseError

try:
    circuit.pxy(1, CosineWaveform(length=40, amplitude=0.2), frequency=7e9)
except PulseError as exc:
    print(exc)  # frequency must be in [4e9, 6e9] Hz
```

Exceptions from task submission and result retrieval come from
`cqlib_tianyan`; see its documentation for details.
