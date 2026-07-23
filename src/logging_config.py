"""Structured logging with loguru + file rotation."""

import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_level: str = "INFO", log_dir: str = "./logs",
                  rotation: str = "10 MB", retention: str = "30 days") -> None:
    """Configure loguru with console + file sinks."""
    logger.remove()

    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        colorize=True,
    )

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_path / "proiaq_{time:YYYY-MM-DD}.log",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
               "{name}:{function}:{line} | {message}",
        rotation=rotation,
        retention=retention,
        compression="gz",
    )

    logger.add(
        log_path / "proiaq_errors_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
               "{name}:{function}:{line} | {message}\n{exception}",
        rotation=rotation,
        retention=retention,
        compression="gz",
    )

    # Separate log for replies only (easy to grep/copy posted URLs)
    logger.add(
        log_path / "replies.log",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
        rotation=rotation,
        retention=retention,
        filter=lambda record: "REPLIED POSTS" in record["message"]
        or "Reply POSTED" in record["message"]
        or "Would post to" in record["message"]
        or "Would reply to" in record["message"],
    )
