"""Structured logging configuration adhering to workspace ODBR guidelines.
Format: [TIMESTAMP] [LEVEL] [MODULE] Message | details
"""

import logging
import sys
from datetime import datetime, timezone


class ODBRFormatter(logging.Formatter):
    """Custom logging formatter outputting [TIMESTAMP] [LEVEL] [MODULE] Message | details."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        level = record.levelname
        module = record.name

        details = getattr(record, "details", None)
        base_msg = record.getMessage()

        if details:
            msg = f"[{timestamp}] [{level}] [{module}] {base_msg} | {details}"
        else:
            msg = f"[{timestamp}] [{level}] [{module}] {base_msg}"

        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                msg = f"{msg}\n{record.exc_text}"
        return msg


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with ODBR-compliant stderr stream handler."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(ODBRFormatter())
    
    root = logging.getLogger("biocontext")
    root.setLevel(level)
    # Avoid duplicate handlers if called multiple times
    if not root.handlers:
        root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Obtain a namespaced logger within the biocontext hierarchy."""
    return logging.getLogger(f"biocontext.{name}")
