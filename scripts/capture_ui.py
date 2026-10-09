import os,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(root))
os.environ['QT_QPA_PLATFORM']='offscreen'; os.environ['RADAR_DATA_DIR']=str(root/'scratch'/'validacao_online')
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QFont
from src.database.connection import DatabaseConnection
from src.database.migrations import init_database
from src.ui.main_window import MainWindow
from src.domain.filters import LicitacaoFilter
app=QApplication([]); QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'); app.setFont(QFont('Segoe UI',9))
db=DatabaseConnection(Path(os.environ['RADAR_DATA_DIR'])/'online.sqlite3')
with db.session() as c: init_database(c)
w=MainWindow(db); w.show()
def wait():
 while w.page_search.query_worker and w.page_search.query_worker.isRunning(): app.processEvents(); time.sleep(.01)
 app.processEvents()
wait(); w._navigate(1); w.page_search.apply_filters(LicitacaoFilter(ufs=['GO','DF'],category_ids=[1],subcategory_ids=[1])); w.page_search._pesquisar_localmente(); wait()
for index,name in [(1,'pesquisa_final'),(6,'classificacao_final')]:
 w._navigate(index); app.processEvents(); w.grab().save(str(root/'scratch'/f'{name}.png'))
w.page_classification.tabs.setCurrentIndex(3); app.processEvents(); w.grab().save(str(root/'scratch'/'regras_final.png'))
w.close(); app.processEvents()
