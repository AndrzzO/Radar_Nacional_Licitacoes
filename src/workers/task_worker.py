"""Worker genérico: sinais entregues a slots da interface, cancelamento cooperativo."""
from PySide6.QtCore import QThread, Signal
from threading import Event
from src.utils.logging_config import get_logger

class TaskWorker(QThread):
    result=Signal(object)
    error=Signal(str)
    progress=Signal(int,int)
    def __init__(self,fn,parent=None):
        super().__init__(parent); self.fn=fn; self.stop=Event()
    def cancel(self): self.stop.set()
    def run(self):
        try: self.result.emit(self.fn(self.progress.emit,self.stop.is_set))
        except Exception as e:
            get_logger().exception('Falha em tarefa de background')
            self.error.emit(str(e))
