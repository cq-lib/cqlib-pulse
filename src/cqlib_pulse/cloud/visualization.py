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

"""Cloud pulse-waveform visualization workflow."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, cast, runtime_checkable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..core.circuit import PulseCircuit
from ..errors import WaveformAPIError
from .auth import DEFAULT_TIANYAN_URL, TianyanAuthClient

CREATE_WAVEFORM_PATH = "/qccp-quantum/sdk/generateWaveformDiagram"
QUERY_WAVEFORM_PATH = "/qccp-quantum/sdk/getWaveformDiagram"


@runtime_checkable
class WaveformAPI(Protocol):
    """The two cloud operations needed for waveform visualization.

    :class:`TianyanWaveformClient` implements this protocol over HTTP. Other
    platform adapters and test doubles can implement the same two methods.
    """

    def create_waveform_data(
        self,
        circuit: str,
        circuit_name: str | None = None,
        is_verify: bool = True,
    ) -> int | str: ...

    def query_waveform_data(self, query_id: int | str) -> str | None: ...


@dataclass(frozen=True, slots=True)
class WaveformJob:
    """Cloud waveform-generation task identifier."""

    query_id: int | str


class TianyanWaveformClient:
    """HTTP client for the two Tianyan waveform-diagram endpoints.

    ``token`` is sent only in the request header. ``qc_code`` is serialized as
    the create endpoint's ``qcCode`` field.
    """

    def __init__(
        self,
        token: str,
        qc_code: str,
        *,
        base_url: str = DEFAULT_TIANYAN_URL,
        request_timeout_secs: float = 30,
        _token_provider: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(token, str) or not token.strip():
            raise ValueError("token must be a non-empty string")
        if not isinstance(qc_code, str) or not qc_code.strip():
            raise ValueError("qc_code must be a non-empty string")
        if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        if request_timeout_secs <= 0:
            raise ValueError("request_timeout_secs must be positive")
        self._token = token
        self.qc_code = qc_code
        self.base_url = base_url.rstrip("/")
        self.request_timeout_secs = request_timeout_secs
        self._token_provider = _token_provider

    @classmethod
    def from_api_key(
        cls,
        api_key: str,
        qc_code: str,
        *,
        base_url: str = DEFAULT_TIANYAN_URL,
        request_timeout_secs: float = 30,
    ) -> TianyanWaveformClient:
        """Log in with an API Key and retain an in-memory refresh provider."""

        auth = TianyanAuthClient(
            api_key,
            base_url=base_url,
            request_timeout_secs=request_timeout_secs,
        )
        return cls(
            auth.get_access_token(),
            qc_code,
            base_url=base_url,
            request_timeout_secs=request_timeout_secs,
            _token_provider=auth.get_access_token,
        )

    def create_waveform_data(
        self,
        circuit: str,
        circuit_name: str | None = None,
        is_verify: bool = True,
    ) -> int | str:
        if not isinstance(circuit, str) or not circuit.strip():
            raise ValueError("circuit must contain non-empty QCIS")
        payload: dict[str, object] = {
            "circuit": circuit,
            "qcCode": self.qc_code,
            "circuitName": circuit_name,
            "isVerify": is_verify,
        }
        data = self._request_json("POST", CREATE_WAVEFORM_PATH, payload=payload)
        query_id = data.get("id")
        if isinstance(query_id, bool) or not isinstance(query_id, (int, str)) or query_id == "":
            raise WaveformAPIError("Waveform creation response data.id must be an int or string")
        return query_id

    def query_waveform_data(self, query_id: int | str) -> str | None:
        if isinstance(query_id, bool) or not isinstance(query_id, (int, str)) or query_id == "":
            raise ValueError("query_id must be a non-empty integer or string")
        data = self._request_json(
            "GET",
            QUERY_WAVEFORM_PATH,
            params={"id": query_id},
        )
        url = data.get("visibleUrl")
        if url in (None, ""):
            return None
        if not isinstance(url, str):
            raise WaveformAPIError("Waveform query response data.visibleUrl must be a string")
        return url

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
        params: dict[str, int | str] | None = None,
    ) -> dict[str, object]:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        refreshed = False
        while True:
            request = Request(
                url,
                data=body,
                method=method,
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._token}",
                    "basicToken": self._token,
                    "Content-Type": "application/json",
                    "token": self._token,
                },
            )
            try:
                with urlopen(request, timeout=self.request_timeout_secs) as response:
                    result = json.loads(response.read().decode("utf-8"))
                break
            except HTTPError as exc:
                if exc.code == 401 and self._token_provider is not None and not refreshed:
                    self._token = self._token_provider()
                    refreshed = True
                    continue
                raise WaveformAPIError(
                    f"Waveform API returned HTTP {exc.code}: {exc.reason}"
                ) from exc
            except URLError as exc:
                raise WaveformAPIError(f"Unable to reach waveform API: {exc.reason}") from exc
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise WaveformAPIError("Waveform API returned invalid JSON") from exc

        if not isinstance(result, dict):
            raise WaveformAPIError("Waveform API response must be a JSON object")
        data = result.get("data")
        if not isinstance(data, dict):
            message = result.get("message") or result.get("msg") or "missing data object"
            raise WaveformAPIError(f"Waveform API request failed: {message}")
        return cast(dict[str, object], data)


class CloudPulseVisualizer:
    """Call the cloud create/query APIs and return the generated asset URL."""

    def __init__(self, api: WaveformAPI) -> None:
        self.api = api

    def create(
        self,
        circuit: PulseCircuit | str,
        *,
        circuit_name: str | None = None,
        is_verify: bool = True,
    ) -> WaveformJob:
        qcis = circuit.to_qcis() if isinstance(circuit, PulseCircuit) else circuit
        if not isinstance(qcis, str) or not qcis.strip():
            raise ValueError("circuit must contain non-empty QCIS")
        query_id = self.api.create_waveform_data(
            qcis,
            circuit_name=circuit_name,
            is_verify=is_verify,
        )
        if query_id is None or query_id == "":
            raise RuntimeError("Cloud waveform API returned an empty query id")
        return WaveformJob(query_id)

    def query(self, job: WaveformJob | int | str) -> str | None:
        query_id = job.query_id if isinstance(job, WaveformJob) else job
        return self.api.query_waveform_data(query_id)

    def wait(
        self,
        job: WaveformJob | int | str,
        *,
        timeout_secs: float = 300,
        poll_interval_secs: float = 3,
    ) -> str:
        """Poll until the cloud returns a visualization URL or timeout expires."""

        if timeout_secs <= 0 or poll_interval_secs <= 0:
            raise ValueError("timeout_secs and poll_interval_secs must be positive")
        deadline = time.monotonic() + timeout_secs
        while True:
            url = self.query(job)
            if url:
                return url
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Timed out waiting for pulse waveform visualization")
            time.sleep(min(poll_interval_secs, remaining))

    def visualize(
        self,
        circuit: PulseCircuit | str,
        *,
        circuit_name: str | None = None,
        is_verify: bool = True,
        timeout_secs: float = 300,
        poll_interval_secs: float = 3,
    ) -> str:
        """Create a cloud waveform task and wait for its visualization URL."""

        job = self.create(circuit, circuit_name=circuit_name, is_verify=is_verify)
        return self.wait(
            job,
            timeout_secs=timeout_secs,
            poll_interval_secs=poll_interval_secs,
        )
