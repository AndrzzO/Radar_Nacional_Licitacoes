"""Modelo de dados de alta performance para a tabela de licitações no Qt."""
from typing import List, Set, Optional
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex, Signal

from src.domain.entities import Licitacao
from src.domain.normalization import format_currency_br, format_cnpj
from src.utils.datetime_utils import format_datetime_br


COLUMNS = [
    ("Sel", 45),
    ("Identificador PNCP", 210),
    ("Edital", 110),
    ("Órgão Comprador", 260),
    ("Município", 140),
    ("UF", 50),
    ("Modalidade", 160),
    ("Objeto", 350),
    ("Valor Estimado", 130),
    ("Publicação", 120),
    ("Prazo Propostas", 130),
    ("Situação", 110),
    ("Categoria", 180), ("Subcategoria",180), ("Confiança",100), ("Origem",100),
]


class ResultsTableModel(QAbstractTableModel):
    """Modelo QAbstractTableModel otimizado para navegação rápida de milhares de registros."""

    sort_requested=Signal(int,object)

    def sort(self,column,order=Qt.SortOrder.AscendingOrder):
        self.sort_requested.emit(column,order)

    def __init__(self, licitacoes: Optional[List[Licitacao]] = None):
        super().__init__()
        self._data: List[Licitacao] = licitacoes or []
        self._selected_ids: Set[str] = set()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section][0]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole):
        if not index.isValid() or index.row() >= len(self._data):
            return None

        lic = self._data[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return ""  # Checkbox exibido via CheckStateRole
            elif col == 1:
                return lic.numero_controle_pncp
            elif col == 2:
                edital = lic.numero_edital or "-"
                ano = f"/{lic.ano}" if lic.ano else ""
                return f"{edital}{ano}"
            elif col == 3:
                return lic.orgao_nome or "-"
            elif col == 4:
                return lic.municipio_nome or "-"
            elif col == 5:
                return lic.uf_sigla or "-"
            elif col == 6:
                return lic.modalidade_nome or "-"
            elif col == 7:
                obj = lic.objeto or "-"
                # Trunca visualmente para conforto de leitura na grade
                return obj if len(obj) <= 120 else obj[:117] + "..."
            elif col == 8:
                return format_currency_br(lic.valor_estimado)
            elif col == 9:
                return format_datetime_br(lic.data_publicacao_pncp, include_time=False)
            elif col == 10:
                return format_datetime_br(lic.data_encerramento_proposta)
            elif col == 11:
                return lic.situacao_prazo
            elif col >= 12:
                result=getattr(lic,'classification',{}); primary=result.get('primary') or {}
                return [primary.get('category','Não Classificado'),primary.get('subcategory','—'),primary.get('confidence','—'),result.get('origin','Pendente')][col-12]

        elif role == Qt.ItemDataRole.CheckStateRole and col == 0:
            return Qt.CheckState.Checked if lic.numero_controle_pncp in self._selected_ids else Qt.CheckState.Unchecked

        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 7:
                return lic.objeto
            elif col == 1:
                return f"Clique duas vezes para abrir detalhes de {lic.numero_controle_pncp}"
            elif col == 8:
                return f"Valor estimado oficial: {format_currency_br(lic.valor_estimado)}"

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (0, 2, 5, 9, 10, 11):
                return int(Qt.AlignmentFlag.AlignCenter)
            elif col == 8:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        return None

    def setData(self, index: QModelIndex, value, role=Qt.ItemDataRole) -> bool:
        if index.isValid() and index.column() == 0 and role == Qt.ItemDataRole.CheckStateRole:
            lic = self._data[index.row()]
            if value in (Qt.CheckState.Checked, Qt.CheckState.Checked.value):
                self._selected_ids.add(lic.numero_controle_pncp)
            else:
                self._selected_ids.discard(lic.numero_controle_pncp)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            return True
        return False

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.column() == 0:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
        return flags

    def set_licitacoes(self, licitacoes: List[Licitacao]):
        """Atualiza a lista completa de licitações na tabela."""
        self.beginResetModel()
        self._data = licitacoes
        # Mantém seleções apenas dos IDs ainda presentes
        valid_ids = {lic.numero_controle_pncp for lic in licitacoes}
        self._selected_ids = self._selected_ids.intersection(valid_ids)
        self.endResetModel()

    def get_licitacao(self, row: int) -> Optional[Licitacao]:
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def select_all(self, select: bool = True):
        """Seleciona ou desmarca todos os registros exibidos."""
        self.beginResetModel()
        if select:
            self._selected_ids = {lic.numero_controle_pncp for lic in self._data}
        else:
            self._selected_ids.clear()
        self.endResetModel()

    def get_selected_pncp_ids(self) -> List[str]:
        """Retorna lista dos IDs selecionados pelo usuário."""
        return list(self._selected_ids)

    def get_selected_count(self) -> int:
        return len(self._selected_ids)
