# Auditoria Codex — Radar Nacional de Licitações 1.1

Data: 08/10/2026. Alterações incrementais executadas diretamente no projeto existente.

## 1. Estado inicial e preservação

Windows 10 19045, Python 3.12.10, PySide6 6.11.2, HTTPX 0.28.1, OpenPyXL 3.1.5, pytest 9.1.1 e PyInstaller 6.22.3. Ambiente `.venv` existente. Não havia Git nesta pasta; nenhuma mudança preexistente foi descartada. A inspeção cobriu entrada, domínio, integrações, serviços, SQLite, interface, workers, utilitários, testes, documentação e build.

Baseline executada: **21 testes aprovados em 2,40 s**. Código e documentação iniciais foram guardados em `scratch/auditoria_inicial/codigo_antes.zip`, com hashes e versões em `manifest.json`. O contrato OpenAPI PNCP consultado está em `pncp_openapi.json`. O build anterior em `dist/` foi preservado. Não foi encontrado banco de produção no diretório padrão consultado; validações e migrações foram feitas em bancos isolados, incluindo um criado com o esquema antigo.

## 2. Problemas encontrados e correções

| Gravidade | Problema | Correção e evidência |
|---|---|---|
| Crítico | Restauração copiava o arquivo principal sobre SQLite potencialmente em WAL | Cópia isolada validada, integrity/foreign_key_check, migração, backup prévio e restauração pela API SQLite; teste de preservação e backup inválido |
| Alto | Widget da pesquisa adicionado duas vezes à pilha, deslocando telas | Índice reservado separado e teste dos sete destinos de navegação |
| Alto | Favoritos sem import de filtro e recuperação parcial dos controles | Import e restauração de filtros implementados; roundtrip de favoritos e persistência testados |
| Alto | Coleta consultava sempre propostas, inclusive para encerradas | Fluxos separados por proposta, publicação e atualização global; contratos verificados |
| Alto | DataInicial indevida em proposta, HTTP 204 sem tratamento, fim de paginação silencioso | Parâmetros corrigidos, 204 tratado, detecção de página repetida/vazia/fora de ordem e limite explícito |
| Alto | Erros de conversão e indisponibilidade podiam não aparecer no resultado | Ressalvas/falhas e logs preservam a distinção de resultado vazio; dados dos lotes anteriores permanecem |
| Alto | INSERT OR REPLACE de estados removia municípios em cascata | UPSERT não destrutivo, com teste de permanência do município |
| Alto | Municípios nacionais limitados às primeiras cinco UFs e consulta na thread gráfica | Todas as UFs, carregamento em worker, cache local e erro claro quando sem cache |
| Alto | Encerramento sem gerenciamento das threads | Cancelamento cooperativo e espera por sinais/fechamento; não destrói QThread em execução |
| Alto | Classificador inexistente | Motor local, catálogo versionado, evidências, reclassificação, proteção manual, interface e integração |
| Alto | EXE gerado inicialmente falhou ao carregar QtWidgets | Diagnóstico apontou ICU do Poppler capturada do PATH. Python funcional usava ICU do Windows. PATH isolado, exclusão da ICU incompatível no spec e smoke test obrigatório |
| Médio | Links PNCP tinham ano/sequencial invertidos | Formato oficial cnpj/ano/sequencial; compatibilidade de leitura para links locais antigos |
| Médio | Situação de prazo envelhecia no banco | Cálculo na consulta usando horário atual, início, fim e situação oficial; datas interpretadas em Brasília |
| Médio | Excel com datas em texto e classificação vazia | 31 colunas, células de data/número, classificação e metadados sanitizados; arquivo gravado atomicamente |
| Médio | Filtro de origem excluía automáticos não classificados | Consulta de origem separada da existência de categoria; teste combinado |
| Médio | Valores inválidos eram silenciosamente ignorados | Parser monetário explícito e mensagens de validação; testes de moeda brasileira e decimal simples |
| Médio | Resultado antigo podia competir com novo objeto | Hash e conferência transacional do texto, pendência e recuperação por reclassificação |
| Baixo | Controles muito largos, ausência de paginação/ordenação/visibilidade | Layout ajustado por capturas, páginas de 200, ordenação de classificação e menu de colunas |

