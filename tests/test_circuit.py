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

import pytest

from cqlib_pulse import (
    CosineWaveform,
    CouplerQubit,
    PulseCircuit,
    PulseValidationError,
    QCISParseError,
    Qubit,
    StandardOperation,
)


def test_build_and_round_trip_protocol_qcis():
    circuit = PulseCircuit(qubits=[0], coupler_qubits=[107])
    circuit.pxy(
        0,
        CosineWaveform(length=40, amplitude=0.2),
        frequency=5e9,
        phase=0.1,
        drag_alpha=-0.2,
    )
    circuit.pz(
        CouplerQubit(107),
        CosineWaveform(length=20, amplitude=-0.1),
        call_mapper=True,
    )
    circuit.g(107, 100, -3_000_000.5)

    expected = "PXY Q0 0 40 0.2 5000000000 0.1 -0.2\nPZ G107 0 20 -0.1 1\nG G107 100 -3000000.5"
    assert circuit.to_qcis() == expected
    assert PulseCircuit.load(expected).to_qcis() == expected
    assert circuit.qubits == (Qubit(0),)
    assert circuit.coupler_qubits == (CouplerQubit(107),)


def test_mixed_standard_and_pulse_qcis_round_trip():
    qcis = "X2P Q0\nRZ Q0 1.25\nI Q0 20\nPZ0 Q0 0 10 0.2 0\nB Q0 Q1\nM Q0"
    circuit = PulseCircuit.from_qcis(qcis)
    assert circuit.to_qcis() == qcis
    assert isinstance(circuit[0], StandardOperation)


def test_all_supported_standard_qcis_builders_and_round_trip():
    circuit = (
        PulseCircuit()
        .x2p(0)
        .x2m(0)
        .y2p(0)
        .y2m(0)
        .xy2p(0, 0.25)
        .xy2m(0, -0.5)
        .rz(0, 1.25)
        .cx(0, 1)
        .i(0, 20)
        .b(Qubit(0), Qubit(1), CouplerQubit(107))
    )

    expected = (
        "X2P Q0\n"
        "X2M Q0\n"
        "Y2P Q0\n"
        "Y2M Q0\n"
        "XY2P Q0 0.25\n"
        "XY2M Q0 -0.5\n"
        "RZ Q0 1.25\n"
        "CX Q0 Q1\n"
        "I Q0 20\n"
        "B Q0 Q1 G107"
    )
    assert circuit.to_qcis() == expected
    assert PulseCircuit.from_qcis(expected).to_qcis() == expected


def test_delay_and_barrier_compatibility_names_match_qcis_names():
    legacy = PulseCircuit().delay(0, 12).barrier(0, 1)
    qcis_named = PulseCircuit().i(0, 12).b(0, 1)

    assert legacy.to_qcis() == qcis_named.to_qcis() == "I Q0 12\nB Q0 Q1"


def test_append_standard_resolves_integer_targets():
    circuit = PulseCircuit().append_standard("X2P", 0)
    circuit.append_standard("CX", (0, Qubit(1)))

    assert circuit.to_qcis() == "X2P Q0\nCX Q0 Q1"
    assert circuit.qubits == (Qubit(0), Qubit(1))


@pytest.mark.parametrize(
    "factory",
    [
        lambda: PulseCircuit(True),
        lambda: PulseCircuit(qubits=[True]),
        lambda: PulseCircuit().x2p(True),
        lambda: PulseCircuit().append_standard("X2P", True),
    ],
)
def test_boolean_is_not_accepted_as_a_target_index(factory):
    with pytest.raises(PulseValidationError, match="Target"):
        factory()


def test_standard_operation_rejects_non_target_objects():
    with pytest.raises(PulseValidationError, match="Operation targets"):
        StandardOperation("X2P", ("Q0",))  # type: ignore[arg-type]


def test_pz0_does_not_advance_channel_time_but_delay_does():
    circuit = PulseCircuit()
    circuit.pz0(0, CosineWaveform(length=30, amplitude=0.2))
    circuit.delay(0, 20)
    circuit.pz(0, CosineWaveform(length=10, amplitude=0.1))

    assert [(item.start_ns, item.end_ns) for item in circuit.schedule()] == [
        (0, 30),
        (0, 20),
        (20, 30),
    ]
    assert circuit.channel_times == {Qubit(0): 30}


def test_public_qubit_is_owned_by_cqlib_pulse():
    assert Qubit.__module__ == "cqlib_pulse.core.targets"
    circuit = PulseCircuit().pz(Qubit(3), CosineWaveform(length=10, amplitude=0.2))
    assert circuit.to_qcis() == "PZ Q3 0 10 0.2 0"


def test_parse_ignores_comments_and_blank_lines():
    circuit = PulseCircuit.from_qcis("# demo\nPZ Q2 0 10 0.2 1 // pulse\n")
    assert circuit.to_qcis() == "PZ Q2 0 10 0.2 1"


def test_target_rules_are_enforced():
    waveform = CosineWaveform(length=10, amplitude=0.2)
    with pytest.raises(PulseValidationError, match="data qubit"):
        PulseCircuit().pxy(CouplerQubit(1), waveform, frequency=5e9)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "qcis",
    [
        "G Q0 10 20",
        "PZ Q0 99 10 0.2 0",
        "PZ Q0 0 10 0.2 0.5",
        "PXY Q0 0 10 0.2",
        "I Q0 10 extra",
        "X2P Q0 0.5",
        "X2M Q0 Q1",
        "Y2P G0",
        "Y2M Q0 0.5",
        "XY2P Q0",
        "XY2M Q0 0.1 0.2",
        "RZ Q0",
        "CX Q0",
        "CX Q0 Q0",
        "CX Q0 G1",
        "B Q0 1",
    ],
)
def test_invalid_qcis_reports_line(qcis):
    with pytest.raises(QCISParseError, match="Line 1"):
        PulseCircuit.from_qcis(qcis)
