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

"""Pulse instruction value objects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import pi
from typing import ClassVar

from ..errors import PulseValidationError
from .targets import CouplerQubit, PulseTarget, Qubit
from .waveforms import MAX_PULSE_LENGTH_NS, Number, NumericWaveform, Waveform, validate_real


@dataclass(frozen=True, slots=True)
class PulseInstruction(ABC):
    opcode: ClassVar[str]

    @abstractmethod
    def validate_target(self, target: PulseTarget) -> None:
        """Validate that this instruction supports ``target``."""

    @abstractmethod
    def parameters(self) -> tuple[Number, ...]:
        """Return the instruction parameters in QCIS order."""

    @property
    @abstractmethod
    def duration_ns(self) -> int:
        """Return the duration of this instruction in nanoseconds."""

    @property
    def advances_time(self) -> bool:
        return True


@dataclass(frozen=True, slots=True)
class PXY(PulseInstruction):
    waveform: Waveform
    frequency: float
    phase: float = 0.0
    drag_alpha: float = 0.0
    opcode: ClassVar[str] = "PXY"

    def __post_init__(self) -> None:
        validate_real("frequency", self.frequency)
        validate_real("phase", self.phase)
        validate_real("drag_alpha", self.drag_alpha)
        if not 4e9 <= self.frequency <= 6e9:
            raise PulseValidationError("frequency must be in [4e9, 6e9] Hz")
        if not -pi < self.phase <= pi:
            raise PulseValidationError("phase must be in (-pi, pi]")
        if not -10 <= self.drag_alpha <= 10:
            raise PulseValidationError("drag_alpha must be in [-10, 10]")
        if isinstance(self.waveform, NumericWaveform):
            if len(self.waveform.samples) < 6 or len(self.waveform.samples) % 2:
                raise PulseValidationError("PXY numeric samples must have even length >= 6")

    def validate_target(self, target: PulseTarget) -> None:
        if not isinstance(target, Qubit):
            raise PulseValidationError("PXY can only target a data qubit")

    def parameters(self) -> tuple[Number, ...]:
        base = self.waveform.parameters()[:3]
        return (
            *base,
            self.frequency,
            self.phase,
            self.drag_alpha,
            *self.waveform.shape_parameters(),
        )

    @property
    def duration_ns(self) -> int:
        return self.waveform.length


@dataclass(frozen=True, slots=True)
class PZ(PulseInstruction):
    waveform: Waveform
    call_mapper: bool | int = False
    opcode: ClassVar[str] = "PZ"

    def __post_init__(self) -> None:
        call_mapper = self.call_mapper
        if not isinstance(call_mapper, (bool, int)) or call_mapper not in (0, 1):
            raise PulseValidationError("call_mapper must be bool, 0 or 1")
        object.__setattr__(self, "call_mapper", bool(call_mapper))

    def validate_target(self, target: PulseTarget) -> None:
        if not isinstance(target, (Qubit, CouplerQubit)):
            raise PulseValidationError("PZ requires a qubit or coupler target")

    def parameters(self) -> tuple[Number, ...]:
        base = self.waveform.parameters()[:3]
        return (*base, int(self.call_mapper), *self.waveform.shape_parameters())

    @property
    def duration_ns(self) -> int:
        return self.waveform.length


@dataclass(frozen=True, slots=True)
class PZ0(PZ):
    opcode: ClassVar[str] = "PZ0"

    @property
    def advances_time(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class G(PulseInstruction):
    length: int
    coupling_strength: float
    opcode: ClassVar[str] = "G"

    def __post_init__(self) -> None:
        if isinstance(self.length, bool) or not isinstance(self.length, int):
            raise PulseValidationError("G length must be an integer")
        if not 0 <= self.length <= MAX_PULSE_LENGTH_NS:
            raise PulseValidationError(f"G length must be in [0, {MAX_PULSE_LENGTH_NS}]")
        validate_real("coupling_strength", self.coupling_strength)

    def validate_target(self, target: PulseTarget) -> None:
        if not isinstance(target, CouplerQubit):
            raise PulseValidationError("G can only target a coupler qubit")

    def parameters(self) -> tuple[Number, ...]:
        return (self.length, self.coupling_strength)

    @property
    def duration_ns(self) -> int:
        return self.length
