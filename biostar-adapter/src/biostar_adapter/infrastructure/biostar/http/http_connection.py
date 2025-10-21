"""
This module provides the BiostarHttpConnection class for managing asynchronous HTTP connections to the Biostar API.
It handles authentication, session management, and client lifecycle, enabling secure and efficient communication with Biostar services.
"""

import json
import logging
import pathlib
from types import TracebackType
from typing import Optional, Type

import httpx

from biostar_adapter.common.utility import LoggerMixin


class BiostarHttpConnection(LoggerMixin):
    """
    Manages an asynchronous HTTP connection to the Biostar API, including authentication,
    session management, and client lifecycle. Provides context manager support for automatic cleanup.
    """

    _client: Optional[httpx.AsyncClient] = None
    _session_token: Optional[str] = None
    _biostar_endpoint: Optional[str] = None

    def __init__(
        self,
        *,
        biostar_endpoint: str,
        session_token: str,
        logger: logging.Logger,
    ) -> None:
        """
        Initialize the BiostarHttpConnection with endpoint, session token, and logger.
        Sets up the HTTPX AsyncClient with the appropriate headers.
        """
        self._biostar_endpoint = biostar_endpoint
        self._session_token = session_token
        self._build_logger(logger=logger)
        self._client = httpx.AsyncClient(
            base_url=biostar_endpoint,
            verify=False,  # TODO: Change to True in production
            headers=self._headers,
        )

    @classmethod
    async def create(
        cls,
        *,
        biostar_endpoint: str,
        username: str,
        password: str,
        logger: logging.Logger,
    ) -> "BiostarHttpConnection":
        """
        Asynchronously creates a BiostarHttpConnection instance by authenticating with the Biostar API.
        Attempts to load a cached session token first; if valid, uses it. Otherwise, logs in normally and caches the token.
        Logs in using the provided username and password, retrieves the session token, and returns an instance.
        Raises RuntimeError if authentication fails or session token is missing.
        """
        biostar_endpoint = (
            f"https://{biostar_endpoint.strip('/')}"  # Ensure URL is well-formed
        )

        cache_dir = pathlib.Path("./cache")
        cache_dir.mkdir(exist_ok=True)
        cache_file = cache_dir / "session_cache.json"

        # Try to load cached session
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    data = json.load(f)
                if data.get("endpoint") == biostar_endpoint:
                    cached_token = data.get("session_token")
                    if cached_token:
                        # Validate cached token
                        test_client = httpx.AsyncClient(
                            base_url=biostar_endpoint,
                            verify=False,
                            headers={"bs-session-id": cached_token},
                            timeout=5.0,
                        )
                        try:
                            response = await test_client.get("/api/users")
                            if response.status_code == 200:
                                logger.info("Using cached session token")
                                await test_client.aclose()
                                return cls(
                                    biostar_endpoint=biostar_endpoint,
                                    session_token=cached_token,
                                    logger=logger,
                                )
                            else:
                                logger.debug(
                                    f"Cached token invalid, status: {response.status_code}"
                                )
                        except Exception as e:
                            logger.debug(f"Error validating cached token: {e}")
                        finally:
                            await test_client.aclose()
            except Exception as e:
                logger.debug(f"Error loading cache: {e}")

        # Proceed with normal login
        authentication_client = httpx.AsyncClient(
            base_url=biostar_endpoint, verify=False
        )
        credentials = {"User": {"login_id": username, "password": password}}

        logger.debug("Sending login request to Biostar endpoint.")

        response = await authentication_client.post(
            "/api/login",
            json=credentials,
        )

        if response.status_code != 200:
            logger.error(
                f"Failed to login to Biostar: {response.status_code} {response.text}"
            )
            await authentication_client.aclose()
            raise RuntimeError(
                f"Failed to login to Biostar: {response.status_code} {response.text}"
            )

        session_token = response.headers.get("bs-session-id")

        logger.debug(f"Received session token: {session_token}")

        if not session_token:
            logger.error("bs-session-id header not found in response")
            await authentication_client.aclose()
            raise RuntimeError("bs-session-id header not found in response")

        await authentication_client.aclose()

        # Cache the session token
        try:
            with open(cache_file, "w") as f:
                json.dump(
                    {"endpoint": biostar_endpoint, "session_token": session_token}, f
                )
            logger.debug("Session token cached")
        except Exception as e:
            logger.warning(f"Failed to cache session token: {e}")

        instance = cls(
            biostar_endpoint=biostar_endpoint,
            session_token=session_token,
            logger=logger,
        )

        logger.info("Successfully logged in to Biostar.")

        return instance

    async def aclose(self) -> None:
        """
        Asynchronously closes the HTTP client and logs out from the Biostar API.
        Resets the client and session token. Raises RuntimeError if client or token is not set.
        """
        if self._client is None:
            self._logger.error("Client is not initialized")
            raise RuntimeError("Client is not initialized")

        if not self._session_token:
            self._logger.error("Session token is not set")
            raise RuntimeError("Session token is not set")

        self._logger.debug("Sending logout request to Biostar endpoint.")

        await self._client.post(
            "/api/logout",
            headers=self._headers,
        )

        await self._client.aclose()

        self._logger.info("Closed Biostar client session.")
        self._client = None
        self._session_token = None

        # Clear cache on logout
        try:
            cache_file = pathlib.Path("./cache/session_cache.json")
            if cache_file.exists():
                cache_file.unlink()
                self._logger.debug("Session cache cleared")
        except Exception as e:
            self._logger.warning(f"Failed to clear session cache: {e}")

    @property
    def client(self) -> httpx.AsyncClient:
        """
        Returns the initialized HTTPX AsyncClient. Raises RuntimeError if not initialized.
        """
        return self._assert_client_initialized()

    @property
    def token(self) -> str:
        """
        Returns the current session token. Raises RuntimeError if not set.
        """
        if self._session_token is None:
            self._logger.error("Session token is not set")
            raise RuntimeError("Session token is not set")
        return self._session_token

    @property
    def _headers(self) -> dict[str, str]:
        """
        Returns the headers containing the session token for authentication.
        """
        return {"bs-session-id": self._session_token} if self._session_token else {}

    def _assert_client_initialized(self) -> httpx.AsyncClient:
        """
        Ensures the HTTPX AsyncClient is initialized. Raises RuntimeError if not.
        """
        if self._client is None:
            self._logger.error("Client is not initialized")
            raise RuntimeError("Client is not initialized")

        return self._client

    async def __aenter__(self) -> "BiostarHttpConnection":
        """
        Asynchronous context manager entry. Returns self.
        """
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """
        Asynchronous context manager exit. Closes the connection.
        """
        await self.aclose()
