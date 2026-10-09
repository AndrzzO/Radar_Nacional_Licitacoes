"""Adaptador para conversão de dados brutos do PNCP para o modelo de domínio."""
import json
from typing import Dict, Any, Optional
from src.domain.entities import Licitacao
from src.utils.datetime_utils import compute_situacao_prazo, get_current_time_sp

ESFERAS_MAP = {
    "M": "Municipal",
    "E": "Estadual",
    "F": "Federal",
    "D": "Distrital",
}

PODERES_MAP = {
    "E": "Executivo",
    "L": "Legislativo",
    "J": "Judiciário",
}


class PNCPAdapter:
    """Converte e normaliza payloads de contratação retornados pela API oficial do PNCP."""

    @staticmethod
    def parse_licitacao(data: Dict[str, Any]) -> Licitacao:
        """
        Converte um dicionário JSON retornado pelo PNCP em uma entidade Licitacao.
        Preserva valores nulos sem inventar números ou datas.
        """
        orgao = data.get("orgaoEntidade") or {}
        unidade = data.get("unidadeOrgao") or {}

        # Identificação e Chaves
        numero_controle = data.get("numeroControlePNCP") or ""
        cnpj = orgao.get("cnpj") or ""
        ano = data.get("anoCompra")
        sequencial = data.get("sequencialCompra")
        numero_compra = data.get("numeroCompra")
        processo = data.get("processo")

        # Esfera e Poder
        esfera_id = orgao.get("esferaId")
        esfera_nome = ESFERAS_MAP.get(esfera_id, esfera_id) if esfera_id else None

        poder_id = orgao.get("poderId")
        poder_nome = PODERES_MAP.get(poder_id, poder_id) if poder_id else None

        # Modalidade e Disputa
        modalidade_id = data.get("modalidadeId")
        modalidade_nome = data.get("modalidadeNome")
        modo_disputa_id = data.get("modoDisputaId")
        modo_disputa_nome = data.get("modoDisputaNome")
        tipo_instrumento_codigo = data.get("tipoInstrumentoConvocatorioCodigo")
        tipo_instrumento_nome = data.get("tipoInstrumentoConvocatorioNome")

        # Localidade
        uf_sigla = unidade.get("ufSigla")
        uf_nome = unidade.get("ufNome")
        municipio_nome = unidade.get("municipioNome")
        codigo_ibge = unidade.get("codigoIbge")
        if codigo_ibge is not None:
            codigo_ibge = str(codigo_ibge).strip()

        # Objeto e complementares
        objeto = data.get("objetoCompra")
        informacao_complementar = data.get("informacaoComplementar")

        # Valores
        valor_estimado = data.get("valorTotalEstimado")
        if valor_estimado is not None:
            try:
                valor_estimado = float(valor_estimado)
            except (ValueError, TypeError):
                valor_estimado = None

        valor_homologado = data.get("valorTotalHomologado")
        if valor_homologado is not None:
            try:
                valor_homologado = float(valor_homologado)
            except (ValueError, TypeError):
                valor_homologado = None

        # Datas
        data_publicacao = data.get("dataPublicacaoPncp")
        data_abertura = data.get("dataAberturaProposta")
        data_encerramento = data.get("dataEncerramentoProposta")
        data_atualizacao = data.get("dataAtualizacao") or data.get("dataAtualizacaoPncp")
        data_atualizacao_global = data.get("dataAtualizacaoGlobal")

        # Situação
        situacao_id = data.get("situacaoCompraId")
        situacao_nome = data.get("situacaoCompraNome")
        situacao_prazo = compute_situacao_prazo(data_encerramento)

        # Links Oficiais
        # Formato verificado no portal: https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}
        link_pncp = None
        if cnpj and sequencial is not None and ano is not None:
            link_pncp = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}"

        link_edital = data.get("linkSistemaOrigem") or data.get("linkProcessoEletronico")

        # Metadados locais de auditoria
        agora_iso = get_current_time_sp().isoformat()
        raw_json_str = json.dumps(data, ensure_ascii=False)

        return Licitacao(
            numero_controle_pncp=numero_controle,
            numero_edital=numero_compra,
            ano=ano,
            sequencial=sequencial,
            processo=processo,
            modalidade_id=modalidade_id,
            modalidade_nome=modalidade_nome,
            modo_disputa_id=modo_disputa_id,
            modo_disputa_nome=modo_disputa_nome,
            tipo_instrumento_codigo=tipo_instrumento_codigo,
            tipo_instrumento_nome=tipo_instrumento_nome,
            orgao_cnpj=cnpj,
            orgao_nome=orgao.get("razaoSocial"),
            esfera_id=esfera_id,
            esfera_nome=esfera_nome,
            poder_id=poder_id,
            poder_nome=poder_nome,
            unidade_codigo=str(unidade.get("codigoUnidade")) if unidade.get("codigoUnidade") is not None else None,
            unidade_nome=unidade.get("nomeUnidade"),
            uf_sigla=uf_sigla,
            uf_nome=uf_nome,
            municipio_nome=municipio_nome,
            municipio_ibge=codigo_ibge,
            objeto=objeto,
            informacao_complementar=informacao_complementar,
            valor_estimado=valor_estimado,
            valor_homologado=valor_homologado,
            moeda="BRL",
            data_publicacao_pncp=data_publicacao,
            data_abertura_proposta=data_abertura,
            data_encerramento_proposta=data_encerramento,
            data_atualizacao_pncp=data_atualizacao,
            data_atualizacao_global=data_atualizacao_global,
            situacao_compra_id=situacao_id,
            situacao_compra_nome=situacao_nome,
            situacao_prazo=situacao_prazo,
            link_pncp=link_pncp,
            link_edital=link_edital,
            fonte_dados="PNCP",
            data_inclusao_local=agora_iso,
            data_atualizacao_local=agora_iso,
            raw_json=raw_json_str,
        )