Na retomada, um teste novo mostrou que a marca de erro não era limpa quando a classificação atual já estava correta em cache. A causa foi corrigida e a regressão foi mantida na suíte. Os testes antigos de links e número de colunas foram atualizados para o contrato corrigido e a nova exportação, sem esconder falhas.

## 3. Novo classificador e funcionalidades

Motor determinístico em `src/classification/engine.py`, persistência e catálogo em `store.py`, configuração inicial em JSON e serviço de lotes independente da UI. São **10 categorias, 44 subcategorias e 122 regras**. Normalização, palavras completas, expressões, sinônimos/plurais explícitos, prioridade de sobreposição, contexto e exclusões locais. Evidência insuficiente e conflitos não são resolvidos arbitrariamente. Confiança não é probabilidade.

Há gestão persistente de categorias, subcategorias e regras; criação, edição, desativação e exclusão somente sem dependências; limiares editáveis; prévia e backup em importações/restauração; testador; reclassificação em quatro modos; revisão; correção manual com justificativa; retorno à automática. O histórico manual não é apagado. Filtros incluem secundárias e combinam geografia, datas, modalidade, texto e valor.

Leia `docs/CLASSIFICADOR.md` para regras precisas do algoritmo e limites. O cadastro foi testado pela própria classe do editor e pelo efeito da regra salva no motor, não apenas pela aparência da tela.

## 4. Testes e evidências

### Determinísticos

**86 aprovados, 0 falhados, 2 ignorados na execução padrão.** Os dois ignorados são integrações online intencionalmente opcionais. A última execução completa antes do build confirmou os 86 aprovados; o log do build registra a nova execução obrigatória.

A suíte cobre migração, rollback, integridade, backup/restauração WAL, tentativa de restauração inválida, coleta/paginação, cancelamento, filtros, deduplicação, cache de localidades, classificação, ambiguidades, exclusões, regras alteradas/desativadas, manual, concorrência, reclassificação em lotes, exportação de todos versus selecionados, metadados e quatro testes de interface Qt.

### Online, separados dos mocks

Os **2 testes online foram executados e passaram**: compra individual no PNCP e estados/municípios GO/DF no IBGE. A API de modalidades respondeu 200 com 19 modalidades; o endpoint individual antigo `/api/pncp/v1/...` respondeu 301 informando a mudança para `/api/consulta/v1/...`, e o destino foi consultado com sucesso (200). As evidências do domínio estão em `scratch/modalidades_oficiais.json` e `scratch/dominios_oficiais.json`.

### Ponta a ponta real

`scripts/validate_online.py` abriu a janela Qt em modo offscreen e executou o fluxo com dados oficiais e banco isolado:

- GO/DF, esferas M/D/E/F, propostas abertas e horizonte de 7 dias, até 15/10/2026.
- Primeira tentativa: 588 registros salvos e HTTP 429 no DF. Registrada como Concluída com ressalvas, nunca como sucesso completo.
- Segunda tentativa, concluída às **05:51 de 08/10/2026, horário de Brasília**: 15 páginas, 707 itens recebidos da API, 75 novos e 588 atualizados. O conjunto persistido após deduplicação e filtros locais continha **663 registros únicos**.
- TI / Software, com o mesmo prazo: **11 registros**; Excel de filtrados e Excel de selecionados tiveram **11 linhas de dados** cada, confirmadas por leitura com OpenPyXL.
- Encerramento e reabertura da janela: **663 registros preservados**.
- SQLite: `integrity_check=ok`, nenhuma violação de chave estrangeira.

Evidência integral: `scratch/validacao_online/resultado.json`. Os XLSX e capturas estão na mesma pasta. Os números são uma fotografia daquele horário; prazos e disponibilidade mudam. O contador de requisições desse relatório foi capturado antes do ajuste que passou a incluir tentativas HTTP adicionais; “15” nessa evidência significa chamadas de páginas, não total de tentativas com retries.

