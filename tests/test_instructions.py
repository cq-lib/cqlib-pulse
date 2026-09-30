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

import math

import pytest

from cqlib_pulse import (
    CosineWaveform,
    NumericWaveform,
    PulseCircuit,
    PulseValidationError,
)


def test_pxy_parameter_order_matches_cloud_protocol():
    circuit = PulseCircuit().pxy(
        1,
        CosineWaveform(length=40, amplitude=0.25),
        frequency=4.8e9,
        phase=math.pi,
        drag_alpha=-1.5,
    )
    assert circuit.to_qcis() == "PXY Q1 0 40 0.25 4800000000 3.14159265358979 -1.5"


def test_numeric_pxy_uses_minus_one_and_i_then_q_samples():
    waveform = NumericWaveform(
        length=3,
        amplitude=1,
        data_list=(0.1, 0.2, 0.3, -0.1, -0.2, -0.3),
    )
    qcis = PulseCircuit().pxy(0, waveform, frequency=5e9).to_qcis()
    assert qcis == "PXY Q0 -1 3 1 5000000000 0 0 0.1 0.2 0.3 -0.1 -0.2 -0.3"
    assert PulseCircuit.from_qcis(qcis).to_qcis() == qcis


@pytest.mark.parametrize("frequency", [3.9e9, 6.1e9])
def test_pxy_frequency_range(frequency):
    with pytest.raises(PulseValidationError, match="frequency"):
        PulseCircuit().pxy(
            0,
            CosineWaveform(length=10, amplitude=0.2),
            frequency=frequency,
        )


def test_numeric_pxy_requires_equal_i_and_q_sample_counts():
    waveform = NumericWaveform(
        length=3,
        amplitude=1,
        data_list=(0.1, 0.2, 0.3, 0.4, 0.5),
    )
    with pytest.raises(PulseValidationError, match="even length"):
        PulseCircuit().pxy(0, waveform, frequency=5e9)


def test_numeric_pxy_accepts_placeholder_frequency_phase_drag():
    # Protocol note i: in numeric mode the frequency/phase/DRAG fields are
    # unused placeholders and may take arbitrary finite values.
    waveform = NumericWaveform(
        length=3,
        amplitude=0,
        data_list=(0.1, 0.2, 0.3, -0.1, -0.2, -0.3),
    )
    qcis = PulseCircuit().pxy(0, waveform, frequency=0, phase=0, drag_alpha=0).to_qcis()
    assert qcis == "PXY Q0 -1 3 0 0 0 0 0.1 0.2 0.3 -0.1 -0.2 -0.3"
    assert PulseCircuit.from_qcis(qcis).to_qcis() == qcis
