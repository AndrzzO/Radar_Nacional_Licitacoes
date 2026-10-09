"""Entidades de domínio do Radar Nacional de Licitações."""
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any


@dataclass
class Estado:
    """Representação de Unidade Federativa (UF)."""
    uf_sigla: str
    nome: str
    id_ibge: Optional[int] = None


@dataclass
class Municipio:
    """Representação de Município com código oficial IBGE."""
    codigo_ibge: str
    nome: str
    uf_sigla: str
    uf_nome: Optional[str] = None


@dataclass
class Orgao:
    """Representação de Órgão Público Comprador."""
    cnpj: str
    razao_social: str
    poder_id: Optional[str] = None  # E, L, J
    poder_nome: Optional[str] = None
    esfera_id: Optional[str] = None  # M, D, E, F
    esfera_nome: Optional[str] = None


@dataclass
class Licitacao:
    """
    Entidade central de Contratação / Edital do PNCP.
    Preserva dados oficiais sem inventar valores ou datas ausentes.
    """
    # Identificação
    numero_controle_pncp: str  # Chave primária oficial única (ex: 54801121000161-1-000015/2026)
    numero_edital: Optional[str] = None
    ano: Optional[int] = None
    sequencial: Optional[int] = None
    processo: Optional[str] = None

    # Modalidade e Instrumento Convocatório
    modalidade_id: Optional[int] = None
    modalidade_nome: Optional[str] = None
    modo_disputa_id: Optional[int] = None
    modo_disputa_nome: Optional[str] = None
    tipo_instrumento_codigo: Optional[int] = None
    tipo_instrumento_nome: Optional[str] = None

    # Órgão Comprador
    orgao_cnpj: Optional[str] = None
    orgao_nome: Optional[str] = None
    esfera_id: Optional[str] = None  # M, D, E, F
    esfera_nome: Optional[str] = None  # Municipal, Distrital, Estadual, Federal
    poder_id: Optional[str] = None  # E, L, J
    poder_nome: Optional[str] = None

    # Unidade Orçamentária / Compradora
    unidade_codigo: Optional[str] = None
    unidade_nome: Optional[str] = None
    uf_sigla: Optional[str] = None
    uf_nome: Optional[str] = None
    municipio_nome: Optional[str] = None
    municipio_ibge: Optional[str] = None

    # Objeto da Contratação
    objeto: Optional[str] = None
    informacao_complementar: Optional[str] = None

    # Valores (NUNCA substituir ausência por 0.00 fictício)
    valor_estimado: Optional[float] = None
    valor_homologado: Optional[float] = None
    moeda: str = "BRL"

    # Datas oficiais
    data_publicacao_pncp: Optional[str] = None
    data_abertura_proposta: Optional[str] = None
    data_encerramento_proposta: Optional[str] = None
    data_atualizacao_pncp: Optional[str] = None
    data_atualizacao_global: Optional[str] = None

    # Situação
    situacao_compra_id: Optional[int] = None
    situacao_compra_nome: Optional[str] = None
    situacao_prazo: str = "Não informado"  # Aberto, Encerrado, Não informado

    # Links Oficiais e Navegação
    link_pncp: Optional[str] = None  # https://pncp.gov.br/app/editais/{cnpj}/{sequencial}/{ano}
    link_edital: Optional[str] = None  # linkSistemaOrigem ou linkProcessoEletronico

    # Auditoria e Controle Local
    fonte_dados: str = "PNCP"
    data_inclusao_local: Optional[str] = None
    data_atualizacao_local: Optional[str] = None
    raw_json: Optional[str] = None

    # Identificador interno do banco de dados (autoincrement)
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte a entidade para dicionário."""
        return asdict(self)


@dataclass
class Sincronizacao:
    """Registro de operação de coleta/sincronização no histórico."""
    data_inicio: str
    fonte: str = "PNCP"
    filtros_json: Optional[str] = None
    data_fim: Optional[str] = None
    total_recebidos: int = 0
    novos: int = 0
    atualizados: int = 0
    descartados_duplicidade: int = 0
    total_requisicoes: int = 0
    paginas_concluidas: int = 0
    erros: Optional[str] = None
    status: str = "Iniciada"  # Concluída, Concluída com ressalvas, Interrompida, Falhou
    id: Optional[int] = None


@dataclass
class PesquisaSalva:
    """Pesquisa favorita com filtros predefinidos pelo usuário."""
    nome: str
    filtros_json: str
    data_criacao: str
    descricao: Optional[str] = None
    id: Optional[int] = None