### Executável

O smoke test abre o EXE com banco isolado e fecha a janela por timer, respeitando os workers, com timeout de 30 segundos. Verifica saída zero e marcador `SMOKE_TEST_OK`, além de registrar SHA-256 do EXE. A evidência final está em `scratch/packaged_smoke_result.json` e o build em `scratch/build_v1_1.log`.

A primeira execução revelou a DLL ICU incompatível; o problema foi reproduzido, identificado por origem da DLL e corrigido na configuração permanente. O smoke test foi incorporado ao build para que geração de arquivo EXE não seja confundida com inicialização bem-sucedida.

## 5. Performance medida

Massa explicitamente sintética, 10 mil objetos, 122 regras, ambiente local:

| Operação | Tempo |
|---|---:|
| Motor puro, com tracemalloc habilitado | 9,39 s |
| Gravação SQLite + classificação de 10 mil registros | 5,28 s |
| Consulta combinada UF + categoria, 5 mil correspondências e página de 200 | 28,9 ms |
| Verificação de pendentes sem alterações | 88,3 ms |

Evidência: `scratch/benchmark.json`, reproduzível por `scripts/benchmark_classification.py`. O motor puro foi medido com instrumentação de memória; não comparar diretamente seu tempo ao trecho sem instrumentação. O pico incremental registrado pelo tracemalloc foi aproximadamente 0,017 MiB após construir o motor; não representa RSS do aplicativo ou memória total do SQLite/Qt/Excel. Não foram medidos RSS total nem exportação de dezenas de milhares de linhas.

Otimizações: índices de relacionamento e classificação, padrões compilados por catálogo, batch de 100, reutilização por hash/versão, consulta paginada e carregamento de classificações por grupos de IDs, sem consulta de regras para cada registro. Exportação continua em memória, com limitação documentada.

## 6. Banco e migrações

Migração aditiva versionada (versão 2), executada dentro da transação existente, sem `executescript` fazendo commit implícito. Não recria nem apaga o acervo. Tabelas oficiais mantidas; novas tabelas têm chaves estrangeiras, unicidade e índices. Catálogo, execuções e intervenções são versionados. A migração foi executada nos bancos temporários e no banco isolado da validação real.

Backup usa `sqlite3.Connection.backup`, incluindo WAL. Edições/importação do catálogo criam backup consistente. Restauração valida e migra uma cópia temporária, preserva backup anterior e exige ausência de workers ativos. Dados persistem fora de `_MEIPASS` e do pacote distribuído.

## 7. Interface

Navegação corrigida e nova entrada Classificação Automática, com sete abas. Consultas locais, coleta, municípios, exportação, reclassificação e manutenção usam trabalhadores. A interface recebe resultados por signals/slots. Filtros e tabela têm estados e progresso reais; colunas de classificação podem ser ordenadas e ocultadas. Capturas revisadas em `scratch/pesquisa_final.png`, `scratch/classificacao_final.png` e `scratch/regras_final.png`.

A validação Qt offscreen é uma execução real dos widgets, mas não equivale a homologação manual em todas as resoluções, escalas de DPI e máquinas Windows. O fechamento do pacote final é validado separadamente pelo smoke test.

## 8. Execução e build

```powershell
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe -m pytest -q
.\scripts\build_windows.ps1
```

Executável: `dist_v1_1/RadarNacionalLicitacoes/RadarNacionalLicitacoes.exe`. Leve a pasta inteira com `_internal`. O script executa testes, PyInstaller e smoke test. Não há instalador ou assinatura digital. Windows deve disponibilizar sua ICU de sistema compatível, como no Windows 10 19045 testado.

## 9. Pendências e limites de aceitação

Não há teste atualmente falhado na suíte determinística. Isso não prova ausência de qualquer defeito.

