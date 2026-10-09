"""Trilha de aprendizagem offline com progresso local e apostila."""
import json
from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QTabWidget, QListWidget, QListWidgetItem, QSplitter, QTextBrowser,
    QRadioButton, QButtonGroup, QScrollArea, QFileDialog, QMessageBox,
)
from src.learning.course import (load_course, lesson_html, resources_html, sources_html,
                                 read_progress, export_course_pdf, official_url)
from src.utils.file_utils import get_default_export_dir


class CoursePage(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.data = load_course()
        self.progress = read_progress(settings, self.data)
        self.index = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        top = QHBoxLayout()
        title = QLabel("Curso • Do cadastro ao recebimento")
        title.setWordWrap(True)
        title.setStyleSheet("font-size:22px;font-weight:700;color:#0f172a;")
        top.addWidget(title, 1)
        self.pdf_button = QPushButton("Baixar curso em PDF")
        self.pdf_button.setMinimumHeight(38)
        self.pdf_button.clicked.connect(self.download_pdf)
        top.addWidget(self.pdf_button)
        layout.addLayout(top)
        description = QLabel("15 módulos • Leitura offline • Base principal: Lei nº 14.133/2021 • Revisão: 08/10/2026")
        description.setWordWrap(True)
        description.setStyleSheet("color:#526479;padding-bottom:4px;")
        layout.addWidget(description)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(self.data["modules"]))
        self.progress_bar.setMaximumHeight(22)
        layout.addWidget(self.progress_bar)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        lessons = QSplitter(Qt.Orientation.Horizontal)
        self.module_list = QListWidget()
        self.module_list.setWordWrap(True)
        self.module_list.setMinimumWidth(190)
        self.module_list.setMaximumWidth(290)
        self.module_list.setStyleSheet("QListWidget {border:0;background:#f1f5f9;} QListWidget::item {padding:8px;} QListWidget::item:selected {background:#dbeafe;color:#0c4a6e;}")
        for i, module in enumerate(self.data["modules"]):
            item = QListWidgetItem(f'{i + 1:02d}  {module["title"]}')
            item.setSizeHint(QSize(220, 64))
            self.module_list.addItem(item)
        lessons.addWidget(self.module_list)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 4, 0, 0)
        self.lesson_tabs = QTabWidget()
        self.reader = self._browser()
        self.lesson_tabs.addTab(self.reader, "Aula e passo a passo")
        self.review_scroll = QScrollArea()
        self.review_scroll.setWidgetResizable(True)
        self.lesson_tabs.addTab(self.review_scroll, "Exercício de revisão")
        right_layout.addWidget(self.lesson_tabs, 1)
        actions = QHBoxLayout()
        self.previous_button = QPushButton("Anterior")
        self.previous_button.clicked.connect(lambda: self.module_list.setCurrentRow(self.index - 1))
        self.complete_button = QPushButton()
        self.complete_button.clicked.connect(self.toggle_complete)
        self.next_button = QPushButton("Próximo")
        self.next_button.clicked.connect(lambda: self.module_list.setCurrentRow(self.index + 1))
        for button in (self.previous_button, self.complete_button, self.next_button):
            button.setMinimumHeight(34)
            actions.addWidget(button)
        right_layout.addLayout(actions)
        lessons.addWidget(right)
        lessons.setStretchFactor(1, 1)
        lessons.setSizes([235, 760])
        self.tabs.addTab(lessons, "Meu curso")
        resources = self._browser()
        resources.setHtml(resources_html(self.data))
        self.tabs.addTab(resources, "Cursos gratuitos EV.G")
        sources = self._browser()
        sources.setHtml(sources_html(self.data))
        self.tabs.addTab(sources, "Fontes e abrangência")
        note = QLabel("Trilha autoral do Radar, sem certificado oficial. Confira as normas vigentes e o edital. Seu progresso fica salvo neste banco local.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#64748b;font-size:11px;")
        layout.addWidget(note)
        self.module_list.currentRowChanged.connect(self.show_module)
        self.module_list.setCurrentRow(0)

    def _browser(self):
        browser = QTextBrowser()
        browser.setOpenLinks(False)
        browser.setOpenExternalLinks(False)
        browser.anchorClicked.connect(self.open_reference)
        browser.setStyleSheet("QTextBrowser {border:0;padding:12px;background:white;}")
        return browser

    def open_reference(self, url):
        if official_url(url.toString()):
            if not QDesktopServices.openUrl(url):
                QMessageBox.warning(self, "Link", "Não foi possível abrir o navegador. Verifique o navegador padrão e sua conexão.")

    def refresh_progress(self):
        # A restauração de backup pode ter alterado as configurações.
        self.progress = read_progress(self.settings, self.data)
        self.show_module(self.index)

    def show_module(self, index):
        if not 0 <= index < len(self.data["modules"]):
            return
        self.index = index
        self.reader.setHtml(lesson_html(self.data, index))
        self.reader.verticalScrollBar().setValue(0)
        self.lesson_tabs.setCurrentIndex(0)
        self.previous_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < len(self.data["modules"]) - 1)
        self._build_review()
        self._update_progress()

    def _build_review(self):
        module = self.data["modules"][self.index]
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 16, 20, 16)
        heading = QLabel(module["title"])
        heading.setWordWrap(True)
        heading.setStyleSheet("font-size:18px;font-weight:600;color:#075985;")
        layout.addWidget(heading)
        question = QLabel(module["quiz"]["question"])
        question.setWordWrap(True)
        layout.addWidget(question)
        self.answers = QButtonGroup(panel)
        for i, answer in enumerate(module["quiz"]["options"]):
            row = QHBoxLayout()
            button = QRadioButton(chr(65 + i))
            self.answers.addButton(button, i)
            row.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)
            label = QLabel(answer)
            label.setWordWrap(True)
            row.addWidget(label, 1)
            layout.addLayout(row)
        self.check_button = QPushButton("Conferir resposta")
        self.check_button.clicked.connect(self.check_answer)
        layout.addWidget(self.check_button)
        self.feedback = QLabel()
        self.feedback.setWordWrap(True)
        self.feedback.setStyleSheet("padding:12px;background:#eff6ff;color:#164e63;")
        layout.addWidget(self.feedback)
        state = self.progress.get(module["id"], {})
        previous = state.get("answer")
        if type(previous) is int and 0 <= previous < len(module["quiz"]["options"]):
            self.answers.button(previous).setChecked(True)
            self._feedback(previous)
        else:
            self.feedback.setText("Escolha uma alternativa. Você pode revisar e tentar novamente.")
        layout.addStretch()
        old = self.review_scroll.takeWidget()
        if old:
            old.deleteLater()
        self.review_scroll.setWidget(panel)

    def _feedback(self, answer):
        quiz = self.data["modules"][self.index]["quiz"]
        prefix = "Resposta correta. " if answer == quiz["correct"] else "Reveja a aula. "
        self.feedback.setText(prefix + quiz["explanation"])

    def _persist(self, field, value):
        module_id = self.data["modules"][self.index]["id"]
        new = {key: dict(val) for key, val in self.progress.items()}
        new.setdefault(module_id, {})[field] = value
        try:
            self.settings.set("course_progress_" + self.data["version"], json.dumps(new, ensure_ascii=False))
        except Exception as error:
            QMessageBox.warning(self, "Progresso não salvo", str(error))
            return False
        self.progress = new
        return True

    def check_answer(self):
        answer = self.answers.checkedId()
        if answer < 0:
            self.feedback.setText("Selecione uma alternativa antes de conferir.")
            return
        if self._persist("answer", answer):
            self._feedback(answer)
            self._update_progress()

    def toggle_complete(self):
        module = self.data["modules"][self.index]
        done = self.progress.get(module["id"], {}).get("completed") is True
        if self._persist("completed", not done):
            self._update_progress()

    def _update_progress(self):
        completed = 0
        correct = 0
        for i, module in enumerate(self.data["modules"]):
            state = self.progress.get(module["id"], {})
            done = state.get("completed") is True
            completed += int(done)
            correct += int(type(state.get("answer")) is int and state["answer"] == module["quiz"]["correct"])
            prefix = "✓ " if done else ""
            self.module_list.item(i).setText(f'{prefix}{i + 1:02d}  {module["title"]}')
        self.progress_bar.setValue(completed)
        self.progress_bar.setFormat(f"{completed}/{len(self.data['modules'])} aulas marcadas como lidas • {correct} respostas corretas")
        current = self.data["modules"][self.index]["id"]
        done = self.progress.get(current, {}).get("completed") is True
        self.complete_button.setText("Desmarcar leitura" if done else "Marcar como lida")

    def download_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Salvar apostila completa", str(get_default_export_dir() / "Curso_Radar_Licitacoes.pdf"), "Documento PDF (*.pdf)")
        if not path:
            return
        try:
            target = export_course_pdf(path)
            QMessageBox.information(self, "PDF salvo", f"Apostila completa salva em:\n{target}")
        except Exception as error:
            QMessageBox.warning(self, "Não foi possível salvar o PDF", str(error))
