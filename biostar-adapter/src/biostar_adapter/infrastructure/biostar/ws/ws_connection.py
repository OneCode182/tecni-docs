"""
This module provides the WebSocketConnection class for managing WebSocket connections to Biostar endpoints.
It handles event listening, message dispatching, and session management for real-time communication with Biostar systems.
"""

import asyncio
import json
import logging
import ssl
from typing import Any, Callable, Dict

import httpx
import websockets

from biostar_adapter.common.utility import LoggerMixin


class WebSocketConnection(LoggerMixin):
    """
    Manages a WebSocket connection to a Biostar endpoint, handling event listening and message callbacks.

    Args:
        biostar_endpoint (str): The Biostar server endpoint.
        session_token (str): The session token for authentication.
        logger (logging.Logger): Logger instance for logging events.
        client (websockets.ClientConnection): The WebSocket client connection.
    """

    _session_token: str
    _biostar_endpoint: str
    _client: websockets.ClientConnection
    _listening_task: asyncio.Task[None] | None = None
    _message_callbacks: list[Callable[[Dict[str, Any]], None]] = []

    def __init__(
        self,
        *,
        biostar_endpoint: str,
        session_token: str,
        logger: logging.Logger,
        client: websockets.ClientConnection,
    ) -> None:
        """
        Initialize the WebSocketConnection instance and start listening for events.
        """
        self._biostar_endpoint = biostar_endpoint
        self._session_token = session_token
        self._build_logger(logger=logger)
        self._client = client
        self._message_callbacks = []

        self._logger.info("WebSocketConnection instance successfully created.")
        self._listening_task = asyncio.create_task(self._listen_events())
        self._logger.debug("Listening task started for WebSocket events.")

    async def aclose(self) -> None:
        """
        Asynchronously close the WebSocket connection and cancel the listening task if running.
        """
        self._logger.debug("Closing WebSocket connection.")
        await self._client.close()

        if self._listening_task:
            self._logger.debug("Cancelling the listening task.")
            cancel_status = self._listening_task.cancel()

            if cancel_status:
                self._logger.debug("Listening task cancelled successfully.")
            else:
                self._logger.warning(
                    "Listening task was not running or already cancelled."
                )

        self._logger.info("WebSocket connection closed.")

    async def _listen_events(self) -> None:
        """
        Internal coroutine to listen for incoming WebSocket events and dispatch them to registered callbacks.
        """
        self._logger.info("Started listening for events on WebSocket.")
        try:
            async for message in self._client:
                message_str = (
                    message.decode() if isinstance(message, bytes) else message
                )
                message_dict = json.loads(message_str)
                for callback in self._message_callbacks:
                    callback(message_dict)

        except Exception as e:
            self._logger.error(f"Error while listening for events: {e}")
        finally:
            self._logger.info("Stopped listening for events on WebSocket.")

    def add_message_handler(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Register a callback to handle incoming WebSocket messages.

        Args:
            callback (Callable[[Dict[str, Any]], None]): Function to handle messages.
        """
        self._message_callbacks.append(callback)

    @classmethod
    async def create(
        cls,
        *,
        biostar_endpoint: str,
        session_token: str,
        logger: logging.Logger,
        http_client: httpx.AsyncClient,
    ) -> "WebSocketConnection":
        """
        Asynchronously create and initialize a WebSocketConnection instance.

        Args:
            biostar_endpoint (str): The Biostar server endpoint.
            session_token (str): The session token for authentication.
            logger (logging.Logger): Logger instance for logging events.
            http_client (httpx.AsyncClient): HTTP client for auxiliary requests.

        Returns:
            WebSocketConnection: The initialized WebSocketConnection instance.
        """
        ws_url = f"wss://{biostar_endpoint}/wsapi"
        session_token_header = f"bs-session-id={session_token}"
        events_url = f"https://{biostar_endpoint}/api/events/start"
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        logger.debug(f"Connecting to WebSocket at {ws_url}")
        ws_client = await websockets.connect(ws_url, ssl=context)
        logger.info("Successfully connected to WebSocket.")

        logger.debug("Sending session token over WebSocket")
        await ws_client.send(session_token_header)
        logger.debug("Session token sent over WebSocket.")

        logger.debug(f"Starting event stream via POST to {events_url}")
        await http_client.post(
            events_url,
            headers={"bs-session-id": session_token},
        )
        logger.debug("Event stream started via HTTP POST.")

        logger.debug("WebSocketConnection instance is being created")
        return cls(
            biostar_endpoint=biostar_endpoint,
            session_token=session_token,
            logger=logger,
            client=ws_client,
        )
