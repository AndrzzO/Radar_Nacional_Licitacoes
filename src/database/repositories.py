"""Repositórios para persistência e consulta dos dados no SQLite."""
from datetime import datetime, timedelta
import json
import sqlite3
from typing import List, Optional, Tuple, Dict, Any

from src.database.connection import DatabaseConnection
from src.domain.entities import Licitacao, Estado, Municipio, Orgao, Sincronizacao, PesquisaSalva
from src.domain.filters import LicitacaoFilter
from src.utils.datetime_utils import get_current_time_sp, compute_situacao_prazo, proposal_status, parse_datetime
from src.utils.logging_config import get_logger

logger = get_logger()


class ProcurementRepository:
    """Repositório de persistência e consulta de Licitações."""

    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn

    def _row_to_entity(self, row: sqlite3.Row) -> Licitacao:
        d = dict(row)
        if d.get('orgao_cnpj') and d.get('ano') and d.get('sequencial'):
            wrong=f"https://pncp.gov.br/app/editais/{d['orgao_cnpj']}/{d['sequencial']}/{d['ano']}"
            if d.get('link_pncp')==wrong: d['link_pncp']=f"https://pncp.gov.br/app/editais/{d['orgao_cnpj']}/{d['ano']}/{d['sequencial']}"
        d["situacao_prazo"] = proposal_status(d["data_encerramento_proposta"],d["data_abertura_proposta"],d["situacao_compra_id"])
        return Licitacao(**d)

    def upsert(self, lic: Licitacao, conn: Optional[sqlite3.Connection] = None) -> Tuple[Licitacao, bool]:
        """
        Insere nova licitação ou atualiza registro existente no banco.
        Preserva a data_inclusao_local original caso já exista.
        Retorna (licitacao_salva, is_new).
        """
        now_iso = get_current_time_sp().isoformat()
        lic.situacao_prazo = compute_situacao_prazo(lic.data_encerramento_proposta)

        def _do_upsert(c: sqlite3.Connection):
            cursor = c.cursor()
            cursor.execute(
                "SELECT id, data_inclusao_local FROM licitacoes WHERE numero_controle_pncp = ?",
                (lic.numero_controle_pncp,),
            )
            existing = cursor.fetchone()

            if existing:
                internal_id = existing["id"]
                data_inclusao_orig = existing["data_inclusao_local"]
                lic.id = internal_id
                lic.data_inclusao_local = data_inclusao_orig
                lic.data_atualizacao_local = now_iso

                cursor.execute(
                    """
                    UPDATE licitacoes SET
                        numero_edital = ?, ano = ?, sequencial = ?, processo = ?,
                        modalidade_id = ?, modalidade_nome = ?, modo_disputa_id = ?, modo_disputa_nome = ?,
                        tipo_instrumento_codigo = ?, tipo_instrumento_nome = ?,
                        orgao_cnpj = ?, orgao_nome = ?, esfera_id = ?, esfera_nome = ?, poder_id = ?, poder_nome = ?,
                        unidade_codigo = ?, unidade_nome = ?, uf_sigla = ?, uf_nome = ?,
                        municipio_nome = ?, municipio_ibge = ?,
                        objeto = ?, informacao_complementar = ?,
                        valor_estimado = ?, valor_homologado = ?, moeda = ?,
                        data_publicacao_pncp = ?, data_abertura_proposta = ?, data_encerramento_proposta = ?,
                        data_atualizacao_pncp = ?, data_atualizacao_global = ?,
                        situacao_compra_id = ?, situacao_compra_nome = ?, situacao_prazo = ?,
                        link_pncp = ?, link_edital = ?, fonte_dados = ?,
                        data_atualizacao_local = ?, raw_json = ?
                    WHERE id = ?
                    """,
                    (
                        lic.numero_edital, lic.ano, lic.sequencial, lic.processo,
                        lic.modalidade_id, lic.modalidade_nome, lic.modo_disputa_id, lic.modo_disputa_nome,
                        lic.tipo_instrumento_codigo, lic.tipo_instrumento_nome,
                        lic.orgao_cnpj, lic.orgao_nome, lic.esfera_id, lic.esfera_nome, lic.poder_id, lic.poder_nome,
                        lic.unidade_codigo, lic.unidade_nome, lic.uf_sigla, lic.uf_nome,
                        lic.municipio_nome, lic.municipio_ibge,
                        lic.objeto, lic.informacao_complementar,
                        lic.valor_estimado, lic.valor_homologado, lic.moeda,
                        lic.data_publicacao_pncp, lic.data_abertura_proposta, lic.data_encerramento_proposta,
                        lic.data_atualizacao_pncp, lic.data_atualizacao_global,
                        lic.situacao_compra_id, lic.situacao_compra_nome, lic.situacao_prazo,
                        lic.link_pncp, lic.link_edital, lic.fonte_dados,
                        lic.data_atualizacao_local, lic.raw_json,
                        internal_id,
                    ),
                )
                return lic, False
            else:
                lic.data_inclusao_local = now_iso
                lic.data_atualizacao_local = now_iso
                cursor.execute(
                    """
                    INSERT INTO licitacoes (
                        numero_controle_pncp, numero_edital, ano, sequencial, processo,
                        modalidade_id, modalidade_nome, modo_disputa_id, modo_disputa_nome,
                        tipo_instrumento_codigo, tipo_instrumento_nome,
                        orgao_cnpj, orgao_nome, esfera_id, esfera_nome, poder_id, poder_nome,
                        unidade_codigo, unidade_nome, uf_sigla, uf_nome,
                        municipio_nome, municipio_ibge,
                        objeto, informacao_complementar,
                        valor_estimado, valor_homologado, moeda,
                        data_publicacao_pncp, data_abertura_proposta, data_encerramento_proposta,
                        data_atualizacao_pncp, data_atualizacao_global,
                        situacao_compra_id, situacao_compra_nome, situacao_prazo,
                        link_pncp, link_edital, fonte_dados,
                        data_inclusao_local, data_atualizacao_local, raw_json
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        lic.numero_controle_pncp, lic.numero_edital, lic.ano, lic.sequencial, lic.processo,
                        lic.modalidade_id, lic.modalidade_nome, lic.modo_disputa_id, lic.modo_disputa_nome,
                        lic.tipo_instrumento_codigo, lic.tipo_instrumento_nome,
                        lic.orgao_cnpj, lic.orgao_nome, lic.esfera_id, lic.esfera_nome, lic.poder_id, lic.poder_nome,
                        lic.unidade_codigo, lic.unidade_nome, lic.uf_sigla, lic.uf_nome,
                        lic.municipio_nome, lic.municipio_ibge,
                        lic.objeto, lic.informacao_complementar,
                        lic.valor_estimado, lic.valor_homologado, lic.moeda,
                        lic.data_publicacao_pncp, lic.data_abertura_proposta, lic.data_encerramento_proposta,
                        lic.data_atualizacao_pncp, lic.data_atualizacao_global,
                        lic.situacao_compra_id, lic.situacao_compra_nome, lic.situacao_prazo,
                        lic.link_pncp, lic.link_edital, lic.fonte_dados,
                        lic.data_inclusao_local, lic.data_atualizacao_local, lic.raw_json,
                    ),
                )
                lic.id = cursor.lastrowid
                return lic, True

        if conn:
            return _do_upsert(conn)
        else:
            with self.db.session() as s:
                return _do_upsert(s)

    def upsert_batch(self, licitacoes: List[Licitacao]) -> Tuple[int, int]:
        """
        Salva lote de licitações em transação única.
        Retorna (novos_count, atualizados_count).
        """
        novos = 0
        atualizados = 0
        with self.db.session() as conn:
            for lic in licitacoes:
                _, is_new = self.upsert(lic, conn=conn)
                if is_new:
                    novos += 1
                else:
                    atualizados += 1
        from src.classification.store import ClassificationStore
        try:
            ClassificationStore(self.db).classify_batch(licitacoes)
        except Exception:
            logger.exception("Classificação pendente; registros oficiais preservados")
        return novos, atualizados

    def get_by_pncp_id(self, numero_controle: str) -> Optional[Licitacao]:
        """Obtém uma licitação pelo seu identificador único oficial no PNCP."""
        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM licitacoes WHERE numero_controle_pncp = ?",
                (numero_controle,),
            )
            row = cursor.fetchone()
            return self._row_to_entity(row) if row else None

    def _build_where_clause(self, f: LicitacaoFilter) -> Tuple[str, List[Any]]:
        conditions = []
        params = []

        # UFs
        if f.ufs:
            placeholders = ",".join("?" for _ in f.ufs)
            conditions.append(f"uf_sigla IN ({placeholders})")
            params.extend(f.ufs)

        # Municípios por código IBGE
        if f.municipios_ibge:
            placeholders = ",".join("?" for _ in f.municipios_ibge)
            conditions.append(f"municipio_ibge IN ({placeholders})")
            params.extend(f.municipios_ibge)

        # Esferas
        if f.esferas:
            placeholders = ",".join("?" for _ in f.esferas)
            conditions.append(f"esfera_id IN ({placeholders})")
            params.extend(f.esferas)

        # Modalidades
        if f.modalidades_ids:
            placeholders = ",".join("?" for _ in f.modalidades_ids)
            conditions.append(f"modalidade_id IN ({placeholders})")
            params.extend(f.modalidades_ids)

        # Status / Situação do prazo
        if f.status_proposta == "recebendo_proposta":
            conditions.append("proposal_status(data_encerramento_proposta,data_abertura_proposta,situacao_compra_id) = 'Aberto'")
        elif f.status_proposta == "encerradas":
            conditions.append("proposal_status(data_encerramento_proposta,data_abertura_proposta,situacao_compra_id) = 'Encerrado'")

        for field, start, end in (("data_publicacao_pncp", f.data_publicacao_inicio, f.data_publicacao_fim), ("data_encerramento_proposta", f.data_encerramento_inicio, f.data_encerramento_fim)):
            if start:
                dt=parse_datetime(start)
                if not dt: raise ValueError("Data inicial inválida")
                conditions.append(f"timestamp_sp({field}) >= ?"); params.append(dt.timestamp())
            if end:
                dt=parse_datetime(end)
                if not dt: raise ValueError("Data final inválida")
                conditions.append(f"timestamp_sp({field}) < ?"); params.append((dt.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)).timestamp())
        if f.prazo_dias:
            current=get_current_time_sp()
            conditions.append("timestamp_sp(data_encerramento_proposta) BETWEEN ? AND ?")
            params.extend([current.timestamp(),(current+timedelta(days=f.prazo_dias)).timestamp()])
        if f.only_unclassified:
            conditions.append("NOT EXISTS(SELECT 1 FROM classification_state s JOIN classifications x ON x.run_id=coalesce(s.manual_id,s.automatic_id) WHERE s.procurement_id=licitacoes.id AND x.is_primary=1)")
        if f.category_ids or f.subcategory_ids or f.confidence_levels:
            match=["x.run_id=coalesce(s.manual_id,s.automatic_id)"]
            for values,column in ((f.category_ids,'category_id'),(f.subcategory_ids,'subcategory_id'),(f.confidence_levels,'confidence')):
                if values:
                    match.append(f"x.{column} IN ({','.join('?' for _ in values)})"); params.extend(values)
            if f.primary_category_only: match.append('x.is_primary=1')
            conditions.append("EXISTS(SELECT 1 FROM classification_state s JOIN classifications x ON x.run_id=coalesce(s.manual_id,s.automatic_id) WHERE s.procurement_id=licitacoes.id AND "+' AND '.join(match)+')')
        if f.classification_origin:
            conditions.append("EXISTS(SELECT 1 FROM classification_state s JOIN classification_runs r ON r.id=coalesce(s.manual_id,s.automatic_id) WHERE s.procurement_id=licitacoes.id AND r.origin=?)")
            params.append(f.classification_origin)

        # Palavra-chave no objeto ou informacao complementar
        if f.palavra_chave:
            termo = f"%{f.palavra_chave.strip()}%"
            conditions.append("(objeto LIKE ? OR informacao_complementar LIKE ?)")
            params.extend([termo, termo])

        # Número do edital ou processo
        if f.numero_edital:
            termo_edital = f"%{f.numero_edital.strip()}%"
            conditions.append("(numero_edital LIKE ? OR processo LIKE ? OR numero_controle_pncp LIKE ?)")
            params.extend([termo_edital, termo_edital, termo_edital])

        # Órgão Comprador (Nome ou CNPJ)
        if f.orgao:
            termo_orgao = f"%{f.orgao.strip()}%"
            conditions.append("(orgao_nome LIKE ? OR orgao_cnpj LIKE ?)")
            params.extend([termo_orgao, termo_orgao])

        # Faixa de valor
        if f.valor_min is not None:
            conditions.append("valor_estimado >= ?")
            params.append(f.valor_min)
        if f.valor_max is not None:
            conditions.append("valor_estimado <= ?")
            params.append(f.valor_max)

        where_str = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return where_str, params

    def search(self, f: LicitacaoFilter) -> Tuple[List[Licitacao], int]:
        """
        Executa pesquisa com filtros dinâmicos no SQLite.
        Retorna (lista_licitacoes, total_registros_filtrados).
        """
        where_str, params = self._build_where_clause(f)

        # Ordenação segura
        colunas_validas = {
            "data_encerramento_proposta", "data_publicacao_pncp", "valor_estimado",
            "orgao_nome", "municipio_nome", "uf_sigla", "numero_edital"
        }
        ordem_col = f.ordenar_por if f.ordenar_por in colunas_validas else "data_encerramento_proposta"
        classification_sort={
            'category_name': 'cat.name', 'subcategory_name':'sub.name',
            'classification_confidence':'x.confidence','classification_origin':'r.origin'}
        if f.ordenar_por in classification_sort:
            column=classification_sort[f.ordenar_por]
            ordem_col=f"(SELECT {column} FROM classification_state s JOIN classification_runs r ON r.id=coalesce(s.manual_id,s.automatic_id) LEFT JOIN classifications x ON x.run_id=r.id AND x.is_primary=1 LEFT JOIN categories cat ON cat.id=x.category_id LEFT JOIN subcategories sub ON sub.id=x.subcategory_id WHERE s.procurement_id=licitacoes.id)"
        ordem_dir = "ASC" if f.ordem_asc else "DESC"

        # Consulta com contagem total
        count_sql = f"SELECT COUNT(*) as total FROM licitacoes {where_str}"
        select_sql = f"""
            SELECT * FROM licitacoes
            {where_str}
            ORDER BY {ordem_col} {ordem_dir} NULLS LAST, id ASC
            LIMIT ? OFFSET ?
        """

        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute(count_sql, params)
            total = cursor.fetchone()["total"]

            query_params = list(params) + [f.limite, f.offset]
            cursor.execute(select_sql, query_params)
            rows = cursor.fetchall()
            items = [self._row_to_entity(r) for r in rows]

            self._attach_classifications(items)
            return items, total

    def get_all_for_export(
        self,
        f: LicitacaoFilter,
        selected_pncp_ids: Optional[List[str]] = None,
    ) -> List[Licitacao]:
        """Obtém todos os registros filtrados ou selecionados para exportação sem limite de paginação."""
        with self.db.session() as conn:
            cursor = conn.cursor()
            if selected_pncp_ids is not None:
                placeholders = ",".join("?" for _ in selected_pncp_ids)
                sql = f"SELECT * FROM licitacoes WHERE numero_controle_pncp IN ({placeholders}) ORDER BY data_encerramento_proposta ASC"
                cursor.execute(sql, selected_pncp_ids)
            else:
                where_str, params = self._build_where_clause(f)
                sql = f"SELECT * FROM licitacoes {where_str} ORDER BY data_encerramento_proposta ASC NULLS LAST"
                cursor.execute(sql, params)

            rows = cursor.fetchall()
            items = [self._row_to_entity(r) for r in rows]
            self._attach_classifications(items)
            return items

    def _attach_classifications(self, items):
        from src.classification.store import ClassificationStore
        data=ClassificationStore(self.db).effective([x.id for x in items])
        for item in items: item.classification=data.get(item.id, {})

    def get_statistics(self) -> Dict[str, Any]:
        """Calcula indicadores reais para o Painel Geral."""
        with self.db.session() as conn:
            cursor = conn.cursor()

            # Totais gerais
            cursor.execute("SELECT COUNT(*) as total FROM licitacoes")
            total = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as aberto FROM licitacoes WHERE proposal_status(data_encerramento_proposta,data_abertura_proposta,situacao_compra_id) = 'Aberto'")
            aberto = cursor.fetchone()["aberto"]

            cursor.execute("SELECT COUNT(*) as encerrado FROM licitacoes WHERE proposal_status(data_encerramento_proposta,data_abertura_proposta,situacao_compra_id) = 'Encerrado'")
            encerrado = cursor.fetchone()["encerrado"]

            cursor.execute("SELECT COUNT(*) as nao_inf FROM licitacoes WHERE proposal_status(data_encerramento_proposta,data_abertura_proposta,situacao_compra_id) = 'Não informado'")
            nao_inf = cursor.fetchone()["nao_inf"]

            cursor.execute("SELECT COUNT(DISTINCT uf_sigla) as ufs FROM licitacoes WHERE uf_sigla IS NOT NULL")
            total_ufs = cursor.fetchone()["ufs"]

            cursor.execute("SELECT COUNT(DISTINCT orgao_cnpj) as orgaos FROM licitacoes WHERE orgao_cnpj IS NOT NULL")
            total_orgaos = cursor.fetchone()["orgaos"]

            # Última sincronização concluída
            cursor.execute(
                """
                SELECT data_fim, novos FROM sincronizacoes
                WHERE status IN ('Concluída', 'Concluída com ressalvas')
                ORDER BY id DESC LIMIT 1
                """
            )
            last_sync = cursor.fetchone()

            data_ultima_sinc = last_sync["data_fim"] if last_sync else None
            novos_ultima_sinc = last_sync["novos"] if last_sync else 0

            return {
                "total_registros": total,
                "prazo_aberto": aberto,
                "prazo_encerrado": encerrado,
                "prazo_nao_informado": nao_inf,
                "total_ufs": total_ufs,
                "total_orgaos": total_orgaos,
                "novos_ultima_sinc": novos_ultima_sinc,
                "data_ultima_sinc": data_ultima_sinc,
            }


class LocationRepository:
    """Repositório de persistência de UFs e Municípios do IBGE."""

    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn

    def save_estados(self, estados: List[Estado]):
        with self.db.session() as conn:
            cursor = conn.cursor()
            for e in estados:
                cursor.execute(
                    "INSERT INTO estados (uf_sigla, nome, id_ibge) VALUES (?, ?, ?) ON CONFLICT(uf_sigla) DO UPDATE SET nome=excluded.nome, id_ibge=excluded.id_ibge",
                    (e.uf_sigla, e.nome, e.id_ibge),
                )

    def get_estados(self) -> List[Estado]:
        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM estados ORDER BY uf_sigla ASC")
            rows = cursor.fetchall()
            return [Estado(uf_sigla=r["uf_sigla"], nome=r["nome"], id_ibge=r["id_ibge"]) for r in rows]

    def save_municipios(self, municipios: List[Municipio]):
        with self.db.session() as conn:
            cursor = conn.cursor()
            for m in municipios:
                cursor.execute(
                    "INSERT OR IGNORE INTO estados (uf_sigla, nome) VALUES (?, ?)",
                    (m.uf_sigla, m.uf_nome or m.uf_sigla),
                )
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO municipios (codigo_ibge, nome, uf_sigla, uf_nome)
                    VALUES (?, ?, ?, ?)
                    """,
                    (m.codigo_ibge, m.nome, m.uf_sigla, m.uf_nome),
                )

    def get_municipios_por_uf(self, uf: str) -> List[Municipio]:
        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM municipios WHERE uf_sigla = ? ORDER BY nome ASC", (uf.upper(),))
            rows = cursor.fetchall()
            return [
                Municipio(codigo_ibge=r["codigo_ibge"], nome=r["nome"], uf_sigla=r["uf_sigla"], uf_nome=r["uf_nome"])
                for r in rows
            ]

    def search_municipios(self, termo: str, ufs: Optional[List[str]] = None) -> List[Municipio]:
        with self.db.session() as conn:
            cursor = conn.cursor()
            params = [f"%{termo.strip()}%"]
            sql = "SELECT * FROM municipios WHERE nome LIKE ?"
            if ufs:
                placeholders = ",".join("?" for _ in ufs)
                sql += f" AND uf_sigla IN ({placeholders})"
                params.extend(ufs)
            sql += " ORDER BY nome ASC LIMIT 100"
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [
                Municipio(codigo_ibge=r["codigo_ibge"], nome=r["nome"], uf_sigla=r["uf_sigla"], uf_nome=r["uf_nome"])
                for r in rows
            ]


