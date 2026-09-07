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

"""Qubit target value objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from ..errors import PulseValidationError

__all__ = ["CouplerQubit", "PulseTarget", "Qubit", "parse_target"]


@dataclass(frozen=True, slots=True, order=True)
class Qubit:
    """A data-qubit target, serialized as ``Q<index>`` in QCIS."""

    index: int

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 0:
            raise PulseValidationError("Qubit index must be a non-negative integer")

    def __str__(self) -> str:
        return f"Q{self.index}"


@dataclass(frozen=True, slots=True, order=True)
class CouplerQubit:
    """A coupling channel, serialized as ``G<index>`` in QCIS."""

    index: int

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 0:
            raise PulseValidationError("CouplerQubit index must be a non-negative integer")

    def __str__(self) -> str:
        return f"G{self.index}"


PulseTarget: TypeAlias = Qubit | CouplerQubit


def parse_target(value: str) -> PulseTarget:
    """Parse a QCIS target token such as ``Q3`` or ``G107``."""

    if len(value) < 2 or value[0] not in {"Q", "G"} or not value[1:].isdigit():
        raise PulseValidationError(f"Invalid pulse target: {value!r}")
    cls = Qubit if value[0] == "Q" else CouplerQubit
    return cls(int(value[1:]))
