"""Definição estruturada de filtros de pesquisa e consulta de licitações."""
from dataclasses import dataclass, field, asdict
from typing import List, Optional
import json


@dataclass
class LicitacaoFilter:
    """Estrutura completa de filtros aplicáveis na pesquisa local e na coleta online."""
    ufs: List[str] = field(default_factory=list)
    municipios_ibge: List[str] = field(default_factory=list)
    esferas: List[str] = field(default_factory=list)  # M, D, E, F
    modalidades_ids: List[int] = field(default_factory=list)

    # Situação do edital / recebimento de propostas
    # Opções: 'recebendo_proposta', 'todas', 'encerradas'
    status_proposta: str = "recebendo_proposta"

    # Filtros por datas
    data_publicacao_inicio: Optional[str] = None  # YYYY-MM-DD ou YYYYMMDD
    data_publicacao_fim: Optional[str] = None
    data_encerramento_inicio: Optional[str] = None
    data_encerramento_fim: Optional[str] = None
    prazo_dias: Optional[int] = None  # 3, 7, 15, 30 dias futuros

    # Filtros textuais e numéricos
    palavra_chave: Optional[str] = None
    numero_edital: Optional[str] = None
    orgao: Optional[str] = None  # Nome ou CNPJ
    valor_min: Optional[float] = None
    valor_max: Optional[float] = None

    category_ids: List[int] = field(default_factory=list)
    subcategory_ids: List[int] = field(default_factory=list)
    confidence_levels: List[str] = field(default_factory=list)
    classification_origin: Optional[str] = None
    primary_category_only: bool = False
    only_unclassified: bool = False

    # Ordenação e paginação local
    ordenar_por: str = "data_encerramento_proposta"
    ordem_asc: bool = True
    limite: int = 1000
    offset: int = 0

    def to_json(self) -> str:
        """Serializa o filtro para JSON persistente."""
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "LicitacaoFilter":
        """Reconstrói a instância de filtros a partir de JSON."""
        data = json.loads(json_str)
        return cls(**data)

    def is_brasil_inteiro(self) -> bool:
        """Retorna True se nenhuma UF foi restrita (abrange todo o Brasil)."""
        return len(self.ufs) == 0

    def has_municipio_filter(self) -> bool:
        """Retorna True se municípios específicos foram selecionados."""
        return len(self.municipios_ibge) > 0
