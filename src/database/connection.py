"""Gerenciamento de conexões SQLite com suporte a WAL e concorrência segura."""
import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from src.utils.file_utils import get_db_path
from src.utils.logging_config import get_logger

logger = get_logger()


class DatabaseConnection:
    """Gerenciador centralizado de conexão com o banco de dados SQLite local."""

    def __init__(self, db_path: Optional[Path | str] = None):
        self.db_path = Path(db_path) if db_path else get_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Cria e configura uma conexão com o SQLite em modo WAL."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            check_same_thread=False,
            isolation_level=None,  # Autocommit gerido explicitamente ou por transações
        )
        conn.row_factory = sqlite3.Row
        from src.utils.datetime_utils import proposal_status, get_current_time_sp, timestamp_sp
        current = get_current_time_sp()
        conn.create_function("proposal_status", 3, lambda end, start, state: proposal_status(end,start,state,current))
        conn.create_function("timestamp_sp", 1, timestamp_sp)
        import hashlib
        conn.create_function("content_hash",1,lambda text:hashlib.sha256((text or "").encode()).hexdigest(),deterministic=True)
        # Otimizações para estabilidade e velocidade local
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        return conn

    @contextmanager
    def session(self):
        """Context manager que fornece conexão e gerencia transações com commit/rollback."""
        conn = self.get_connection()
        try:
            if not conn.in_transaction:
                conn.execute("BEGIN;")
            yield conn
            if conn.in_transaction:
                conn.execute("COMMIT;")
        except Exception:
            if conn.in_transaction:
                try:
                    conn.execute("ROLLBACK;")
                except Exception:
                    pass
            raise
        finally:
            conn.close()

    def backup(self, destination=None):
        """Snapshot consistente, incluindo WAL, sem manter transação de escrita."""
        from datetime import datetime
        dest = Path(destination) if destination else self.db_path.parent / 'backups' / ('radar_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.sqlite3')
        if dest.resolve() == self.db_path.resolve():
            raise ValueError('Backup deve ter caminho diferente do banco ativo.')
        dest.parent.mkdir(parents=True,exist_ok=True)
        source = self.get_connection()
        target = sqlite3.connect(str(dest))
        try:
            source.backup(target)
        finally:
            target.close(); source.close()
        return dest

    def restore(self, source_path):
        """Validar cópia isolada, migrar e restaurar via backup SQLite."""
        import tempfile
        from src.database.migrations import init_database
        source_path = Path(source_path).resolve()
        if source_path == self.db_path.resolve(): raise ValueError('Escolha outro arquivo de backup.')
        with tempfile.TemporaryDirectory() as folder:
            staged = DatabaseConnection(Path(folder)/'restore.sqlite3')
            source = sqlite3.connect(source_path.as_uri()+'?mode=ro',uri=True)
            target = staged.get_connection()
            try: source.backup(target)
            finally: source.close(); target.close()
            with staged.session() as c:
                if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Backup corrompido.')
                c.execute('SELECT numero_controle_pncp,objeto FROM licitacoes LIMIT 1')
                init_database(c)
                if c.execute('PRAGMA foreign_key_check').fetchone(): raise ValueError('Referências inválidas no backup.')
            backup = self.backup()
            source=staged.get_connection(); target=self.get_connection()
            try: source.backup(target)
            finally: source.close(); target.close()
            return backup
