"""Utilitários de arquivos, diretórios e sanitização segura."""
import os
import re
import sys
from pathlib import Path


def get_app_dir() -> Path:
    """Retorna o diretório persistente do usuário para dados da aplicação."""
    if os.environ.get("RADAR_DATA_DIR"):
        app_dir = Path(os.environ["RADAR_DATA_DIR"]).resolve()
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            base = Path(local_app_data)
        else:
            base = Path.home() / "AppData" / "Local"
    else:
        base = Path.home() / ".local" / "share"

    app_dir = base / "RadarNacionalLicitacoes"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_db_path() -> Path:
    """Retorna o caminho padrão do banco de dados SQLite."""
    return get_app_dir() / "radar_licitacoes.sqlite3"


def get_logs_dir() -> Path:
    """Retorna o diretório para arquivos de log."""
    logs_dir = get_app_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_default_export_dir() -> Path:
    """Retorna o diretório padrão para exportação de arquivos Excel."""
    export_dir = get_app_dir() / "exportacoes"
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


def get_backups_dir() -> Path:
    """Retorna o diretório padrão para cópias de segurança (backup)."""
    backups_dir = get_app_dir() / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    return backups_dir


def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos para nomes de arquivos no sistema operacional."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name or "arquivo"


# Regex para caracteres de controle ilegais no XML do OpenPyXL
ILLEGAL_CHARACTERS_RE = re.compile(r"[\000-\010]|[\013-\014]|[\016-\037]")


def sanitize_for_excel(val: object) -> object:
    """
    1. Remove caracteres de controle ilegais no OpenPyXL (ex: \x0b, \x0c, \x00).
    2. Protege contra injeção de fórmulas no Excel (Formula Injection).
       Se o valor de texto começar com '=', '+', '-', '@', '\t', '\r', prefixa com apóstrofo
       preservando o conteúdo informativo sem execução de fórmula arbitrária.
    """
    if val is None:
        return ""
    if isinstance(val, (int, float, bool)):
        return val

    text = str(val)
    # Remove caracteres de controle que quebram o OpenPyXL
    text = ILLEGAL_CHARACTERS_RE.sub("", text)

    if text and (text.lstrip()[:1] in ("=", "+", "-", "@") or text[0] in ("\t", "\r", "\n")):
        return "'" + text
    return text
