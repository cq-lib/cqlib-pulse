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

"""Public exceptions raised by :mod:`cqlib_pulse`."""


class PulseError(Exception):
    """Base exception for this package."""


class PulseValidationError(PulseError, ValueError):
    """A pulse target or parameter is invalid."""


class QCISParseError(PulseError, ValueError):
    """A QCIS source line cannot be parsed as a supported pulse command."""


class WaveformAPIError(PulseError, RuntimeError):
    """The cloud waveform API request or response is invalid."""


class TianyanAuthenticationError(WaveformAPIError):
    """An API Key cannot be exchanged for a Tianyan access token."""