class SyncRepository:
    """Repositório de histórico das operações de sincronização e coleta."""

    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn

    def create_sync(self, sync: Sincronizacao) -> int:
        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sincronizacoes (
                    data_inicio, data_fim, fonte, filtros_json,
                    total_recebidos, novos, atualizados, descartados_duplicidade,
                    total_requisicoes, paginas_concluidas, erros, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sync.data_inicio, sync.data_fim, sync.fonte, sync.filtros_json,
                    sync.total_recebidos, sync.novos, sync.atualizados, sync.descartados_duplicidade,
                    sync.total_requisicoes, sync.paginas_concluidas, sync.erros, sync.status,
                ),
            )
            sync.id = cursor.lastrowid
            return sync.id

    def update_sync(self, sync: Sincronizacao):
        if not sync.id:
            return
        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sincronizacoes SET
                    data_fim = ?, total_recebidos = ?, novos = ?, atualizados = ?,
                    descartados_duplicidade = ?, total_requisicoes = ?, paginas_concluidas = ?,
                    erros = ?, status = ?
                WHERE id = ?
                """,
                (
                    sync.data_fim, sync.total_recebidos, sync.novos, sync.atualizados,
                    sync.descartados_duplicidade, sync.total_requisicoes, sync.paginas_concluidas,
                    sync.erros, sync.status, sync.id,
                ),
            )

    def list_history(self, limit: int = 50) -> List[Sincronizacao]:
        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sincronizacoes ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [Sincronizacao(**dict(r)) for r in rows]


class SavedSearchRepository:
    """Repositório de pesquisas favoritas do usuário."""

    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn

    def save(self, item: PesquisaSalva) -> int:
        with self.db.session() as conn:
            cursor = conn.cursor()
            if item.id:
                cursor.execute(
                    "UPDATE pesquisas_salvas SET nome = ?, descricao = ?, filtros_json = ? WHERE id = ?",
                    (item.nome, item.descricao, item.filtros_json, item.id),
                )
                return item.id
            else:
                cursor.execute(
                    "INSERT INTO pesquisas_salvas (nome, descricao, filtros_json, data_criacao) VALUES (?, ?, ?, ?)",
                    (item.nome, item.descricao, item.filtros_json, item.data_criacao),
                )
                item.id = cursor.lastrowid
                return item.id

    def list_all(self) -> List[PesquisaSalva]:
        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pesquisas_salvas ORDER BY nome ASC")
            rows = cursor.fetchall()
            return [PesquisaSalva(**dict(r)) for r in rows]

    def delete(self, item_id: int):
        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pesquisas_salvas WHERE id = ?", (item_id,))


class SettingsRepository:
    """Repositório de configurações do aplicativo."""

    def __init__(self, db_conn: DatabaseConnection):
        self.db = db_conn

    def get(self, chave: str, default: Optional[str] = None) -> Optional[str]:
        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT valor FROM configuracoes WHERE chave = ?", (chave,))
            row = cursor.fetchone()
            return row["valor"] if row else default

    def set(self, chave: str, valor: str):
        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)",
                (chave, valor),
            )

    def get_all(self) -> Dict[str, str]:
        with self.db.session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chave, valor FROM configuracoes")
            return {r["chave"]: r["valor"] for r in cursor.fetchall()}
