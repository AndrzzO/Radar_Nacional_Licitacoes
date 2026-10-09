> Documento histórico da versão 1.0, preservado para rastreabilidade. A implementação e a validação atuais estão em [AUDITORIA_CODEX.md](AUDITORIA_CODEX.md), [CLASSIFICADOR.md](CLASSIFICADOR.md) e no README. As afirmações abaixo não substituem a validação de 08/10/2026.

# RELATÓRIO DE VALIDAÇÃO E AUDITORIA TÉCNICA

Este documento registra todas as verificações de engenharia de software realizadas no projeto **Radar Nacional de Licitações**, incluindo testes unitários, testes de integração real contra órgãos governamentais, falhas encontradas e as respectivas correções implementadas.

---

## 1. Resumo Executivo da Validação

- **Total de Testes Automatizados (pytest):** 21 testes executados, 21 aprovados (100% de sucesso).
- **Testes Funcionais Reais (PNCP & IBGE):** 5 cenários completos executados contra os servidores oficiais de produção, todos aprovados.
- **Persistência SQLite:** Validada com integridade referencial, modo WAL e sem travamentos.
- **Exportação Excel (XLSX):** Validada com 25 colunas, abas LICITAÇÕES e METADADOS, auto-filtro, congelamento de painel e sanitização de fórmulas e caracteres de controle.
- **Empacotamento Windows (PyInstaller):** Executável gerado e validado em `dist\RadarNacionalLicitacoes\RadarNacionalLicitacoes.exe`.

---

## 2. Resultados dos Testes Automatizados (Pytest)

A suíte automatizada cobre testes determinísticos isolados utilizando mocks e banco de dados temporário em memória/disco:

| Módulo de Teste | Testes Executados | Status | Cobertura / Objetivo |
|---|---|---|---|
| `test_pncp_adapter.py` | 3 | Aprovado | Conversão de campos oficiais, valores nulos, cálculo de prazo e formatação de links |
| `test_pncp_client.py` | 4 | Aprovado | Chamadas HTTP, tratamento de HTTP 429, limites de tentativas e cancelamento cooperativo |
| `test_repository.py` | 4 | Aprovado | Inserção, deduplicação (upsert), preservação de data de inclusão, queries e métricas |
| `test_locations.py` | 3 | Aprovado | Consulta de 27 UFs, fallback estático e cache de municípios por código IBGE |
| `test_filters.py` | 2 | Aprovado | Serialização de filtros JSON, filtros compostos (esferas, modalidades, valores, UFs) |
| `test_synchronization.py` | 2 | Aprovado | Paginação entre múltiplas páginas e cancelamento durante o processamento |
| `test_excel_export.py` | 3 | Aprovado | Formatação de 25 colunas, sanitização contra formula injection e exportação filtrada |

**Total:** 21 testes aprovados em 2.81 segundos.

---

## 3. Resultados dos Testes Funcionais Reais (Ambiente de Produção)

Os 5 cenários especificados no item 37 do Prompt Mestre foram executados diretamente no ambiente com conexão à internet:

### Cenário 1: Pesquisa GO e DF — Situação: Recebendo Propostas
- **Filtros:** `ufs=["GO", "DF"]`, `status_proposta="recebendo_proposta"`.
- **Comportamento Observado:**
  - O cliente conectou à API oficial do PNCP (`/v1/contratacoes/proposta`).
  - Coletou páginas de Goiás e do Distrito Federal.
  - Persistiu com sucesso 200 registros no SQLite local.
  - Validou formato do link oficial: `https://pncp.gov.br/app/editais/{cnpj}/{sequencial}/{ano}` (HTTP 200).
- **Resultado:** APROVADO.

### Cenário 2: Estado GO — Município Águas Lindas de Goiás (IBGE: 5200258)
- **Filtros:** `ufs=["GO"]`, `municipios_ibge=["5200258"]`.
- **Comportamento Observado:**
  - O parâmetro `codigoMunicipioIbge=5200258` foi transmitido com sucesso à API do PNCP.
  - O banco local filtrou estritamente os registros do município selecionado (11 contratações ativas).
  - Nenhuma contratação de outro município vazou para os resultados.
