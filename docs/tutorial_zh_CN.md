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

# cqlib-pulse 中文教程

## 安装

在项目根目录执行：

```bash
python -m pip install -e .
```

安装时会自动安装 `cqlib-tianyan`，用于天衍任务提交和结果查询。

## 构建脉冲线路

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
    CouplerQubit(107),
    CosineWaveform(length=20, amplitude=-0.1),
    call_mapper=True,
)
circuit.g(107, length=100, coupling_strength=-3_000_000)
circuit.delay(1, length=20)
circuit.measure(1)
```

## 转换和解析 QCIS

```python
qcis = circuit.to_qcis()
print(qcis)

restored = PulseCircuit.from_qcis(qcis)
print(restored.schedule())
print(restored.channel_times)
```

`schedule()` 返回各操作的起止时间，`channel_times` 返回各通道的最终时刻。

## 提交到天衍平台

```python
from cqlib_tianyan import TianyanPlatform

platform = TianyanPlatform.login("your-api-key")
backend = platform.get_backend("your-machine-name")
task = backend.run([circuit.to_qcis()], shots=1000)
results = task.wait(timeout_secs=3600, poll_interval_secs=10)
print(results)
```
