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

本教程介绍如何使用 `cqlib-pulse` 构建脉冲级量子线路、生成和解析 QCIS
指令、管理通道时序，并将线路提交到天衍量子云平台执行。

## 目录

1. [安装](#1-安装)
2. [快速上手](#2-快速上手)
3. [脉冲指令](#3-脉冲指令)
4. [波形](#4-波形)
5. [时序模型与通道调度](#5-时序模型与通道调度)
6. [与标准量子门混排](#6-与标准量子门混排)
7. [QCIS 序列化与解析](#7-qcis-序列化与解析)
8. [提交到天衍平台](#8-提交到天衍平台)
9. [云端脉冲波形可视化](#9-云端脉冲波形可视化)
10. [异常处理](#10-异常处理)

---

## 1. 安装

```bash
python -m pip install cqlib-pulse
```

安装时会自动安装必需依赖 `cqlib-tianyan`，用于天衍任务提交和结果查询。

从源码安装（开发模式）：

```bash
python -m pip install -e .
```

## 2. 快速上手

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

输出：

```text
PXY Q1 0 40 0.2 5000000000 0 1
PZ G96 0 20 -0.1 1
G G96 100 -3
I Q1 20
M Q1
```

## 3. 脉冲指令

`cqlib-pulse` 支持 QCIS 脉冲控制指令集中的四条指令：

| 指令 | 作用目标 | 通道 | 时序 | 说明 |
|------|----------|------|------|------|
| `PXY` | 数据比特（`Q<n>`） | XY | 串联 | 交流脉冲，独立控制时长、幅度、频率、相位和 DRAG 系数 |
| `PZ` | 数据比特 / 耦合比特 | Z | 串联 | 直流脉冲，`call_mapper` 控制幅值映射 |
| `PZ0` | 数据比特 / 耦合比特 | Z | 并联 | 直流脉冲，不推进时间标记，可与其他脉冲叠加 |
| `G` | 耦合比特（`G<n>`） | Z | 串联 | 调控相邻数据比特间的耦合强度 |

**串联**表示后续脉冲在当前脉冲结束后开始，即脉冲独占时序；**并联**
表示脉冲叠加在同一时刻，不独占时序。

目标用 `Qubit`（数据比特）和 `CouplerQubit`（耦合比特）表示；凡是接受
目标的位置都可以直接传整数（默认解释为数据比特，仅 `g()` 解释为耦合
比特）。

### 3.1 PXY：XY 通道交流脉冲

```python
circuit.pxy(
    1,                                        # 数据比特 Q1
    CosineWaveform(length=40, amplitude=0.2), # 波形
    frequency=5e9,                            # 脉冲频率，Hz，范围 [4e9, 6e9]
    phase=0.0,                                # 边带混频相位，rad，范围 (-pi, pi]
    drag_alpha=1.0,                           # DRAG 修正系数，范围 [-10, 10]
)
```

### 3.2 PZ / PZ0：Z 通道直流脉冲

```python
# 作用于数据比特
circuit.pz(1, CosineWaveform(length=20, amplitude=-0.1), call_mapper=True)

# 作用于耦合比特
circuit.pz(CouplerQubit(96), CosineWaveform(length=20, amplitude=-0.1))

# PZ0：并联版本，不推进时间标记
circuit.pz0(1, CosineWaveform(length=30, amplitude=0.05))
```

`call_mapper`（映射开关）的含义：

- `call_mapper=True`：传入的是**频率/耦合强度**相关参数。系统先生成频率
  （或耦合强度）波形，再按标定的映射关系转换为 AWG 码值波形，波形会发生
  形变。
- `call_mapper=False`：传入的是**归一化 AWG 码值**相关参数，系统直接生成
  码值波形，不做映射转换，波形无形变。

`PZ0` 与 `PZ` 参数完全相同，区别在于时序：`PZ0` 不改变所属通道的时间
标记，其后的脉冲与它在同一时刻开始，因此多个 `PZ0` 可以叠加出复合波形。

> **注意**：由于频率偏移/耦合强度与控制码值之间的映射是非线性的，两个
> 幅度为 `A1`、`A2` 的信号叠加后的效果并不等于幅度 `A1 + A2` 的信号。
> `call_mapper=True` 时应谨慎使用 `PZ0` 进行信号叠加。

### 3.3 G：耦合强度调控

```python
circuit.g(96, length=100, coupling_strength=-3)
```

`G` 作用于耦合比特的 Z 通道，将相邻两个数据比特之间的耦合强度调节到
`coupling_strength`（单位 **MHz**）。各耦合器可调控的强度范围不同，且
由芯片标定数据决定；超出标定范围会在云端校验时报错。

> 耦合比特的编号因设备而异（例如 tianyan176 上合法的耦合编号是稀疏、
> 不连续的）。提交前请确认目标机器上存在所用的耦合比特。

### 3.4 幅度 `amplitude` 的含义

幅度参数的含义取决于目标类型和 `call_mapper`：

| 目标 | call_mapper | 幅度含义 |
|------|-------------|----------|
| 数据比特 | `True` | 相对工作点频率的比特频率偏移信号幅度，单位 Hz |
| 耦合比特 | `True` | 耦合强度控制信号幅度，单位 MHz |
| 任意 | `False` | 归一化 AWG 码值信号幅度，无量纲 |

幅度的合法区间受硬件电子学、当前工作点偏置和芯片标定数据共同约束，
本包只做基本校验（有限实数），具体范围由云端校验。平台侧的标定范围
查询接口（如耦合强度范围、比特可调频率范围）将随 SDK 后续版本提供。

## 4. 波形

四种波形通过波形编号区分，编号会出现在 QCIS 指令中：

| 类 | 编号 | 额外参数 | 说明 |
|----|------|----------|------|
| `NumericWaveform` | -1 | `data_list` | 任意数值序列 |
| `CosineWaveform` | 0 | 无 | 余弦包络 |
| `FlattopWaveform` | 1 | `edge`（ns，非负） | 平顶包络 |
| `SlepianWaveform` | 2 | `thf, thi, lam2, lam3`（均在 [-1, 1]） | Slepian 包络 |

所有波形共有的参数：

- `length`：脉冲时长，整数，单位 ns，范围 [0, 49984]；
- `amplitude`：脉冲幅度，含义见 [3.4 节](#34-幅度-amplitude-的含义)。

```python
from cqlib_pulse import FlattopWaveform, NumericWaveform, SlepianWaveform

FlattopWaveform(length=40, amplitude=0.2, edge=5)
SlepianWaveform(length=40, amplitude=0.2, thf=0.5, thi=-0.5, lam2=0.1, lam3=0.0)
```

### 4.1 numeric 波形

`NumericWaveform` 用显式数值序列描述波形：

- 对于 `PZ`/`PZ0`，`data_list` 是单通道时序信号；
- 对于 `PXY`，`data_list` 描述 I/Q 双通道信号，**前半段为 I 序列，后半段
  为 Q 序列**，因此样本数必须为偶数且不少于 6。

```python
# I = [0.1, 0.2, 0.3], Q = [-0.1, -0.2, -0.3]
wf = NumericWaveform(length=3, amplitude=1, data_list=(0.1, 0.2, 0.3, -0.1, -0.2, -0.3))
circuit.pxy(0, wf, frequency=0, phase=0, drag_alpha=0)
```

在 numeric 模式下，`PXY` 的 `frequency`/`phase`/`drag_alpha` 以及波形的
`length`/`amplitude` 均为占位参数（波形时序完全由 `data_list` 描述），
可以赋任意有限数值，但必须占位。

### 4.2 工厂方法与反序列化

```python
from cqlib_pulse import Waveform, WaveformType

w1 = Waveform.create(WaveformType.COSINE, 20, 0.3)
w2 = Waveform.create(-1, 10, 1.0, samples=[0.1, 0.2, 0.3])  # numeric，samples 是 data_list 的别名
w3 = Waveform.load("1 40 0.2 5")  # 按 "编号 length 幅度 [形状参数...]" 解析
```

## 5. 时序模型与通道调度

每个通道（数据比特或耦合比特）各自维护一个**时间标记**：

- `PXY`、`PZ`、`G` 串联添加：从时间标记处开始，结束后时间标记后移脉冲
  时长；
- `PZ0` 并联添加：从时间标记处开始，但**不移动**时间标记；
- `I` 指令（`circuit.delay()`）手动将时间标记后移指定时长；
- `B` 指令（`circuit.barrier()`）将多个通道的时间标记对齐到其中的最大
  值，实现跨通道同步。

```python
from cqlib_pulse import CosineWaveform, PulseCircuit

circuit = PulseCircuit()
circuit.pxy(0, CosineWaveform(length=40, amplitude=0.2), frequency=5e9)
circuit.pz0(0, CosineWaveform(length=10, amplitude=0.1))   # 与下一个脉冲同时开始
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

输出：

```text
PXY  [   0,   40]
PZ0  [  40,   50]
PXY  [  40,   80]
I    [  80,  100]
B    [ 100,  100]
M    [ 100,  100]
{Qubit(index=0): 100, Qubit(index=1): 100}
```

`schedule()` 返回每个操作的起止时间（`ScheduledOperation`），
`channel_times` 返回各通道的最终时刻。

## 6. 与标准量子门混排

脉冲指令可以与标准 QCIS 门混合使用：

```python
circuit = PulseCircuit()
circuit.pxy(0, CosineWaveform(length=40, amplitude=0.5), frequency=5e9, phase=0, drag_alpha=0)
circuit.x2p(0)          # 等价于 append_standard("X2P", 0)
circuit.rz(0, 1.5708)
circuit.measure(0)
```

支持的便捷方法：`x2p`、`x2m`、`y2p`、`y2m`、`xy2p(angle)`、
`xy2m(angle)`、`rz(angle)`、`cx(control, target)`、`delay/i`、
`barrier/b`、`measure`。其他 QCIS 指令可用
`circuit.append_standard(opcode, targets, parameters)` 追加。

标准门不占时长（起止时间相同），`delay` 和 `barrier` 按时序模型推进或
对齐时间标记。

## 7. QCIS 序列化与解析

```python
qcis = circuit.to_qcis()                 # 线路 -> QCIS 文本
restored = PulseCircuit.from_qcis(qcis)  # QCIS 文本 -> 线路（别名：load）
assert restored.to_qcis() == qcis
```

也可以使用模块级函数操作列表：

```python
from cqlib_pulse import qcis_dumps, qcis_loads

text = qcis_dumps(list(circuit))
operations = qcis_loads(text)
```

解析器支持 `#` 和 `//` 行注释与空行；科学计数法（如 `5e9`）可以正常
解析。格式错误的输入会抛出 `QCISParseError`，错误信息中带行号：

```python
from cqlib_pulse import QCISParseError, PulseCircuit

try:
    PulseCircuit.from_qcis("M Q0\nPXY Q0 0 40")
except QCISParseError as exc:
    print(exc)  # Line 2: PXY requires at least 6 parameters
```

## 8. 提交到天衍平台

提交和结果查询由 `cqlib-tianyan` 提供，QCIS 文本直接作为线路格式：

```python
from cqlib_tianyan import TianyanPlatform

# 首次登录（凭据默认保存到 ~/.cqlib/tianyan/，之后可用
# TianyanPlatform.from_credentials() 直接复用）
platform = TianyanPlatform.login("your-api-key")
backend = platform.get_backend("tianyan176")

task = backend.run([circuit.to_qcis()], shots=1000)
results = task.wait(timeout=3600, poll_interval=10)  # 单位均为秒
for r in results:
    print(r.counts)
```

要点：

- `backend.run()` 立即返回 `TaskHandle`，线路在云端排队；`wait()` 轮询
  直到完成或超时，超时抛出 `TimeoutError`。
- `wait()` 默认对超导设备在有校准数据时自动应用读取误差矫正；
  `task.wait_raw()` 返回原始计数。
- 每次请求最多 50 条线路，`cqlib-tianyan` 会自动分批。
- 更多能力（后端列举、设备拓扑、矫正模式等）见
  [cqlib-tianyan 文档](https://pypi.org/project/cqlib-tianyan/)。

## 9. 云端脉冲波形可视化

`cqlib-pulse` 内置了天衍波形图接口的客户端，可以在提交前预览脉冲时序图：

```python
from cqlib_pulse import CloudPulseVisualizer, TianyanWaveformClient

client = TianyanWaveformClient.from_api_key(
    api_key="your-api-key",
    qc_code="tianyan176",  # 目标机器代码
)
visualizer = CloudPulseVisualizer(client)

# 一步完成：创建 + 轮询直到生成波形图 URL
url = visualizer.visualize(circuit, circuit_name="demo")
print(url)
```

也可以拆成独立步骤手动控制：

```python
job = visualizer.create(circuit)          # 返回 WaveformJob(query_id=...)
url = visualizer.query(job)               # 未生成时返回 None
url = visualizer.wait(job, timeout_secs=300, poll_interval_secs=3)
```

`is_verify=False` 可跳过云端的线路约束校验。access token 只保存在内存
中；接口返回 401 时客户端会自动重新登录并重试一次。

## 10. 异常处理

所有异常都继承自 `PulseError`：

| 异常                           | 触发场景                               |
|------------------------------|------------------------------------|
| `PulseValidationError`       | 目标或参数非法（越界、类型错误等），同时是 `ValueError` |
| `QCISParseError`             | QCIS 文本无法解析，同时是 `ValueError`       |
| `WaveformAPIError`           | 波形接口请求失败或响应非法，同时是 `RuntimeError`   |
| `TianyanAuthenticationError` | API Key 换取 token 失败                |

```python
from cqlib_pulse import PulseError

try:
    circuit.pxy(1, CosineWaveform(length=40, amplitude=0.2), frequency=7e9)
except PulseError as exc:
    print(exc)  # frequency must be in [4e9, 6e9] Hz
```

天衍任务提交和结果查询抛出的异常来自 `cqlib_tianyan`，参见其文档。
