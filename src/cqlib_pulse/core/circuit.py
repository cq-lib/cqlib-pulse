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

"""Mixed pulse/standard circuit construction and scheduling."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from typing import TypeVar, overload

from ..errors import PulseValidationError
from .instructions import PXY, PZ, PZ0, G, PulseInstruction
from .operations import Operation, PulseOperation, ScheduledOperation, StandardOperation
from .targets import CouplerQubit, PulseTarget, Qubit
from .waveforms import MAX_PULSE_LENGTH_NS, Number, Waveform

_TargetT = TypeVar("_TargetT", Qubit, CouplerQubit)


def _targets(
    value: int | Iterable[int | _TargetT] | None,
    cls: type[_TargetT],
) -> set[_TargetT]:
    if value is None:
        return set()
    if isinstance(value, bool):
        raise PulseValidationError("Target count must be a non-negative integer")
    if isinstance(value, int):
        if value < 0:
            raise PulseValidationError("Target count must be non-negative")
        return {cls(index) for index in range(value)}
    result: set[_TargetT] = set()
    for item in value:
        if isinstance(item, bool):
            raise PulseValidationError("Target index must be a non-negative integer")
        target = cls(item) if isinstance(item, int) else item
        if not isinstance(target, cls):
            raise PulseValidationError(f"Expected {cls.__name__}, got {type(target).__name__}")
        result.add(target)
    return result


def _resolve_target(target: int | PulseTarget) -> PulseTarget:
    if isinstance(target, bool):
        raise PulseValidationError("Target index must be a non-negative integer")
    return Qubit(target) if isinstance(target, int) else target


class PulseCircuit(Sequence[Operation]):
    """An ordered circuit supporting both pulse and ordinary QCIS operations.

    The extension owns its targets and Python operation sequence independently.
    """

    def __init__(
        self,
        qubits: int | Iterable[int | Qubit] | None = None,
        coupler_qubits: int | Iterable[int | CouplerQubit] | None = None,
    ) -> None:
        self._qubits = _targets(qubits, Qubit)
        self._couplers = _targets(coupler_qubits, CouplerQubit)
        self._operations: list[Operation] = []

    def __len__(self) -> int:
        return len(self._operations)

    @overload
    def __getitem__(self, index: int) -> Operation: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[Operation]: ...

    def __getitem__(self, index: int | slice) -> Operation | Sequence[Operation]:
        return self._operations[index]

    def __iter__(self) -> Iterator[Operation]:
        return iter(self._operations)

    @property
    def qubits(self) -> tuple[Qubit, ...]:
        return tuple(sorted(self._qubits, key=lambda target: target.index))

    @property
    def coupler_qubits(self) -> tuple[CouplerQubit, ...]:
        return tuple(sorted(self._couplers, key=lambda target: target.index))

    def append(
        self,
        instruction: PulseInstruction,
        target: int | PulseTarget,
    ) -> PulseCircuit:
        return self.append_operation(PulseOperation(instruction, _resolve_target(target)))

    append_pulse = append

    def append_operation(self, operation: Operation) -> PulseCircuit:
        if not isinstance(operation, (PulseOperation, StandardOperation)):
            raise PulseValidationError("operation must be a pulse or standard operation")
        self._operations.append(operation)
        for target in operation.targets:
            if isinstance(target, Qubit):
                self._qubits.add(target)
            else:
                self._couplers.add(target)
        return self

    def append_standard(
        self,
        opcode: str,
        targets: int | PulseTarget | Iterable[int | PulseTarget],
        parameters: Iterable[Number] = (),
    ) -> PulseCircuit:
        if isinstance(targets, (int, Qubit, CouplerQubit)):
            targets = (targets,)
        resolved_targets = tuple(_resolve_target(target) for target in targets)
        return self.append_operation(StandardOperation(opcode, resolved_targets, tuple(parameters)))

    def pxy(
        self,
        qubit: int | Qubit,
        waveform: Waveform,
        *,
        frequency: float,
        phase: float = 0.0,
        drag_alpha: float = 0.0,
    ) -> PulseCircuit:
        return self.append(PXY(waveform, frequency, phase, drag_alpha), qubit)

    def pz(
        self,
        target: int | PulseTarget,
        waveform: Waveform,
        *,
        call_mapper: bool | int = False,
    ) -> PulseCircuit:
        return self.append(PZ(waveform, call_mapper), target)

    def pz0(
        self,
        target: int | PulseTarget,
        waveform: Waveform,
        *,
        call_mapper: bool | int = False,
    ) -> PulseCircuit:
        return self.append(PZ0(waveform, call_mapper), target)

    def g(
        self,
        coupler: int | CouplerQubit,
        length: int,
        coupling_strength: float,
    ) -> PulseCircuit:
        target = CouplerQubit(coupler) if isinstance(coupler, int) else coupler
        return self.append(G(length, coupling_strength), target)

    def delay(self, target: int | PulseTarget, length: int) -> PulseCircuit:
        return self.i(target, length)

    def rz(self, qubit: int | Qubit, angle: float) -> PulseCircuit:
        return self.append_standard("RZ", qubit, (angle,))

    def x2p(self, qubit: int | Qubit) -> PulseCircuit:
        return self.append_standard("X2P", qubit)

    def x2m(self, qubit: int | Qubit) -> PulseCircuit:
        return self.append_standard("X2M", qubit)

    def y2p(self, qubit: int | Qubit) -> PulseCircuit:
        return self.append_standard("Y2P", qubit)

    def y2m(self, qubit: int | Qubit) -> PulseCircuit:
        return self.append_standard("Y2M", qubit)

    def xy2p(self, qubit: int | Qubit, angle: float) -> PulseCircuit:
        return self.append_standard("XY2P", qubit, (angle,))

    def xy2m(self, qubit: int | Qubit, angle: float) -> PulseCircuit:
        return self.append_standard("XY2M", qubit, (angle,))

    def cx(
        self,
        control: int | Qubit,
        target: int | Qubit,
    ) -> PulseCircuit:
        return self.append_standard("CX", (control, target))

    def i(self, target: int | PulseTarget, length: int) -> PulseCircuit:
        """Append a QCIS ``I`` delay instruction."""

        return self.append_standard("I", target, (length,))

    def b(self, *targets: int | PulseTarget) -> PulseCircuit:
        """Append a QCIS ``B`` barrier instruction."""

        return self.append_standard("B", targets)

    def measure(self, qubit: int | Qubit) -> PulseCircuit:
        return self.append_standard("M", qubit)

    def barrier(self, *targets: int | PulseTarget) -> PulseCircuit:
        return self.b(*targets)

    def to_qcis(self) -> str:
        from ..qcis import dumps

        return dumps(self._operations)

    @classmethod
    def from_qcis(cls, qcis: str) -> PulseCircuit:
        from ..qcis import loads

        circuit = cls()
        for operation in loads(qcis):
            circuit.append_operation(operation)
        return circuit

    load = from_qcis

    def schedule(self) -> tuple[ScheduledOperation, ...]:
        """Derive channel-relative times using the pulse protocol rules."""

        clocks: dict[PulseTarget, int] = {}
        result: list[ScheduledOperation] = []
        for operation in self._operations:
            if isinstance(operation, PulseOperation):
                start = clocks.get(operation.target, 0)
                end = start + operation.instruction.duration_ns
                if operation.instruction.advances_time:
                    clocks[operation.target] = end
            elif operation.opcode == "B":
                start = max((clocks.get(target, 0) for target in operation.targets), default=0)
                end = start
                for target in operation.targets:
                    clocks[target] = start
            elif operation.opcode == "I":
                duration = _delay_duration(operation)
                start = max(clocks.get(target, 0) for target in operation.targets)
                end = start + duration
                for target in operation.targets:
                    clocks[target] = end
            else:
                start = max(clocks.get(target, 0) for target in operation.targets)
                end = start
            result.append(ScheduledOperation(operation, start, end))
        return tuple(result)

    @property
    def channel_times(self) -> dict[PulseTarget, int]:
        clocks: dict[PulseTarget, int] = {target: 0 for target in self.qubits}
        clocks.update((target, 0) for target in self.coupler_qubits)
        for scheduled in self.schedule():
            operation = scheduled.operation
            if isinstance(operation, PulseOperation) and not operation.instruction.advances_time:
                continue
            if isinstance(operation, StandardOperation) and operation.opcode not in {"I", "B"}:
                continue
            for target in operation.targets:
                clocks[target] = scheduled.end_ns
        return clocks

    def __str__(self) -> str:
        return self.to_qcis()


def _delay_duration(operation: StandardOperation) -> int:
    if len(operation.parameters) != 1:
        raise PulseValidationError("I requires exactly one length parameter")
    value = operation.parameters[0]
    if isinstance(value, bool) or not isinstance(value, int):
        raise PulseValidationError("I length must be an integer")
    if not 0 <= value <= MAX_PULSE_LENGTH_NS:
        raise PulseValidationError(f"I length must be in [0, {MAX_PULSE_LENGTH_NS}]")
    return value
