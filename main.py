"""Ponto de entrada principal do Radar Nacional de Licitações."""
import sys
import os
from pathlib import Path

# Adiciona o diretório raiz ao sys.path para importações absolutas limpas
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Adquire antes de carregar o Qt ou tocar no banco. O Windows mantém a
# exclusão atômica entre processos e libera a trava se o processo terminar.
if __name__ == "__main__" and os.name == "nt":
    import atexit
    from src.utils.single_instance import SingleInstance
    _instance_guard = SingleInstance()
    if not _instance_guard.acquired:
        sys.exit(0)
    atexit.register(_instance_guard.close)

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont

    from src.database.connection import DatabaseConnection
    from src.database.migrations import init_database
    from src.database.repositories import LocationRepository, SettingsRepository
    from src.application.location_service import LocationService
    from src.ui.main_window import MainWindow
    from src.utils.logging_config import setup_logging, get_logger
    from src.utils.file_utils import get_app_dir, get_db_path, get_default_export_dir
except Exception:
    # Falhas anteriores ao logger também precisam deixar diagnóstico no pacote windowed.
    import traceback
    diagnostic_dir=Path(os.environ.get('RADAR_DATA_DIR') or (Path(os.environ.get('LOCALAPPDATA',Path.home()))/'RadarNacionalLicitacoes'))
    diagnostic_dir.mkdir(parents=True,exist_ok=True)
    (diagnostic_dir/'startup_error.log').write_text(traceback.format_exc(),encoding='utf8')
    raise


def bootstrap_application():
    """Inicializa banco de dados, tabelas e configurações na primeira execução."""
    logger = get_logger()
    logger.info("Iniciando Radar Nacional de Licitações v1.1.0...")

    # Garante diretórios
    get_app_dir()
    get_default_export_dir()

    # Inicializa banco de dados e migrações
    db_conn = DatabaseConnection(get_db_path())
    with db_conn.session() as conn:
        init_database(conn)

    # Inicializa cache das UFs
    loc_repo = LocationRepository(db_conn)
    loc_service = LocationService(loc_repo)
    from src.application.location_service import FALLBACK_ESTADOS
    if len(loc_repo.get_estados()) != 27:
        loc_repo.save_estados(FALLBACK_ESTADOS)
    loc_service.ibge_client.close()

    return db_conn


def main():
    """Inicializa a aplicação Qt e executa o loop de eventos."""
    setup_logging()
    logger = get_logger()

    # Configuração de aplicação Qt
    app = QApplication(sys.argv)
    app.setApplicationName("Radar Nacional de Licitações")
    app.setOrganizationName("RadarNacional")

    # Fonte padrão legível e limpa no Windows
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    try:
        db_conn = bootstrap_application()
        window = MainWindow(db_conn)
        window.show()
        if "--smoke-test" in sys.argv:
            from src.learning.course import verify_pdf_assets
            verify_pdf_assets()
            window._navigate(7)
            assert len(window.page_course.data["modules"]) == 15
            logger.info("COURSE_SMOKE_OK: curso e apostila disponíveis no pacote")
            from PySide6.QtCore import QTimer
            app.lastWindowClosed.connect(lambda: logger.info("SMOKE_TEST_OK: janela inicializada e encerrada com segurança"))
            QTimer.singleShot(750, window.close)
        sys.exit(app.exec())
    except Exception as e:
        logger.exception(f"Erro fatal na inicialização: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
