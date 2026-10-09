> Documento histórico da versão 1.0, preservado para rastreabilidade. A implementação e a validação atuais estão em [AUDITORIA_CODEX.md](AUDITORIA_CODEX.md), [CLASSIFICADOR.md](CLASSIFICADOR.md) e no README. As afirmações abaixo não substituem a validação de 08/10/2026.

# ARQUITETURA TÉCNICA — RADAR NACIONAL DE LICITAÇÕES

## 1. Visão Geral do Sistema

O **Radar Nacional de Licitações** é uma aplicação desktop privada desenvolvida em Python para ambiente Windows, concebida para coletar, organizar, persistir localmente e exportar contratações públicas brasileiras registradas no Portal Nacional de Contratações Públicas (PNCP) e catalogadas com códigos oficiais de municípios do Instituto Brasileiro de Geografia e Estatística (IBGE).

A arquitetura foi desenhada segundo os princípios de separação de responsabilidades (SoC), persistência em camadas e modelo assíncrono para garantir estabilidade, segurança e responsividade da interface gráfica.

---

## 2. Diagrama de Módulos e Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────┐
│                    Camada de Apresentação                   │
│                     (PySide6 / Qt UI)                       │
│  - MainWindow                                               │
│  - DashboardPage (Painel Geral & Métricas)                  │
│  - SearchPage (Área A: Filtros, Área B: Ações, Área C: Grid)│
│  - DetailsDialog (Modal Completo do Edital)                 │
│  - SavedSearchesPage & HistoryPage & SettingsPage           │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────────┐┌─────────────────────────────┐
│       CollectionWorker       ││        ExportWorker         │
│  (QThread - Coleta Assíncrona││(QThread - Exportação XLSX)  │
└──────────────┬───────────────┘└─────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Camada de Aplicação                      │
│  - CollectionService (Orquestração e Paginação PNCP)        │
│  - SynchronizationService (Sincronização Incremental)       │
│  - SearchService (Consultas Locais em SQLite)               │
│  - ExportService (Geração de XLSX via OpenPyXL)             │
│  - LocationService (Cache de UFs e Municípios do IBGE)      │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────────┐┌─────────────────────────────┐
│     Camada de Integração     ││     Camada de Persistência  │
│  - PNCPClient (HTTPX / Pool) ││  - DatabaseConnection (WAL) │
│  - PNCPAdapter (Normalização)││  - ProcurementRepository    │
│  - IBGEClient (Localidades)  ││  - LocationRepository       │
└──────────────────────────────┘│  - SyncRepository           │
                                │  - SavedSearchRepository    │
                                │  - SettingsRepository       │
                                └─────────────────────────────┘
```

---

## 3. Endpoints e Contratos Oficiais Utilizados

### 3.1. PNCP — Propostas Abertas
- **Endpoint:** `GET /v1/contratacoes/proposta`
- **URL Base Oficial:** `https://pncp.gov.br/api/consulta/v1`
- **Finalidade:** Coletar contratações com recebimento de propostas aberto.
- **Parâmetros Suportados:**
  - `dataFinal` (Obrigatório, formato `yyyyMMdd`): data limite para encerramento das propostas.
  - `dataInicial` (Opcional, formato `yyyyMMdd`): data inicial de corte.
  - `uf` (Opcional, texto de 2 letras): sigla da UF (ex: `GO`, `DF`).
  - `codigoMunicipioIbge` (Opcional): código IBGE de 7 dígitos do município.
  - `codigoModalidadeContratacao` (Opcional): ID numérico da modalidade de contratação.
  - `cnpj` (Opcional): CNPJ do órgão comprador.
  - `pagina` (Obrigatório, inteiro base 1): índice da página.
  - `tamanhoPagina` (Opcional, máx. 50): número de itens por página.
- **Estrutura de Retorno:** Objeto com `totalRegistros`, `totalPaginas`, `numeroPagina`, `paginasRestantes` e array `data`.

### 3.2. PNCP — Publicações
- **Endpoint:** `GET /v1/contratacoes/publicacao`
- **Finalidade:** Consultar editais por período de publicação no PNCP.
- **Parâmetros:** `dataInicial` (obrigatório), `dataFinal` (obrigatório), `codigoModalidadeContratacao` (obrigatório), `uf`, `codigoMunicipioIbge`, `pagina`, `tamanhoPagina`.

### 3.3. PNCP — Atualizações Globais
- **Endpoint:** `GET /v1/contratacoes/atualizacao`
- **Finalidade:** Obter alterações globais ocorridas em contratações para sincronização incremental.

### 3.4. PNCP — Detalhe da Contratação
- **Endpoint:** `GET /v1/orgaos/{cnpj}/compras/{ano}/{sequencial}`
- **URL Web Portal:** `https://pncp.gov.br/app/editais/{cnpj}/{sequencial}/{ano}`

### 3.5. IBGE — Localidades
- **Estados:** `https://servicodados.ibge.gov.br/api/v1/localidades/estados`
- **Municípios por UF:** `https://servicodados.ibge.gov.br/api/v1/localidades/estados/{UF}/municipios`

---

## 4. Estratégia de Paginação e Particionamento

1. **Particionamento por UF:**
   Quando o usuário seleciona múltiplas UFs (ex: GO e DF), a coleta particiona o trabalho em ciclos ordenados por UF. Se nenhuma UF for selecionada, o particionamento executa consulta de âmbito nacional (`uf=None`).
2. **Lotes Otimizados:**
   A API do PNCP impõe um limite máximo de 50 registros por página (`tamanhoPagina=50`). O coletor utiliza o tamanho máximo permitido para reduzir em 80% o número de requisições HTTP necessárias.
3. **Limite de Segurança:**
   Para prevenir loops infinitos em caso de inconsistência na contagem de páginas da fonte, há uma trava de segurança configurável de 500 páginas por partição.
4. **Cancelamento Cooperativo:**
   Antes e durante cada requisição de página, o worker verifica a flag `_is_cancelled`. Se acionada pelo usuário, a coleta encerra imediatamente a partição e registra o estado `"Interrompida"` no banco de dados.

---

## 5. Resiliência HTTP e Controle de Taxa (Rate Limit)

- **HTTPX Client:** Instância única e reutilizável com keep-alive habilitado e pool de conexões (máx. 5 keep-alive, 10 conexões totais).
- **Tratamento de HTTP 429:**
  A API do PNCP adota limitador de taxa (token bucket). Quando uma resposta 429 é recebida, o cliente inspeciona o cabeçalho `Retry-After`. Se ausente, aplica espera com recuo exponencial progressivo (iniciando em 2,5s e dobrando) acrescido de variação aleatória (*jitter*).
- **Erros de Servidor (500, 502, 503, 504):**
  Tratados como falhas transitórias com repetição controlada de até 5 tentativas.
- **Intervalo de Cortesia:**
  Intervalo configurável entre requisições consecutivas (padrão de 0,35s) para não sobrecarregar a infraestrutura governamental.

---

## 6. Persistência e Integridade de Dados

- **SQLite WAL Mode:**
  O banco de dados utiliza `PRAGMA journal_mode = WAL;` (Write-Ahead Logging) e `PRAGMA synchronous = NORMAL;`, permitindo leituras concorrentes pela interface gráfica enquanto coletas assíncronas gravam lotes de dados em segundo plano sem travamentos (`database is locked`).
- **Chave de Identidade Única:**
  A identidade primária da licitação é o `numero_controle_pncp` oficial (composto por CNPJ + tipo + sequencial + ano, ex: `54801121000161-1-000015/2026`).
- **Política de Upsert e Deduplicação:**
  Ao re-coletar registros já existentes:
  - O identificador interno (`id`) e a data original de inclusão local (`data_inclusao_local`) são estritamente preservados.
  - A data de atualização local (`data_atualizacao_local`) e todos os dados mutáveis (objeto, valor, datas oficiais, status) são atualizados.
  - Nunca são geradas duplicidades.
  - Registros nunca são deletados por ausência em consultas posteriores.
- **Integridade de Valores Ausentes:**
  Campos não fornecidos pela fonte (como `valorTotalEstimado` ausente) permanecem gravados como `NULL` e exibidos como `"-"`, evitando distorções contábeis (ex: gravar R$ 0,00 fictício).

---

## 7. Proteção e Segurança na Exportação Excel

- **Formula Injection Mitigation:**
  Textos que iniciam com caracteres perigosos no Excel (`=`, `+`, `-`, `@`, `\t`, `\r`) são automaticamente prefixados com apóstrofo (`'`), impedindo execução involuntária de comandos externos (DDE ou macros).
- **Controle de Caracteres XML:**
  Caracteres de controle ASCII inválidos (`\x00` a `\x08`, `\x0b`, `\x0c`, `\x0e` a `\x1f`), frequentemente presentes em textos de editais colados no PNCP, são filtrados antes da serialização pelo OpenPyXL.
- **Estrutura Dupla:**
  - Aba `LICITAÇÕES`: 25 colunas oficiais com cabeçalho azul marinho institucional (`#1B365D`), AutoFiltro, congelamento de painel (`A2`), formatação monetária e links clicáveis.
  - Aba `METADADOS`: registro de parâmetros, filtros aplicados, data e hora, quantidade de registros e notas de integridade.

---

## 8. Extensibilidade Futura

O sistema adota desacoplamento entre coletores e repositórios através de entidades de domínio:
- Para adicionar novas fontes (ex: Compras.gov.br direto, BEC-SP, portais municipais):
  1. Criar novo cliente HTTP em `src/integrations/`.
  2. Implementar um adaptador que converta o payload para a entidade `Licitacao` em `src/domain/entities.py`.
  3. Registrar a nova fonte no `CollectionService` mantendo o mesmo banco de dados, filtros e exportador.
