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

"""Waveform value objects for the Tianyan QCIS pulse extension."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import IntEnum
from math import isfinite
from typing import ClassVar, cast

from ..errors import PulseValidationError, QCISParseError

Number = int | float
MAX_PULSE_LENGTH_NS = 49_984


class WaveformType(IntEnum):
    """Waveform identifiers defined by the cloud pulse protocol."""

    NUMERIC = -1
    COSINE = 0
    FLATTOP = 1
    SLEPIAN = 2


def validate_real(name: str, value: Number) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise PulseValidationError(f"{name} must be a finite real number")


@dataclass(frozen=True, slots=True, kw_only=True)
class Waveform:
    """Base waveform shared by the supported pulse instructions."""

    length: int
    amplitude: float
    waveform_type: ClassVar[WaveformType]

    @staticmethod
    def create(
        w_type: WaveformType | int,
        length: int,
        amplitude: float,
        **kwargs: object,
    ) -> Waveform:
        classes = {
            WaveformType.NUMERIC: NumericWaveform,
            WaveformType.COSINE: CosineWaveform,
            WaveformType.FLATTOP: FlattopWaveform,
            WaveformType.SLEPIAN: SlepianWaveform,
        }
        try:
            cls = classes[WaveformType(w_type)]
        except (TypeError, ValueError, KeyError) as exc:
            raise PulseValidationError(f"Unsupported waveform type: {w_type!r}") from exc
        if "samples" in kwargs and "data_list" not in kwargs:
            kwargs["data_list"] = kwargs.pop("samples")
        return cast(Waveform, cls(length=length, amplitude=amplitude, **kwargs))

    def __post_init__(self) -> None:
        if isinstance(self.length, bool) or not isinstance(self.length, int):
            raise PulseValidationError("length must be an integer")
        if not 0 <= self.length <= MAX_PULSE_LENGTH_NS:
            raise PulseValidationError(f"length must be in [0, {MAX_PULSE_LENGTH_NS}] nanoseconds")
        # Physical amplitude ranges depend on the cloud-side mapper.
        validate_real("amplitude", self.amplitude)

    def shape_parameters(self) -> tuple[Number, ...]:
        return ()

    def parameters(self) -> tuple[Number, ...]:
        return (
            int(self.waveform_type),
            self.length,
            self.amplitude,
            *self.shape_parameters(),
        )

    @property
    def data(self) -> list[Number]:
        return list(self.parameters())

    def __str__(self) -> str:
        return " ".join(_format_number(value) for value in self.parameters())

    @classmethod
    def load(cls, waveform: str | Sequence[Number], gate: str | None = None) -> Waveform:
        """Load ``waveform_id length amplitude [shape parameters...]``.

        ``gate`` is retained for source compatibility. Gate-specific fields
        are now parsed by the instruction layer, where they belong.
        """

        del gate
        try:
            values = (
                [_parse_number(item) for item in waveform.split()]
                if isinstance(waveform, str)
                else list(waveform)
            )
        except ValueError as exc:
            raise QCISParseError("Waveform parameters must be numeric") from exc
        return waveform_from_parameters(values)


@dataclass(frozen=True, slots=True, kw_only=True)
class CosineWaveform(Waveform):
    waveform_type: ClassVar[WaveformType] = WaveformType.COSINE


@dataclass(frozen=True, slots=True, kw_only=True)
class FlattopWaveform(Waveform):
    """Flat-top waveform; ``edge`` is the edge duration in nanoseconds."""

    edge: float
    waveform_type: ClassVar[WaveformType] = WaveformType.FLATTOP

    def __post_init__(self) -> None:
        super(FlattopWaveform, self).__post_init__()
        validate_real("edge", self.edge)
        if self.edge < 0:
            raise PulseValidationError("edge must be non-negative")

    def shape_parameters(self) -> tuple[Number, ...]:
        return (self.edge,)


@dataclass(frozen=True, slots=True, kw_only=True)
class SlepianWaveform(Waveform):
    thf: float
    thi: float
    lam2: float
    lam3: float
    waveform_type: ClassVar[WaveformType] = WaveformType.SLEPIAN

    def __post_init__(self) -> None:
        super(SlepianWaveform, self).__post_init__()
        for name in ("thf", "thi", "lam2", "lam3"):
            value = getattr(self, name)
            validate_real(name, value)
            if not -1 <= value <= 1:
                raise PulseValidationError(f"{name} must be in [-1, 1]")

    def shape_parameters(self) -> tuple[Number, ...]:
        return (self.thf, self.thi, self.lam2, self.lam3)


@dataclass(frozen=True, slots=True, kw_only=True)
class NumericWaveform(Waveform):
    """Arbitrary samples (I samples followed by Q samples for PXY)."""

    data_list: tuple[float, ...] = field(default_factory=tuple)
    waveform_type: ClassVar[WaveformType] = WaveformType.NUMERIC

    def __post_init__(self) -> None:
        super(NumericWaveform, self).__post_init__()
        object.__setattr__(self, "data_list", tuple(self.data_list))
        if len(self.data_list) < 3:
            raise PulseValidationError("numeric waveform requires at least 3 samples")
        for sample in self.data_list:
            validate_real("sample", sample)

    def shape_parameters(self) -> tuple[Number, ...]:
        return self.data_list

    @property
    def samples(self) -> tuple[float, ...]:
        return self.data_list


def waveform_from_parameters(parameters: Sequence[Number]) -> Waveform:
    """Deserialize a waveform and enforce its shape-specific arity."""

    if len(parameters) < 3:
        raise QCISParseError("Waveform requires id, length and amplitude")
    if isinstance(parameters[0], bool) or not isinstance(parameters[0], int):
        raise QCISParseError("Waveform id must be an integer")
    try:
        waveform_type = WaveformType(parameters[0])
    except (TypeError, ValueError) as exc:
        raise QCISParseError(f"Unsupported waveform type: {parameters[0]!r}") from exc
    raw_length = parameters[1]
    if isinstance(raw_length, bool) or int(raw_length) != raw_length:
        raise QCISParseError("Waveform length must be an integer")
    length = int(raw_length)
    amplitude = parameters[2]
    rest = list(parameters[3:])
    try:
        if waveform_type is WaveformType.COSINE:
            if rest:
                raise QCISParseError("Cosine waveform has unexpected parameters")
            return CosineWaveform(length=length, amplitude=amplitude)
        if waveform_type is WaveformType.FLATTOP:
            if len(rest) != 1:
                raise QCISParseError("Flattop waveform requires one edge parameter")
            return FlattopWaveform(length=length, amplitude=amplitude, edge=rest[0])
        if waveform_type is WaveformType.SLEPIAN:
            if len(rest) != 4:
                raise QCISParseError("Slepian waveform requires thf, thi, lam2 and lam3")
            return SlepianWaveform(
                length=length,
                amplitude=amplitude,
                thf=rest[0],
                thi=rest[1],
                lam2=rest[2],
                lam3=rest[3],
            )
        return NumericWaveform(length=length, amplitude=amplitude, data_list=tuple(rest))
    except PulseValidationError as exc:
        raise QCISParseError(str(exc)) from exc


def _parse_number(value: str) -> Number:
    parsed = float(value)
    return (
        int(parsed) if parsed.is_integer() and not any(c in value.lower() for c in ".e") else parsed
    )


def _format_number(value: Number) -> str:
    return str(value) if isinstance(value, int) else format(value, ".15g")
