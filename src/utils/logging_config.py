"""Configuração centralizada de logs com rotação e formato estruturado."""
import logging
from logging.handlers import RotatingFileHandler
import sys
from src.utils.file_utils import get_logs_dir

LOGGER_NAME = "radar_nacional_licitacoes"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configura e retorna o logger da aplicação com saída em arquivo rotativo e console."""
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(funcName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler do arquivo rotativo
    try:
        log_file = get_logs_dir() / "radar.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Aviso: Não foi possível criar arquivo de log: {e}", file=sys.stderr)

    # Handler do console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger() -> logging.Logger:
    """Retorna o logger principal da aplicação."""
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        return setup_logging()
    return logger
