import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_logging(log_dir: Path) -> logging.Logger:
    """Configure file + console logging. Returns root bot logger."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"bot_{datetime.date.today()}.log"

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = TimedRotatingFileHandler(
        log_file, when="midnight", interval=1, backupCount=7, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(file_handler)

    # Suppress noisy third-party loggers
    for noisy in ("playwright", "asyncio", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logging.getLogger("lemit_bot")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"lemit_bot.{name}")
