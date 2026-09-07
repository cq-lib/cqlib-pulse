# This code is part of cqlib.
#
# Copyright (C) 2026 China Telecom Quantum Group.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Standalone Python pulse module for CQLib."""

from importlib.metadata import version as _distribution_version

from .cloud import (
    CloudPulseVisualizer,
    TianyanAuthClient,
    TianyanWaveformClient,
    WaveformAPI,
    WaveformJob,
)
from .core import (
    PXY,
    PZ,
    PZ0,
    CosineWaveform,
    CouplerQubit,
    FlattopWaveform,
    G,
    NumericWaveform,
    Operation,
    PulseCircuit,
    PulseInstruction,
    PulseOperation,
    PulseTarget,
    Qubit,
    ScheduledOperation,
    SlepianWaveform,
    StandardOperation,
    Waveform,
    WaveformType,
)
from .errors import (
    PulseError,
    PulseValidationError,
    QCISParseError,
    TianyanAuthenticationError,
    WaveformAPIError,
)
from .qcis import dumps as qcis_dumps
from .qcis import loads as qcis_loads

__version__ = _distribution_version("cqlib-pulse")

__all__ = [
    "CloudPulseVisualizer",
    "CosineWaveform",
    "CouplerQubit",
    "FlattopWaveform",
    "G",
    "NumericWaveform",
    "Operation",
    "PulseCircuit",
    "PulseError",
    "PulseInstruction",
    "PulseOperation",
    "PulseTarget",
    "PulseValidationError",
    "PXY",
    "PZ",
    "PZ0",
    "QCISParseError",
    "Qubit",
    "SlepianWaveform",
    "ScheduledOperation",
    "StandardOperation",
    "TianyanAuthClient",
    "TianyanAuthenticationError",
    "TianyanWaveformClient",
    "Waveform",
    "WaveformAPI",
    "WaveformAPIError",
    "WaveformJob",
    "WaveformType",
    "qcis_dumps",
    "qcis_loads",
]