- Classificação não foi calibrada contra um conjunto humano de referência; pode exigir refinamento do catálogo. Contexto é lexical e não interpreta negação/cláusulas.
- Validação online completa cobriu propostas GO/DF. Publicações e atualização global têm testes determinísticos de integração; não foi feita coleta nacional exaustiva nem teste online de todas as 19 modalidades.
- O limite de 500 páginas é explícito e produz coleta incompleta, exigindo partições menores; a aplicação não promete coleta nacional ilimitada em uma operação.
- Cobertura temporal é configurável; padrões de 90 dias para propostas, 30 para publicação e 7 para atualização não equivalem ao acervo inteiro do portal.
- Cancelamento de rede aguarda a requisição atual ou seu timeout; não há interrupção insegura de threads.
- Tela de revisão mostra até 200 casos por vez; o acervo completo é acessível por filtros e páginas.
- Excel usa memória proporcional ao arquivo; exportações muito maiores que as testadas ainda precisam de medição.
- Backups e histórico não possuem limpeza automática; acompanhe espaço em disco.
- Homologação manual prolongada, DPI variados, outra máquina e instalador assinado não foram realizados.

## 10. Arquivos alterados

- `.gitignore`
- `README.md`
- `RadarNacionalLicitacoes.spec`
- `docs/ARQUITETURA.md`
- `docs/VALIDACAO.md`
- `main.py`
- `pyproject.toml`
- `scripts/build_windows.ps1`
- `src/__init__.py`
- `src/application/collection_service.py`
- `src/application/export_service.py`
- `src/application/location_service.py`
- `src/application/synchronization_service.py`
- `src/database/connection.py`
- `src/database/migrations.py`
- `src/database/repositories.py`
- `src/domain/filters.py`
- `src/domain/validation.py`
- `src/integrations/ibge_client.py`
- `src/integrations/pncp_adapter.py`
- `src/integrations/pncp_client.py`
- `src/ui/components/municipio_selector.py`
- `src/ui/components/uf_selector.py`
- `src/ui/dashboard.py`
- `src/ui/details_panel.py`
- `src/ui/main_window.py`
- `src/ui/results_table.py`
- `src/ui/search_page.py`
- `src/ui/settings_page.py`
- `src/utils/datetime_utils.py`
- `src/utils/file_utils.py`
- `tests/test_excel_export.py`
- `tests/test_pncp_adapter.py`
- `tests/test_pncp_client.py`

### Arquivos adicionados
- `docs/CLASSIFICADOR.md`
- `scripts/benchmark_classification.py`
- `scripts/capture_ui.py`
- `scripts/smoke_build.py`
- `scripts/validate_online.py`
- `src/application/reclassification_service.py`
- `src/classification/__init__.py`
- `src/classification/default_catalog.json`
- `src/classification/engine.py`
- `src/classification/store.py`
- `src/domain/modalities.py`
- `src/ui/classification_page.py`
- `src/workers/task_worker.py`
- `tests/test_audit_regressions.py`
- `tests/test_classification.py`
- `tests/test_online_optional.py`
- `tests/test_ui.py`
- `docs/AUDITORIA_CODEX.md`

## Complemento: instância única

Adicionada trava atômica por sessão do Windows, adquirida antes do Qt, logger e banco. Aberturas adicionais encerram sem criar janela. O sistema libera a trava inclusive após falha do processo. Testes entre processos verificam bloqueio, reabertura e recuperação após encerramento forçado. O smoke test do pacote também verifica três tentativas simultâneas com a trava ocupada, seguidas de inicialização normal após liberar a trava. Evidência do build: `scratch/build_single_instance.log`.

## Complemento: curso dentro do aplicativo

Implementados 15 módulos offline, exercícios, progresso e apostila PDF de 37 páginas. A validação posterior ampliou a suíte para 105 testes aprovados e dois opcionais online ignorados. Detalhes e limites estão em `docs/CURSO_VALIDACAO.md`; evidências em `scratch/build_course.log` e `scratch/course_pdf_validation.json`.