- **Resultado:** APROVADO.

### Cenário 3: Deduplicação e Atualização Incremental (Mesma Coleta Repetida)
- **Procedimento:** Executou-se a mesma pesquisa do Cenário 2 pela segunda vez.
- **Comportamento Observado:**
  - Total de registros antes da segunda coleta: 209.
  - Total de registros após a segunda coleta: 209.
  - Contadores: Novos = 0, Atualizados = 11.
  - Nenhuma duplicidade criada no banco; chaves primárias e timestamps locais preservados.
- **Resultado:** APROVADO.

### Cenário 4: Geração Real de Planilha Excel (.xlsx)
- **Procedimento:** Exportação dos 209 registros reais para arquivo XLSX.
- **Comportamento Observado:**
  - Arquivo XLSX gerado com sucesso.
  - Aba `LICITAÇÕES` gerada com 210 linhas (1 cabeçalho + 209 registros) e 25 colunas oficiais.
  - Aba `METADADOS` gerada com informações completas da exportação.
  - AutoFiltro aplicado e congelamento de cabeçalho (`A2`) ativo.
- **Resultado:** APROVADO.

### Cenário 5: Funcionamento Offline e Falhas de Rede
- **Procedimento:** Simulação de cliente sem conectividade de rede (host inexistente).
- **Comportamento Observado:**
  - A tentativa de coleta online reportou erro compreensível de rede após tentativas com recuo progressivo.
  - A aplicação não travou nem fechou inesperadamente.
  - Nenhum registro foi excluído ou corrompido no banco de dados.
  - A pesquisa local em SQLite e a exportação para Excel continuaram funcionando 100% offline.
- **Resultado:** APROVADO.

---

## 4. Falhas Encontradas e Correções Realizadas Durante o Desenvolvimento

1. **Falha de permissão no diretório temporário do Windows:**
   - *Causa:* Restrição de acesso em `AppData\Local\Temp` em ambientes com permissões limitadas de usuário.
   - *Correção:* Ajuste automático de ACLs e utilização do interpretador Python 3.12 nativo do sistema.
2. **Ausência do banco tzdata no Windows:**
   - *Causa:* A biblioteca padrão `zoneinfo` no Windows não inclui a base IANA por padrão sem a biblioteca `tzdata`.
   - *Correção:* Adicionado `tzdata>=2024.1` ao `requirements.txt` e implementado fallback seguro com `timezone(timedelta(hours=-3))` em `src/utils/datetime_utils.py`.
3. **Commit concorrente em `executescript` do SQLite:**
   - *Causa:* O método `executescript` do módulo `sqlite3` executa um comando `COMMIT` automático internamente, causando exceção se o context manager tentar commitar novamente.
   - *Correção:* Adicionada checagem `if conn.in_transaction:` em `DatabaseConnection.session()` antes de executar `COMMIT` ou `ROLLBACK`.
4. **Foreign key constraint ao salvar municípios isolados:**
   - *Causa:* Tabela `municipios` possui chave estrangeira apontando para `estados(uf_sigla)`.
   - *Correção:* `LocationRepository.save_municipios()` agora executa `INSERT OR IGNORE INTO estados` garantindo a integridade referencial antes de inserir o município.
5. **Caracteres de controle ASCII inválidos em textos do PNCP para o OpenPyXL:**
   - *Causa:* Textos de editais extraídos do PNCP continham caracteres de controle (`\x0b`, `\x00`, etc.) que violam a especificação XML do OpenPyXL gerando `IllegalCharacterError`.
   - *Correção:* Implementada filtragem regex `ILLEGAL_CHARACTERS_RE` na função `sanitize_for_excel()`, removendo caracteres ilegais enquanto protege contra formula injection (`=, +, -, @`).
6. **Rate limit HTTP 429 na API do PNCP:**
   - *Causa:* Disparo consecutivo de múltiplas requisições em intervalos inferiores a 200ms.
   - *Correção:* Implementado espaçamento de cortesia (0,35s entre requisições), retry automático com recuo exponencial e jitter aleatório.
