"""Cliente HTTP robusto para comunicação com a API oficial do PNCP."""
import time
import random
from typing import Dict, Any, Optional, Callable
import httpx

from src.utils.logging_config import get_logger

logger = get_logger()

DEFAULT_BASE_URL = "https://pncp.gov.br/api/consulta/v1"
DEFAULT_TIMEOUT = 25.0
DEFAULT_MAX_RETRIES = 5
DEFAULT_REQUEST_INTERVAL = 1.2  # Intervalo de cortesia para não sobrecarregar


class PNCPClientError(Exception):
    """Exceção base para erros na integração com o PNCP."""
    pass


class PNCPRateLimitError(PNCPClientError):
    """Exceção lançada quando a API retorna HTTP 429 persistente."""
    pass


class PNCPClient:
    """
    Cliente HTTPX para a API de Consulta do Portal Nacional de Contratações Públicas (PNCP).
    Possui gerenciamento de conexões reutilizáveis, retentativas com recuo exponencial,
    tratamento de HTTP 429 e cancelamento cooperativo.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        request_interval: float = DEFAULT_REQUEST_INTERVAL,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.request_interval = request_interval
        self._last_request_time = 0.0
        self.request_count = 0

        headers = {
            "User-Agent": "RadarNacionalLicitacoes/1.0 (Windows; Desktop; Contratacoes Publicas)",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate",
        }
        self.client = httpx.Client(
            timeout=self.timeout,
            headers=headers,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

    def close(self):
        """Fecha o cliente HTTP e libera conexões."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _wait(self, seconds, check_cancelled=None):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if check_cancelled and check_cancelled():
                raise PNCPClientError("Operação cancelada pelo usuário.")
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))

    def _throttle(self, check_cancelled: Optional[Callable[[], bool]] = None):
        """Aplica espaçamento respeitoso entre requisições consecutivas."""
        if check_cancelled and check_cancelled():
            raise PNCPClientError("Operação cancelada pelo usuário.")

        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_interval:
            sleep_time = self.request_interval - elapsed
            self._wait(sleep_time, check_cancelled)

    def _request_with_retry(
        self,
        endpoint: str,
        params: Dict[str, Any],
        check_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Executa requisição GET com recuo exponencial e jitter para 429 e 5xx.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        clean_params = {k: v for k, v in params.items() if v is not None}

        attempt = 0
        backoff = 2.0

        while attempt < self.max_retries:
            if check_cancelled and check_cancelled():
                raise PNCPClientError("Operação cancelada pelo usuário.")

            self._throttle(check_cancelled)
            attempt += 1

            try:
                self._last_request_time = time.time()
                self.request_count += 1
                response = self.client.get(url, params=clean_params)

                # Sucesso
                if response.status_code == 200:
                    try:
                        return response.json()
                    except Exception as e:
                        logger.error(f"Erro ao decodificar JSON de {url}: {e}")
                        raise PNCPClientError(f"Resposta JSON inválida da API do PNCP: {e}")

                elif response.status_code == 204:
                    return {"data": [], "totalPaginas": 0, "totalRegistros": 0, "numeroPagina": params.get("pagina", 1)}

                # Rate Limit (HTTP 429)
                elif response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait_time = backoff
                    if retry_after:
                        try: wait_time=max(0,float(retry_after))
                        except ValueError:
                            from email.utils import parsedate_to_datetime
                            from datetime import datetime, timezone
                            try: wait_time=max(0,(parsedate_to_datetime(retry_after)-datetime.now(timezone.utc)).total_seconds())
                            except (ValueError,TypeError,OverflowError): pass
                    if attempt >= self.max_retries or wait_time > 120:
                        raise PNCPRateLimitError('HTTP 429 persistente. Aguarde antes de repetir a coleta.')
                    wait_time += random.uniform(0.5, 1.5)
                    logger.warning(
                        f"HTTP 429 (Taxa excedida) no PNCP. Tentativa {attempt}/{self.max_retries}. "
                        f"Aguardando {wait_time:.1f}s..."
                    )
                    self._wait(min(wait_time, 120), check_cancelled)
                    backoff = min(backoff * 2.0, 30.0)
                    continue

                # Erros transitórios de servidor (500, 502, 503, 504)
                elif 500 <= response.status_code <= 599:
                    logger.warning(
                        f"HTTP {response.status_code} no PNCP. Tentativa {attempt}/{self.max_retries}. "
                        f"Aguardando {backoff:.1f}s..."
                    )
                    self._wait(backoff + random.uniform(0.2, 1.0), check_cancelled)
                    backoff = min(backoff * 2.0, 30.0)
                    continue

                # Erro 400 ou 404 (parâmetro inválido ou não encontrado)
                elif response.status_code in (400, 404):
                    msg = f"HTTP {response.status_code} ao consultar {url} com params {clean_params}: {response.text[:200]}"
                    logger.error(msg)
                    raise PNCPClientError(msg)

                else:
                    raise PNCPClientError(f"HTTP {response.status_code}: {response.text[:200]}")

            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
                logger.warning(
                    f"Falha de rede/timeout ({type(e).__name__}) ao conectar ao PNCP. "
                    f"Tentativa {attempt}/{self.max_retries}: {e}"
                )
                if attempt >= self.max_retries:
                    raise PNCPClientError(f"Falha de conexão com o PNCP após {self.max_retries} tentativas: {e}")
                self._wait(backoff + random.uniform(0.2, 1.0), check_cancelled)
                backoff = min(backoff * 2.0, 30.0)

        raise PNCPRateLimitError(
            f"Não foi possível obter resposta do PNCP após {self.max_retries} tentativas devido a limites ou indisponibilidade."
        )

    def get_propostas(
        self,
        data_final: str,
        data_inicial: Optional[str] = None,
        uf: Optional[str] = None,
        codigo_ibge: Optional[str] = None,
        modalidade_id: Optional[int] = None,
        cnpj: Optional[str] = None,
        pagina: int = 1,
        tamanho_pagina: int = 50,
        check_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Consulta contratações com recebimento de propostas aberto.
        Endpoint: /v1/contratacoes/proposta
        """
        params = {
            "dataFinal": data_final,
            "uf": uf,
            "codigoMunicipioIbge": codigo_ibge,
            "codigoModalidadeContratacao": modalidade_id,
            "cnpj": cnpj,
            "pagina": pagina,
            "tamanhoPagina": max(10, min(tamanho_pagina, 50)),
        }
        return self._request_with_retry("contratacoes/proposta", params, check_cancelled)

    def get_publicacoes(
        self,
        data_inicial: str,
        data_final: str,
        modalidade_id: int,
        uf: Optional[str] = None,
        codigo_ibge: Optional[str] = None,
        cnpj: Optional[str] = None,
        pagina: int = 1,
        tamanho_pagina: int = 50,
        check_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Consulta contratações por data de publicação.
        Endpoint: /v1/contratacoes/publicacao
        """
        params = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": modalidade_id,
            "uf": uf,
            "codigoMunicipioIbge": codigo_ibge,
            "cnpj": cnpj,
            "pagina": pagina,
            "tamanhoPagina": max(10, min(tamanho_pagina, 50)),
        }
        return self._request_with_retry("contratacoes/publicacao", params, check_cancelled)

    def get_atualizacoes(
        self,
        data_inicial: str,
        data_final: str,
        modalidade_id: int,
        uf: Optional[str] = None,
        codigo_ibge: Optional[str] = None,
        cnpj: Optional[str] = None,
        pagina: int = 1,
        tamanho_pagina: int = 50,
        check_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Consulta contratações por data de atualização global.
        Endpoint: /v1/contratacoes/atualizacao
        """
        params = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": modalidade_id,
            "uf": uf,
            "codigoMunicipioIbge": codigo_ibge,
            "cnpj": cnpj,
            "pagina": pagina,
            "tamanhoPagina": max(10, min(tamanho_pagina, 50)),
        }
        return self._request_with_retry("contratacoes/atualizacao", params, check_cancelled)

    def get_compra(
        self,
        cnpj: str,
        ano: int,
        sequencial: int,
        check_cancelled: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Consulta os detalhes completos de uma contratação específica.
        Endpoint: /v1/orgaos/{cnpj}/compras/{ano}/{sequencial}
        """
        endpoint = f"orgaos/{cnpj}/compras/{ano}/{sequencial}"
        if not str(cnpj).isdigit() or len(str(cnpj))!=14 or int(ano)<2000 or int(sequencial)<1:
            raise ValueError("Identificadores oficiais inválidos.")
        return self._request_with_retry(endpoint,{},check_cancelled)
