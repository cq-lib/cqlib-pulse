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

中文 README | [English README](README_EN.md)

[中文教程](docs/tutorial_zh_CN.md) | [English Tutorial](docs/tutorial_en.md)

`cqlib-pulse` 是一个支持 Python 3.10+、面向 CQLib 生态的独立脉冲线路扩展包，提供：

- QCIS 脉冲目标、波形和指令数据结构；
- `PulseCircuit` 混合线路构建、QCIS 序列化/反序列化和通道时间线；
- 将生成的 QCIS 通过 `cqlib-tianyan` 直接提交到天衍平台；
- 调用云平台的创建、查询接口取得脉冲可视化 URL。


## 源码架构

源码按职责分为三层，使用者通常只需要从顶层 `cqlib_pulse` 导入：

```text
src/cqlib_pulse/
├── __init__.py          对外统一导出稳定 API
├── errors.py            公共异常
├── py.typed             PEP 561 类型标记
├── core/                Python 脉冲领域模型
│   ├── targets.py       Qubit/CouplerQubit 目标
│   ├── waveforms.py     四种波形
│   ├── instructions.py  PXY/PZ/PZ0/G 指令
│   ├── operations.py    指令与目标的绑定
│   └── circuit.py       线路构建和时间调度
├── qcis/                QCIS 协议适配层
│   ├── parser.py        QCIS -> Python 对象
│   └── serializer.py    Python 对象 -> QCIS
└── cloud/               外部云平台适配层
    ├── auth.py          API Key 登录与 token 刷新
    └── visualization.py 云端波形创建和查询
```

`qcis` 和 `cloud` 都建立在 `core` 数据结构之上；`PulseCircuit` 仅在执行
转换方法时延迟调用 QCIS 适配层。云平台代码不会进入波形、指令等基础
数据结构，QCIS 文本处理也不负责网络请求。

## 安装和构建

```bash
python -m pip install -e .
python -m pip install build
python -m build
```

安装发布包：

```bash
python -m pip install cqlib-pulse
```

安装时会自动安装必需依赖 `cqlib-tianyan`，用于天衍任务提交和结果查询。
脉冲可视化客户端由本包直接提供。

## 构建线路并转 QCIS

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

输出：

```text
PXY Q1 0 40 0.2 5000000000 0 1
PZ G107 0 20 -0.1 1
G G107 100 -3000000
I Q1 20
M Q1
```

反向解析使用：

```python
restored = PulseCircuit.from_qcis(qcis)
# 兼容旧入口：PulseCircuit.load(qcis)
```

云平台脉冲协议的四种波形编号是：数值型 `-1`、余弦型 `0`、
平顶型 `1`、Slepian 型 `2`。`PXY` 的频率、相位和 DRAG 参数属于
指令；`PZ/PZ0` 的 `call_mapper` 也属于指令，而不是波形。

线路也可以保留普通 QCIS 指令：

```python
circuit.x2p(1).x2m(1).y2p(1).y2m(1)
circuit.xy2p(1, 0.25).xy2m(1, -0.25).rz(1, 1.57)
circuit.cx(1, 2).i(1, 20).b(Qubit(1), Qubit(2))
print(circuit.schedule())       # 每条操作的 start_ns / end_ns
print(circuit.channel_times)    # 每个通道的最终时刻
```

当前完整支持 `X2P`、`X2M`、`Y2P`、`Y2M`、`XY2P`、`XY2M`、`RZ`、
`CX`、`I`、`B` 和 `M`。`delay()`/`barrier()` 是 `i()`/`b()` 的兼容名称。

`PXY/PZ/G/I` 推进对应通道时间，`PZ0` 不推进时间，`B` 对齐所列通道。
机器标定值、映射关系和数值波形的硬件约束仍由云平台校验，本地只进行
与公开协议一致的结构和基础数值检查。

## 提交任务并取得结果

```python
from cqlib_tianyan import TianyanPlatform

platform = TianyanPlatform.login("...")
backend = platform.get_backend("...")
task = backend.run([circuit.to_qcis()], shots=1000)
results = task.wait(timeout_secs=3600, poll_interval_secs=10)

print(task)
print(results)
```

`PulseCircuit` 只负责生成 QCIS；设备选择、任务状态、校准模式和结果类型均由
`cqlib-tianyan` 直接提供，避免重复包装其 API。

## 云端脉冲可视化

可视化对象只依赖云平台的两个操作：

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

默认客户端地址为 `https://qc.zdxlz.com`。创建接口发送 `circuit`、
`qcCode`、`circuitName`、`isVerify`，查询接口根据任务 ID 返回响应中的
`data.visibleUrl`。API Key 用于登录换取 access token，token 只保存在
内存并以天衍兼容的 `basicToken`、`Authorization: Bearer` 请求头发送；
如果接口返回 401，客户端只自动刷新重试一次。

## 参与贡献

贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)，社区行为规范见
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

各版本变更记录见 [releasenotes](releasenotes/README.md)。

## 许可证

本项目采用 [Apache License 2.0](LICENSE)。
