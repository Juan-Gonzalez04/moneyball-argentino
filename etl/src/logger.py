"""
Módulo de Logging Centralizado para MoneyBall Argentino / Argos.

Configura salida simultánea a consola y a archivo rotativo (RotatingFileHandler),
asegurando persistencia en disco sin riesgo de desbordamiento en el servidor Argos.
"""

from logging.handlers import RotatingFileHandler
import logging
from pathlib import Path

from etl.src.config import LOGS_DIR


def configure_logging(base_logger_name: str = "etl") -> logging.Logger:
    """
    Configura el logger base con dos destinos:
    1. StreamHandler (consola / stdout).
    2. RotatingFileHandler en /app/logs/etl.log (máx 5 MB por archivo, 5 rotaciones).
    """
    logger = logging.getLogger(base_logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Prevenir handlers duplicados si se llama múltiples veces
    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # 1. Consola
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 2. Archivo rotativo
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_file_path = LOGS_DIR / "etl.log"
        file_handler = RotatingFileHandler(
            str(log_file_path),
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
