"""Criação e evolução do esquema do banco de dados SQLite."""
import sqlite3
from src.utils.logging_config import get_logger

logger = get_logger()

SCHEMA_SQL = """
-- Tabela de Estados (UFs)
CREATE TABLE IF NOT EXISTS estados (
    uf_sigla TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    id_ibge INTEGER
);

-- Tabela de Municípios com código IBGE
CREATE TABLE IF NOT EXISTS municipios (
    codigo_ibge TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    uf_sigla TEXT NOT NULL,
    uf_nome TEXT,
    FOREIGN KEY (uf_sigla) REFERENCES estados(uf_sigla) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_municipios_uf ON municipios(uf_sigla);
CREATE INDEX IF NOT EXISTS idx_municipios_nome ON municipios(nome);

-- Tabela de Órgãos Compradores
CREATE TABLE IF NOT EXISTS orgaos (
    cnpj TEXT PRIMARY KEY,
    razao_social TEXT NOT NULL,
    poder_id TEXT,
    poder_nome TEXT,
    esfera_id TEXT,
    esfera_nome TEXT
);

-- Tabela Principal de Licitações / Contratações
CREATE TABLE IF NOT EXISTS licitacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_controle_pncp TEXT NOT NULL UNIQUE,
    numero_edital TEXT,
    ano INTEGER,
    sequencial INTEGER,
    processo TEXT,
    
    modalidade_id INTEGER,
    modalidade_nome TEXT,
    modo_disputa_id INTEGER,
    modo_disputa_nome TEXT,
    tipo_instrumento_codigo INTEGER,
    tipo_instrumento_nome TEXT,
    
    orgao_cnpj TEXT,
    orgao_nome TEXT,
    esfera_id TEXT,
    esfera_nome TEXT,
    poder_id TEXT,
    poder_nome TEXT,
    
    unidade_codigo TEXT,
    unidade_nome TEXT,
    uf_sigla TEXT,
    uf_nome TEXT,
    municipio_nome TEXT,
    municipio_ibge TEXT,
    
    objeto TEXT,
    informacao_complementar TEXT,
    
    valor_estimado REAL,
    valor_homologado REAL,
    moeda TEXT DEFAULT 'BRL',
    
    data_publicacao_pncp TEXT,
    data_abertura_proposta TEXT,
    data_encerramento_proposta TEXT,
    data_atualizacao_pncp TEXT,
    data_atualizacao_global TEXT,
    
    situacao_compra_id INTEGER,
    situacao_compra_nome TEXT,
    situacao_prazo TEXT NOT NULL DEFAULT 'Não informado',
    
    link_pncp TEXT,
    link_edital TEXT,
    
    fonte_dados TEXT DEFAULT 'PNCP',
    data_inclusao_local TEXT NOT NULL,
    data_atualizacao_local TEXT NOT NULL,
    raw_json TEXT
);

-- Índices de alta performance para buscas
CREATE INDEX IF NOT EXISTS idx_licitacoes_pncp ON licitacoes(numero_controle_pncp);
CREATE INDEX IF NOT EXISTS idx_licitacoes_uf ON licitacoes(uf_sigla);
CREATE INDEX IF NOT EXISTS idx_licitacoes_ibge ON licitacoes(municipio_ibge);
CREATE INDEX IF NOT EXISTS idx_licitacoes_modalidade ON licitacoes(modalidade_id);
CREATE INDEX IF NOT EXISTS idx_licitacoes_esfera ON licitacoes(esfera_id);
CREATE INDEX IF NOT EXISTS idx_licitacoes_dt_pub ON licitacoes(data_publicacao_pncp);
CREATE INDEX IF NOT EXISTS idx_licitacoes_dt_enc ON licitacoes(data_encerramento_proposta);
CREATE INDEX IF NOT EXISTS idx_licitacoes_cnpj ON licitacoes(orgao_cnpj);
CREATE INDEX IF NOT EXISTS idx_licitacoes_prazo ON licitacoes(situacao_prazo);

-- Tabela de Histórico de Sincronizações / Coletas
CREATE TABLE IF NOT EXISTS sincronizacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_inicio TEXT NOT NULL,
    data_fim TEXT,
    fonte TEXT NOT NULL DEFAULT 'PNCP',
    filtros_json TEXT,
    total_recebidos INTEGER DEFAULT 0,
    novos INTEGER DEFAULT 0,
    atualizados INTEGER DEFAULT 0,
    descartados_duplicidade INTEGER DEFAULT 0,
    total_requisicoes INTEGER DEFAULT 0,
    paginas_concluidas INTEGER DEFAULT 0,
    erros TEXT,
    status TEXT NOT NULL DEFAULT 'Iniciada'
);

-- Tabela de Pesquisas Salvas (Favoritas)
CREATE TABLE IF NOT EXISTS pesquisas_salvas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    descricao TEXT,
    filtros_json TEXT NOT NULL,
    data_criacao TEXT NOT NULL
);

-- Tabela de Configurações do Aplicativo
CREATE TABLE IF NOT EXISTS configuracoes (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""


def init_database(conn: sqlite3.Connection):
    """Executa scripts de criação e atualização de tabelas e índices."""
    logger.info("Inicializando esquema do banco de dados local SQLite...")
    for statement in SCHEMA_SQL.split(";"):
        if statement.strip():
            conn.execute(statement)
    from src.classification.store import migrate
    migrate(conn)
    logger.info("Esquema do banco de dados inicializado com sucesso.")
