import os,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(root))
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['RADAR_DATA_DIR']=str(root/'scratch'/'course_ui')
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QFont
from src.database.connection import DatabaseConnection
from src.database.migrations import init_database
from src.ui.main_window import MainWindow
app=QApplication([])
QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf'); app.setFont(QFont('Segoe UI',9))
dest=root/'scratch'/'course_ui'; dest.mkdir(parents=True,exist_ok=True)
db=DatabaseConnection(dest/'ui.sqlite3')
with db.session() as conn: init_database(conn)
w=MainWindow(db); w.show(); w._navigate(7)
while w.page_search.query_worker and w.page_search.query_worker.isRunning():
 app.processEvents(); time.sleep(.01)
app.processEvents(); w.grab().save(str(dest/'course.png'))
w.page_course.module_list.setCurrentRow(11); w.page_course.lesson_tabs.setCurrentIndex(1)
app.processEvents(); w.grab().save(str(dest/'exercise.png'))
w.page_course.tabs.setCurrentIndex(1); app.processEvents(); w.grab().save(str(dest/'external.png'))
w.resize(1024,680); w.page_course.tabs.setCurrentIndex(0); w.page_course.lesson_tabs.setCurrentIndex(0)
app.processEvents(); w.grab().save(str(dest/'minimum.png'))
w.close(); app.processEvents()
