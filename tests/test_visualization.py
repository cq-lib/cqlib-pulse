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

import json
from urllib.error import HTTPError
from urllib.parse import parse_qs

import pytest

from cqlib_pulse import (
    CloudPulseVisualizer,
    CosineWaveform,
    PulseCircuit,
    TianyanAuthClient,
    TianyanWaveformClient,
    WaveformJob,
)
from cqlib_pulse.cloud import auth, visualization


class FakeWaveformAPI:
    def __init__(self):
        self.created = None
        self.queries = []

    def create_waveform_data(self, circuit, circuit_name=None, is_verify=True):
        self.created = (circuit, circuit_name, is_verify)
        return 42

    def query_waveform_data(self, query_id):
        self.queries.append(query_id)
        return "https://cloud.example/pulse/42" if len(self.queries) >= 2 else None


def test_cloud_visualization_uses_create_and_query_apis():
    circuit = PulseCircuit().pz(0, CosineWaveform(length=10, amplitude=0.2))
    api = FakeWaveformAPI()
    visualizer = CloudPulseVisualizer(api)

    job = visualizer.create(circuit, circuit_name="demo", is_verify=False)
    assert job == WaveformJob(42)
    assert api.created == ("PZ Q0 0 10 0.2 0", "demo", False)
    assert visualizer.wait(job, timeout_secs=1, poll_interval_secs=0.001) == (
        "https://cloud.example/pulse/42"
    )
    assert api.queries == [42, 42]


def test_waveform_client_rejects_invalid_query_id():
    client = TianyanWaveformClient("secret-token", "tianyan176")

    with pytest.raises(ValueError, match="query_id"):
        client.query_waveform_data(True)


class FakeHTTPResponse:
    def __init__(self, result):
        self.payload = json.dumps(result).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.payload


def test_api_key_is_exchanged_for_an_access_token(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeHTTPResponse({"code": 0, "data": {"access_token": "access-1"}})

    monkeypatch.setattr(auth, "urlopen", fake_urlopen)
    token = TianyanAuthClient("personal-api-key").get_access_token()

    request, timeout = requests[0]
    assert request.full_url == "https://qc.zdxlz.com/qccp-auth/oauth2/sdk/opnId"
    assert request.method == "POST"
    assert request.get_header("Authorization") == "Basic d2ViQXBwOndlYkFwcA=="
    assert parse_qs(request.data.decode("utf-8")) == {
        "grant_type": ["openId"],
        "openId": ["personal-api-key"],
        "account_type": ["member"],
    }
    assert timeout == 30
    assert token == "access-1"


def test_tianyan_http_client_uses_public_url_and_protocol_fields(monkeypatch):
    requests = []
    responses = iter(
        [
            FakeHTTPResponse({"data": {"id": 2091024341700579328}}),
            FakeHTTPResponse({"data": {"visibleUrl": "https://object.example/waveform.pkl"}}),
        ]
    )

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return next(responses)

    monkeypatch.setattr(visualization, "urlopen", fake_urlopen)
    client = TianyanWaveformClient("secret-token", "tianyan176")

    query_id = client.create_waveform_data(
        "PZ Q0 0 20 0.2 0",
        circuit_name="demo",
        is_verify=False,
    )
    url = client.query_waveform_data(query_id)

    create_request, create_timeout = requests[0]
    assert create_request.full_url == (
        "https://qc.zdxlz.com/qccp-quantum/sdk/generateWaveformDiagram"
    )
    assert create_request.method == "POST"
    assert create_request.get_header("Token") == "secret-token"
    assert create_request.get_header("Basictoken") == "secret-token"
    assert create_request.get_header("Authorization") == "Bearer secret-token"
    assert json.loads(create_request.data) == {
        "circuit": "PZ Q0 0 20 0.2 0",
        "qcCode": "tianyan176",
        "circuitName": "demo",
        "isVerify": False,
    }
    assert create_timeout == 30

    query_request, _ = requests[1]
    assert query_request.full_url == (
        "https://qc.zdxlz.com/qccp-quantum/sdk/getWaveformDiagram?id=2091024341700579328"
    )
    assert query_request.method == "GET"
    assert url == "https://object.example/waveform.pkl"


def test_client_from_api_key_refreshes_once_after_401(monkeypatch):
    access_tokens = iter(("access-1", "access-2"))
    login_count = 0
    waveform_tokens = []

    def fake_login_urlopen(request, timeout):
        nonlocal login_count
        login_count += 1
        return FakeHTTPResponse({"code": 0, "data": {"access_token": next(access_tokens)}})

    def fake_waveform_urlopen(request, timeout):
        waveform_tokens.append(request.get_header("Token"))
        if len(waveform_tokens) == 1:
            raise HTTPError(request.full_url, 401, "Unauthorized", None, None)
        return FakeHTTPResponse({"data": {"id": 42}})

    monkeypatch.setattr(auth, "urlopen", fake_login_urlopen)
    monkeypatch.setattr(visualization, "urlopen", fake_waveform_urlopen)

    client = TianyanWaveformClient.from_api_key(
        "personal-api-key",
        "tianyan176",
    )
    assert client.create_waveform_data("PZ Q0 0 20 0.2 0") == 42
    assert login_count == 2
    assert waveform_tokens == ["access-1", "access-2"]
