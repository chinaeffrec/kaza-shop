import logging
import logging.handlers
import os
import sys
from pathlib import Path


def configure_logging(name: str = "app") -> None:
    """Настраивает логирование: консоль + ротируемый файл."""
    try:
        from app.core.config import get_settings
        level_name = get_settings().log_level.upper()
    except Exception:
        level_name = os.getenv("LOG_LEVEL", "INFO").upper()

    level = getattr(logging, level_name, logging.INFO)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    formatter = logging.Formatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)

    # Консоль
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Файл с ротацией
    log_dir = Path("/app/logs")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / f"{name}.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except Exception:
        pass  # Если /app/logs недоступен — только консоль

    # Приглушаем шумные библиотеки
    for noisy in ("sqlalchemy.engine", "aiogram", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
