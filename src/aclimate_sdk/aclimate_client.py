from __future__ import annotations

import asyncio
import atexit
import time
import logging
from typing import Any

from aclimate_sdk.aclimate_auth_error import AClimateAuthError
from aclimate_sdk.aclimate_api_error import AClimateAPIError

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)

class AClimateClient:
    """
    Async AClimate v3 client (api.aclimate.org).

    Use Keycloak client credentials for M2M authentication.
    The token is automatically renewed before expiring.
    """

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout

        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "AClimateClient":
        self._http = httpx.AsyncClient(
            timeout=self._timeout,
            headers={"Content-Type": "application/json"},
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    # ── Auth ─────────────────────────────────────────────────────────────────

    async def _fetch_token(self) -> None:
        """Obtain a new token via client credentials (POST /auth/get-client-token)."""
        assert self._http, "Client not initialized — use async with"
        logger.debug("Fetching new Keycloak token for client %s", self._client_id)

        response = await self._http.post(
            f"{self.base_url}/auth/get-client-token",
            json={"client_id": self._client_id, "client_secret": self._client_secret},
        )

        if response.status_code != 200:
            raise AClimateAuthError(
                f"Keycloak auth failed ({response.status_code}): {response.text}"
            )

        data = response.json()
        self._token = data.get("access_token") or data.get("token")
        if not self._token:
            raise AClimateAuthError(f"No access_token in response: {data}")

        expires_in = data.get("expires_in", 300)
        self._token_expires_at = time.monotonic() + expires_in - 60
        logger.debug("Token obtained, expires in %ds", expires_in)

    async def _ensure_token(self) -> str:
        """Returns valid token, renewing it if expired."""
        if not self._token or time.monotonic() >= self._token_expires_at:
            await self._fetch_token()
        assert self._token
        return self._token

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def get(self, path: str, **params: Any) -> Any:
        """
        GET to API v3. Query parameters as kwargs.
        Returns parsed JSON.
        """
        assert self._http, "Client not initialized — use async with"
        token = await self._ensure_token()

        clean_params = {k: v for k, v in params.items() if v is not None}
        logger.debug("GET %s params=%s", path, clean_params)

        response = await self._http.get(
            f"{self.base_url}{path}",
            params=clean_params,
            headers={"Authorization": f"Bearer {token}"},
        )

        if response.status_code == 401:
            self._token = None
            token = await self._ensure_token()
            response = await self._http.get(
                f"{self.base_url}{path}",
                params=clean_params,
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code >= 400:
            raise AClimateAPIError(response.status_code, response.text[:500])

        return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=True,
    )
    async def post(self, path: str, json_body: dict[str, Any]) -> Any:
        """
        POST to API v3. Mainly used for GeoServer point-data.
        """
        assert self._http, "Client not initialized — use async with"
        token = await self._ensure_token()

        logger.debug("POST %s body=%s", path, json_body)

        response = await self._http.post(
            f"{self.base_url}{path}",
            json=json_body,
            headers={"Authorization": f"Bearer {token}"},
        )

        if response.status_code == 401:
            self._token = None
            token = await self._ensure_token()
            response = await self._http.post(
                f"{self.base_url}{path}",
                json=json_body,
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code >= 400:
            raise AClimateAPIError(response.status_code, response.text[:500])

        return response.json()


# ── SHARED CLIENT LIFECYCLE ───────────────────────────────────────────────────

_client: AClimateClient | None = None
_client_lock = asyncio.Lock()
_client_started = False


async def get_client(
    base_url: str,
    client_id: str,
    client_secret: str,
    timeout: float = 30.0,
) -> AClimateClient:
    """
    Returns a shared initialized client.
    Initializes it lazily on first use.
    """
    global _client, _client_started

    if _client is not None and _client_started:
        return _client

    async with _client_lock:
        if _client is not None and _client_started:
            return _client

        client = AClimateClient(
            base_url=base_url,
            client_id=client_id,
            client_secret=client_secret,
            timeout=timeout,
        )
        await client.__aenter__()

        _client = client
        _client_started = True
        logger.info("AClimateClient initialized lazily")
        return _client


async def close_client() -> None:
    global _client, _client_started

    if _client is not None and _client_started:
        try:
            await _client.__aexit__(None, None, None)
            logger.info("AClimateClient closed successfully")
        except Exception:
            logger.exception("Error closing AClimateClient")
        finally:
            _client = None
            _client_started = False


def _close_client_at_exit() -> None:
    """
    Sync wrapper for graceful shutdown on process exit.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return
        loop.run_until_complete(close_client())
    except Exception:
        pass


atexit.register(_close_client_at_exit)