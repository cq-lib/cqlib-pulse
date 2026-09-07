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


def test_layered_imports_and_top_level_api_are_available():
    from cqlib_pulse import PulseCircuit as PublicCircuit
    from cqlib_pulse.cloud import CloudPulseVisualizer
    from cqlib_pulse.core import PulseCircuit
    from cqlib_pulse.qcis import dumps, loads

    assert PublicCircuit is PulseCircuit
    assert PulseCircuit.__module__ == "cqlib_pulse.core.circuit"
    assert CloudPulseVisualizer.__module__ == "cqlib_pulse.cloud.visualization"
    assert dumps(loads("X2P Q0")) == "X2P Q0"
