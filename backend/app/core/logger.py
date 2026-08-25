import json
from datetime import datetime, timezone
import logging
import sys
from typing import Any

def _get_logger() -> logging.Logger:
    logger = logging.getLogger("lenny_growth")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

_logger = _get_logger()

def log_event(event_name: str, **kwargs: Any) -> None:
    """Logs a structured JSON event."""
    log_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_name,
    }
    for k, v in kwargs.items():
        if isinstance(v, Exception):
            log_data[k] = str(v)
            log_data[f"{k}_type"] = v.__class__.__name__
        else:
            log_data[k] = v
    _logger.info(json.dumps(log_data))
