import logging
import sys
import json
from datetime import datetime
from typing import Any

from kyc_platform.shared.config import config


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data
            
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, config.LOG_LEVEL))
        logger.propagate = False
    
    return logger


def log_with_context(logger: logging.Logger, level: str, message: str, **kwargs: Any) -> None:
    record = logger.makeRecord(
        logger.name,
        getattr(logging, level.upper()),
        "",
        0,
        message,
        (),
        None,
    )
    record.extra_data = kwargs
    logger.handle(record)
