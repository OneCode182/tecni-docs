"""
This module provides utility classes for logging, string manipulation, and colored log formatting.
"""

import logging


class LoggerMixin:
    """
    Mixin class to provide a logger instance to child classes.

    Methods:
        _build_logger(logger): Initializes a child logger for the class.
        _log(level, message): Logs a message at the specified level using the class logger.
    """

    _logger: logging.Logger

    def _build_logger(
        self,
        logger: logging.Logger,
    ) -> None:
        """
        Initialize a logger for the class as a child of the provided logger.

        Args:
            logger (logging.Logger): The base logger to use.
        """
        self._logger = logger.getChild(self.__class__.__name__)

    def _log(
        self,
        level: int,
        message: str,
    ) -> None:
        """
        Log a message at the specified level using the class logger.

        Args:
            level (int): Logging level (e.g., logging.INFO).
            message (str): The message to log.
        """
        if self._logger:
            self._logger.log(level, message)


class StringUtils:
    """
    Utility class for string manipulation and JSON formatting.
    """

    @staticmethod
    def to_snake_case(s: str) -> str:
        """Convert a string to snake_case."""
        return s.replace(" ", "_").lower()

    @staticmethod
    def to_camel_case(s: str) -> str:
        """Convert a string to camelCase."""
        parts = s.split(" ")
        return parts[0].lower() + "".join(part.capitalize() for part in parts[1:])

    @staticmethod
    def pretty_json(data: dict[str, object]) -> str:
        """Return a pretty-printed JSON string."""
        import json

        return json.dumps(data, indent=4, sort_keys=True)


class ColorFormatter(logging.Formatter):
    """
    Custom logging formatter that adds color to log messages based on their level.
    """

    COLORS = {
        "DEBUG": "\033[94m",  # Blue
        "INFO": "\033[92m",  # Green
        "WARNING": "\033[93m",  # Yellow
        "ERROR": "\033[91m",  # Red
        "CRITICAL": "\033[95m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with color based on its level.

        Args:
            record (logging.LogRecord): The log record to format.
        Returns:
            str: The formatted log message with color codes.
        """
        color = self.COLORS.get(record.levelname, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"
