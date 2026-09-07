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

"""Operations stored by :class:`cqlib_pulse.PulseCircuit`."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..errors import PulseValidationError
from .instructions import PulseInstruction
from .targets import CouplerQubit, PulseTarget, Qubit
from .waveforms import MAX_PULSE_LENGTH_NS, Number, validate_real

_SINGLE_QUBIT_GATES = {"X2P", "X2M", "Y2P", "Y2M"}
_PARAMETRIC_SINGLE_QUBIT_GATES = {"XY2P", "XY2M", "RZ"}


@dataclass(frozen=True, slots=True)
class PulseOperation:
    """A pulse instruction bound to one channel."""

    instruction: PulseInstruction
    target: PulseTarget

    def __post_init__(self) -> None:
        self.instruction.validate_target(self.target)

    @property
    def targets(self) -> tuple[PulseTarget, ...]:
        return (self.target,)


@dataclass(frozen=True, slots=True)
class StandardOperation:
    """A non-pulse QCIS operation retained in a mixed circuit."""

    opcode: str
    targets: tuple[PulseTarget, ...]
    parameters: tuple[Number, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "opcode", self.opcode.upper())
        object.__setattr__(self, "targets", tuple(self.targets))
        object.__setattr__(self, "parameters", tuple(self.parameters))
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", self.opcode):
            raise PulseValidationError(f"Invalid QCIS opcode: {self.opcode!r}")
        if not self.targets:
            raise PulseValidationError("A standard operation requires at least one target")
        if any(not isinstance(target, (Qubit, CouplerQubit)) for target in self.targets):
            raise PulseValidationError("Operation targets must be Qubit or CouplerQubit instances")
        for value in self.parameters:
            validate_real("operation parameter", value)
        if self.opcode in _SINGLE_QUBIT_GATES:
            self._validate_arity(1, 0)
            self._validate_data_qubits()
        elif self.opcode in _PARAMETRIC_SINGLE_QUBIT_GATES:
            self._validate_arity(1, 1)
            self._validate_data_qubits()
        elif self.opcode == "CX":
            self._validate_arity(2, 0)
            self._validate_data_qubits()
            if self.targets[0] == self.targets[1]:
                raise PulseValidationError("CX control and target must be different qubits")
        if self.opcode == "I":
            self._validate_arity(1, 1)
            if not isinstance(self.parameters[0], int):
                raise PulseValidationError("I requires one integer length parameter")
            if not 0 <= self.parameters[0] <= MAX_PULSE_LENGTH_NS:
                raise PulseValidationError(f"I length must be in [0, {MAX_PULSE_LENGTH_NS}]")
        elif self.opcode == "B":
            if self.parameters:
                raise PulseValidationError("B does not accept parameters")
        elif self.opcode == "M":
            if self.parameters:
                raise PulseValidationError("M does not accept parameters")
            self._validate_data_qubits()

    def _validate_arity(self, targets: int, parameters: int) -> None:
        if len(self.targets) != targets or len(self.parameters) != parameters:
            raise PulseValidationError(
                f"{self.opcode} requires exactly {targets} target(s) and {parameters} parameter(s)"
            )

    def _validate_data_qubits(self) -> None:
        if any(isinstance(target, CouplerQubit) for target in self.targets):
            raise PulseValidationError(f"{self.opcode} requires data-qubit targets")


Operation = PulseOperation | StandardOperation


@dataclass(frozen=True, slots=True)
class ScheduledOperation:
    """An operation with its derived channel-relative time interval."""

    operation: Operation
    start_ns: int
    end_ns: int
