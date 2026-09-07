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

"""Parse QCIS text into pulse and standard operations."""

from __future__ import annotations

import re

from ..core.instructions import PXY, PZ, PZ0, G, PulseInstruction
from ..core.operations import Operation, PulseOperation, StandardOperation
from ..core.targets import parse_target
from ..core.waveforms import Number, waveform_from_parameters
from ..errors import PulseValidationError, QCISParseError

_TARGET = re.compile(r"[QG][0-9]+")


def loads(qcis: str) -> list[Operation]:
    operations: list[Operation] = []
    for line_number, raw_line in enumerate(qcis.splitlines(), start=1):
        line = re.sub(r"(#|//).*", "", raw_line).strip()
        if not line:
            continue
        try:
            operations.append(_parse_line(line))
        except (PulseValidationError, QCISParseError, ValueError) as exc:
            raise QCISParseError(f"Line {line_number}: {exc}") from exc
    return operations


def _parse_line(line: str) -> Operation:
    parts = line.split()
    if len(parts) < 2:
        raise QCISParseError("Incomplete QCIS instruction")
    opcode = parts[0].upper()
    if opcode in {"PXY", "PZ", "PZ0", "G"}:
        if len(parts) < 3:
            raise QCISParseError("Incomplete pulse instruction")
        target = parse_target(parts[1])
        values = [_parse_number(token) for token in parts[2:]]
        instruction = _parse_pulse(opcode, values)
        return PulseOperation(instruction, target)

    target_end = 1
    while target_end < len(parts) and _TARGET.fullmatch(parts[target_end]):
        target_end += 1
    if target_end == 1:
        raise QCISParseError(f"{opcode} requires at least one Q/G target")
    targets = tuple(parse_target(token) for token in parts[1:target_end])
    parameters = tuple(_parse_number(token) for token in parts[target_end:])
    return StandardOperation(opcode, targets, parameters)


def _parse_pulse(opcode: str, values: list[Number]) -> PulseInstruction:
    if opcode == "G":
        if len(values) != 2 or isinstance(values[0], float):
            raise QCISParseError("G requires an integer length and coupling strength")
        return G(values[0], values[1])
    fixed = 6 if opcode == "PXY" else 4
    if len(values) < fixed:
        raise QCISParseError(f"{opcode} requires at least {fixed} parameters")
    if opcode == "PXY":
        waveform = waveform_from_parameters([*values[:3], *values[6:]])
        return PXY(waveform, values[3], values[4], values[5])
    waveform = waveform_from_parameters([*values[:3], *values[4:]])
    call_mapper = values[3]
    if not isinstance(call_mapper, int):
        raise QCISParseError(f"{opcode} call_mapper must be 0 or 1")
    cls: type[PZ] = PZ if opcode == "PZ" else PZ0
    return cls(waveform, call_mapper)


def _parse_number(value: str) -> Number:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise QCISParseError(f"Expected a numeric parameter, got {value!r}") from exc
    if parsed.is_integer() and not any(c in value.lower() for c in ".e"):
        return int(parsed)
    return parsed
