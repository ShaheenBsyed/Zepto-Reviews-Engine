"""
src/utils/logger.py
===================
Shared logger for all pipeline modules.
Uses a plain StreamHandler with UTF-8 encoding to avoid Windows cp1252
encoding crashes that occur with Rich's legacy Windows renderer.

Usage:
    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Starting Phase 1...")
"""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger with a UTF-8 safe StreamHandler.
    Using the module __name__ as the logger name ensures log messages
    show which module they came from.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(stream=open(
            sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1, closefd=False
        ))
        handler.setFormatter(
            logging.Formatter(
                fmt="[%(asctime)s] %(levelname)-8s %(name)s  %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

