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

"""Tianyan API-key authentication without credential persistence."""

from __future__ import annotations

import json
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..errors import TianyanAuthenticationError

DEFAULT_TIANYAN_URL = "https://qc.zdxlz.com"
LOGIN_PATH = "/qccp-auth/oauth2/sdk/opnId"
SDK_BASIC_AUTHORIZATION = "Basic d2ViQXBwOndlYkFwcA=="


class TianyanAuthClient:
    """Exchange a personal-center API Key for a short-lived access token."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_TIANYAN_URL,
        request_timeout_secs: float = 30,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("api_key must be a non-empty string")
        if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        if request_timeout_secs <= 0:
            raise ValueError("request_timeout_secs must be positive")
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.request_timeout_secs = request_timeout_secs

    def get_access_token(self) -> str:
        """Perform one login exchange and return ``data.access_token``."""

        body = urlencode(
            {
                "grant_type": "openId",
                "openId": self._api_key,
                "account_type": "member",
            }
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}{LOGIN_PATH}",
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Authorization": SDK_BASIC_AUTHORIZATION,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        result = self._send(request)
        if result.get("code", 0) != 0:
            message = result.get("message") or result.get("msg") or "unknown error"
            raise TianyanAuthenticationError(f"Tianyan login failed: {message}")

        token = result.get("access_token")
        data = result.get("data")
        if not token and isinstance(data, dict):
            token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise TianyanAuthenticationError("Tianyan login response is missing data.access_token")
        return token

    def _send(self, request: Request) -> dict[str, object]:
        try:
            with urlopen(request, timeout=self.request_timeout_secs) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise TianyanAuthenticationError(
                f"Tianyan login returned HTTP {exc.code}: {exc.reason}"
            ) from exc
        except URLError as exc:
            raise TianyanAuthenticationError(
                f"Unable to reach Tianyan login API: {exc.reason}"
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TianyanAuthenticationError("Tianyan login API returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise TianyanAuthenticationError("Tianyan login response must be a JSON object")
        return cast(dict[str, object], result)
