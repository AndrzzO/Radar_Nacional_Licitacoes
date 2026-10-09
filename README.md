# 🛰️ Radar Nacional de Licitações

**Aplicativo Desktop Windows para Coleta, Organização, Monitoramento, Classificação e Exportação de Licitações Públicas Brasileiras.**

<div align="center">

[![Baixar Executável Windows](https://img.shields.io/badge/⬇️_BAIXAR_EXECUTÁVEL_(.EXE)-Windows_64--bit-1B365D?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/AndrzzO/Radar_Nacional_Licitacoes/releases/latest)
[![Última Versão](https://img.shields.io/github/v/release/AndrzzO/Radar_Nacional_Licitacoes?style=for-the-badge&color=0E703C)](https://github.com/AndrzzO/Radar_Nacional_Licitacoes/releases)
[![Status dos Testes](https://img.shields.io/badge/Testes-21%2F21_Aprovados-0E703C?style=for-the-badge&logo=pytest&logoColor=white)](https://github.com/AndrzzO/Radar_Nacional_Licitacoes)

<br/>

### 📥 [👉 **CLIQUE AQUI PARA BAIXAR A VERSÃO EXECUTÁVEL (.EXE / .ZIP)** 👈](https://github.com/AndrzzO/Radar_Nacional_Licitacoes/releases/latest)

> **Não precisa instalar Python, banco de dados ou dependências:**
> 1. Baixe o pacote **`RadarNacionalLicitacoes_Windows.zip`** na página de [Releases](https://github.com/AndrzzO/Radar_Nacional_Licitacoes/releases/latest).
> 2. Descompacte o arquivo ZIP em qualquer pasta do seu Windows.
> 3. Dê dois cliques em **`RadarNacionalLicitacoes.exe`** para começar a usar imediatamente!

</div>

---

## 1. Visão Geral e Objetivo

O **Radar Nacional de Licitações** é uma aplicação desktop nativa desenvolvida em Python (PySide6 / Qt) voltada para a prospecção comercial, monitoramento estratégico e inteligência de mercado em contratações públicas brasileiras.

O sistema conecta-se diretamente às fontes oficiais do governo federal — em especial à **API oficial do Portal Nacional de Contratações Públicas (PNCP)** e à **API de localidades do Instituto Brasileiro de Geografia e Estatística (IBGE)** —, armazena os dados em um banco de dados local SQLite otimizado (modo WAL), categoriza automaticamente os editais por regras determinísticas editáveis e permite a exportação para planilhas profissionais no formato Excel (.xlsx).

O software funciona com autonomia local completa: uma vez realizada a coleta, todas as consultas, buscas por palavras-chave, classificações e exportações funcionam **100% offline**, sem dependência de internet ou servidores externos.

---

## 2. Como o Aplicativo Funciona por Dentro (Fluxo Operacional)

O funcionamento do aplicativo segue um fluxo modular e estruturado em camadas:

```
                  ┌──────────────────────────────────────────────┐
                  │          Fontes Oficiais Externas            │
                  │   - API PNCP (Contratações / Publicações)    │
                  │   - API IBGE (Localidades / Códigos)         │
                  └──────────────────────┬───────────────────────┘
                                         │ Requisições HTTPX
                                         ▼ (com rate limit e retry)
┌────────────────────────────────────────────────────────────────────────┐
│                        Camada de Coleta e Adaptação                    │
│  - PNCPClient: Conexões seguras, controle de HTTP 429, pool de sockets │
│  - PNCPAdapter: Normalização e validação dos dados brutos recebidos    │
└────────────────────────────────────────┬───────────────────────────────┘
                                         │
                                         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Banco de Dados Local (SQLite)                   │
│  - Modo WAL (Write-Ahead Logging): Leituras e escritas concorrentes    │
│  - Deduplicação Estrita: Número de controle PNCP como chave única      │
│  - Upsert Transacional: Preserva histórico e atualiza dados mutáveis   │
└──────────────┬──────────────────────────────────────────┬──────────────┘
               │                                          │
               ▼                                          ▼
┌──────────────────────────────┐        ┌────────────────────────────────┐
│   Classificador Automático   │        │     Interface Gráfica (Qt)     │
│  - Regras ponderadas locais  │        │  - Painel Geral / Dashboard    │
│  - Sinônimos e exclusões     │◄───────┤  - Pesquisa e Filtros          │
│  - 10 Categorias / 44 Subcat.│        │  - Detalhes Completos          │
└──────────────┬───────────────┘        └────────────────┬───────────────┘
               │                                         │
               ▼                                         ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     Exportação Excel Profissional                      │
│  - OpenPyXL: Abas "LICITAÇÕES" (25 colunas) e "METADADOS"              │
│  - Proteção contra Formula Injection e caracteres XML de controle      │
└────────────────────────────────────────────────────────────────────────┘
```

### O Passo a Passo da Operação:
1. **Configuração de Parâmetros:** O usuário define o escopo geográfico (todo o Brasil, estados específicos ou municípios por código IBGE), esferas administrativas (Federal, Estadual, Municipal, Distrital), modalidades e período.
2. **Coleta Online em Background:** A coleta é executada por uma *worker thread* dedicada (`QThread`), garantindo que a interface gráfica permaneça fluida e responsiva. O usuário acompanha páginas, registros recebidos, novos e atualizados em tempo real, com opção de cancelamento imediato.
3. **Persistência e Deduplicação:** Os registros são gravados em lotes no SQLite. Editais já conhecidos têm seus campos atualizados sem criar duplicatas, mantendo intacta a data do primeiro registro no sistema.
4. **Classificação e Enriquecimento:** O motor de regras analisa o objeto e dados complementares, associando o edital à categoria e subcategoria correspondentes (ex: *Tecnologia da Informação -> Software*), com indicação do nível de confiança (Alta, Média ou Baixa).
5. **Consulta e Filtro:** O usuário pesquisa no acervo local de forma instantânea com filtros combinados (palavra-chave, valor, prazo de propostas, modalidade).
6. **Exportação Formatada:** Os registros filtrados ou selecionados são exportados para planilha XLSX com formatação corporativa, links clicáveis e proteção de segurança.

---

## 3. Telas e Funcionalidades em Detalhes

### 3.1. Painel Geral (Dashboard)
Apresenta uma visão executiva do acervo com dados calculados em tempo real a partir do banco de dados local:
- **Total de Contratações Armazenadas:** Tamanho total do acervo acumulado.
- **Propostas Abertas:** Editais cujo prazo de encerramento ainda é futuro.
- **Propostas Encerradas:** Editais com prazo expirado.
- **Sem Data de Encerramento:** Editais cujo órgão comprador não cadastrou prazo final na fonte oficial.
- **Unidades Federativas e Órgãos Compradores:** Quantitativo de estados e CNPJs distintos no banco.
- **Última Sincronização:** Data, hora e quantidade de novos registros inseridos na operação mais recente.
- **Botão de Ação Rápida:** Acesso direto para iniciar uma nova coleta.

### 3.2. Pesquisar Licitações
A tela central de trabalho, subdividida em três áreas operacionais:
- **Área A — Painel de Filtros:**
  - *Estados (UFs):* Seletor múltiplo abrangendo as 27 UFs do Brasil (padrão inicial GO e DF).
  - *Municípios:* Carregamento integrado via IBGE com código oficial de cada cidade. Permite buscar por nome ou filtrar apenas cidades específicas dos estados selecionados.
  - *Esferas:* Seleção independente para Municipal (M), Estadual (E), Federal (F) e Distrital (D).
  - *Situação das Propostas:* "Recebendo Propostas (Aberto)", "Todas as Situações" ou "Propostas Encerradas".
  - *Modalidades Oficiais:* Pregão Eletrônico, Concorrência, Dispensa, Inexigibilidade, Leilão, Diálogo Competitivo, Credenciamento e demais modalidades da Lei 14.133/2021.
  - *Prazos e Datas:* Filtros por data de publicação, encerramento e botões rápidos para prazos futuros (próximos 3, 7, 15 ou 30 dias).
  - *Palavra-chave e Órgão:* Busca textual insensível a maiúsculas e acentos no objeto da compra e razão social/CNPJ.
  - *Faixa de Valor:* Mínimo e máximo em reais.
  - *Painel Retrátil:* Botão para expandir/recolher os filtros, maximizando o espaço útil da tabela.
- **Área B — Ações e Monitoramento:**
  - *Pesquisar Dados Armazenados:* Consulta imediata no banco local SQLite.
  - *Coletar / Atualizar Dados Online:* Dispara a coleta oficial via API do PNCP.
  - *Cancelar Coleta:* Interrompe com segurança a operação em andamento sem perda dos lotes já gravados.
  - *Exportar para Excel:* Gera planilha `.xlsx`.
  - *Indicadores e Progresso:* Barra de progresso com contadores em tempo real (Total Encontrados, Novos e Atualizados).
- **Área C — Tabela de Resultados:**
  - Grade customizada de alta velocidade (`QAbstractTableModel`) capaz de lidar com dezenas de milhares de linhas sem congelamento.
  - Seleção por checkbox individual ou em lote ("Selecionar Todos" / "Desmarcar Todos").
  - Ordenação por colunas clicáveis.
  - Acesso direto aos detalhes e ao link oficial no portal PNCP.

### 3.3. Licitações Armazenadas
Modo de navegação dedicado à exploração dos dados já salvos no computador. Permite navegar, filtrar e pesquisar livremente sem emitir nenhuma requisição para a internet.

### 3.4. Detalhes da Contratação (Modal Completo)
Ao dar duplo clique em qualquer registro da grade, abre-se uma janela com todos os metadados:
- Número de Controle PNCP único oficial.
- Modalidade, modo de disputa e tipo de instrumento convocatório (Edital/Aviso).
- Razão social, CNPJ, esfera e poder do órgão comprador.
- Unidade compradora, município e UF.
- Objeto completo da contratação e informações complementares na íntegra.
- Valor total estimado e valor homologado (quando existirem).
- Datas de publicação, abertura e encerramento das propostas.
- Botão **"Copiar Link PNCP"** (copia a URL oficial para a área de transferência).
- Botão **"Abrir no Portal PNCP"** (abre a página oficial do edital no navegador padrão: `https://pncp.gov.br/app/editais/{cnpj}/{sequencial}/{ano}`).

### 3.5. Classificação Automática
Motor de inteligência de regras que categoriza cada edital sem custo de APIs ou chamadas externas:
- **Catálogo Estruturado:** 10 categorias principais e 44 subcategorias de mercado (Tecnologia da Informação, Engenharia e Obras, Saúde, Alimentos, Serviços Gerais, etc.).
- **Regras Editáveis:** Mais de 120 regras com termos-chave, sinônimos, plurais, pesos de relevância e termos de exclusão contextuais.
- **Nível de Confiança:** Indica a força da evidência (Alta, Média ou Baixa).
- **Reclassificação em Lote:** Permite reclassificar todo o banco local após ajustar ou adicionar regras.
- **Ajuste Manual com Histórico:** O usuário pode corrigir a categoria de um edital nos detalhes; o sistema memoriza a alteração e preserva a prioridade manual sobre o motor automático.

### 3.6. Pesquisas Salvas
Permite salvar conjuntos complexos de filtros como favoritos (ex: *"TI em Goiás — Propostas Abertas"*). Com um clique, os filtros são recarregados na tela principal.

### 3.7. Histórico de Coletas
Auditoria detalhada de cada sincronização realizada:
- Data e hora de início e conclusão.
- Fonte consultada e filtros utilizados.
- Quantidade de registros recebidos, novos cadastrados e atualizados.
- Total de requisições HTTP e páginas concluídas.
- Status da operação (`Concluída`, `Concluída com ressalvas`, `Interrompida`, `Falhou`).
- Log técnico de eventuais erros encontrados.

### 3.8. Curso de Licitações Integrado
Ambiente educacional offline embutido diretamente no aplicativo:
- **15 Módulos Práticos:** Do planejamento da empresa ao pós-licitação e leilões de alienação, fundamentados na Lei nº 14.133/2021.
- **Passos, Exemplos e Exercícios:** Cada aula conta com exemplos reais, listas de conferência e exercícios com gabarito comentado.
- **Controle de Progresso:** Registro de leitura persistido no banco local.
- **Apostila Completa em PDF:** Botão **"Baixar curso em PDF"** que gera e exporta a apostila completa de 37 páginas formatada, sem necessidade de internet.

### 3.9. Configurações, Backup e Restauração
- **Diretório de Exportação:** Definição da pasta padrão para salvar arquivos Excel.
- **Local do Banco de Dados:** Aponta para o arquivo SQLite persistente em `%LOCALAPPDATA%/RadarNacionalLicitacoes/`.
- **Backup do Banco de Dados:** Criação de cópia consistente do SQLite (usando a API nativa de backup que inclui o arquivo de log WAL).
- **Restauração Assistida:** Validação de integridade do arquivo antes de restaurar, com backup de salvaguarda automático do estado anterior.
- **Visualização de Logs:** Acesso rápido ao arquivo rotativo `radar.log`.

---

## 4. Engenharia de Integração com o PNCP

A integração com o Portal Nacional de Contratações Públicas foi desenhada para aderir estritamente aos contratos oficiais documentados no Swagger do governo:

### Endpoints Utilizados:
1. `GET /v1/contratacoes/proposta`:
   - Endpoint prioritário para o modo "Recebendo Propostas".
   - Parâmetro obrigatório: `dataFinal` (formato `yyyyMMdd`).
   - Parâmetros opcionais suportados: `uf`, `codigoMunicipioIbge`, `codigoModalidadeContratacao`, `cnpj`, `pagina`, `tamanhoPagina` (máximo de 50 por chamada).
2. `GET /v1/contratacoes/publicacao`:
   - Utilizado para consultas históricas por período de publicação.
   - Parâmetros obrigatórios: `dataInicial`, `dataFinal`, `codigoModalidadeContratacao`.
3. `GET /v1/contratacoes/atualizacao`:
   - Utilizado pelo modo de sincronização para detectar aditivos, revogações ou atualizações globais em contratações existentes.
4. `GET /v1/orgaos/{cnpj}/compras/{ano}/{sequencial}`:
   - Consulta unitária aos detalhes oficiais da contratação.

### Resiliência e Proteções HTTP:
- **Pool de Conexões HTTPX:** Reutilização eficiente de conexões TLS/TCP com cabeçalhos padronizados.
- **Tratamento de Rate Limit (HTTP 429):** Leitura de `Retry-After`. Quando ausente, aplicação automática de recuo exponencial progressivo (iniciando em 2,5s e escalando até 30s) somado a *jitter* aleatório para evitar colisões repetidas.
- **Erros Transitórios (500, 502, 503, 504):** Tolerância a falhas temporárias com até 5 tentativas antes de abortar.
- **Espaçamento de Cortesia:** Intervalo configurável entre requisições (padrão de 0,35s) para não sobrecarregar a infraestrutura governamental.

---

## 5. Exportação para Excel (.xlsx)

A exportação é realizada pelo módulo [export_service.py](file:///c:/Users/andre/Documents/Radar_Nacional_Licitacoes/src/application/export_service.py) via OpenPyXL e gera arquivos XLSX legítimos com duas abas estruturadas:

### 1ª Aba: `LICITAÇÕES`
Contém 25 colunas formatadas:
1. ID PNCP (Identificador único oficial)
2. Número da Licitação
3. Ano
4. Modalidade Oficial
5. Esfera Administrativa (Municipal, Estadual, Federal, Distrital)
6. Órgão Comprador
7. CNPJ
8. Unidade Compradora
9. UF
10. Município
11. Código IBGE
12. Objeto Completo
13. Valor Estimado (R$ numérico, formatado com separador de milhar e centavos)
14. Data de Publicação
15. Início das Propostas
16. Encerramento das Propostas
17. Situação Oficial da Compra
18. Situação do Prazo (Aberto / Encerrado / Não informado)
19. Última Atualização Oficial
20. Link da Publicação (Hiperlink clicável no PNCP)
21. Link do Edital (Hiperlink do sistema de origem ou processo)
22. Fonte de Dados (`PNCP`)
23. Data da Coleta Local
24. Categoria Classificada
25. Subcategoria Classificada

*Recursos visuais:* Cabeçalhos em azul marinho corporativo (`#1B365D`) com texto branco em negrito, AutoFiltro nativo ativado em todas as colunas e congelamento de painel na linha 1 (`freeze_panes = "A2"`).

### 2ª Aba: `METADADOS`
Contém a ficha de auditoria da extração:
- Data e hora da exportação no fuso horário de Brasília.
- Critérios e filtros exatos utilizados na busca.
- Estados e municípios selecionados.
- Quantidade exata de registros exportados.
- Data da última sincronização do acervo.
- Notas de integridade dos dados e esclarecimentos técnicos.

### Segurança da Exportação:
- **Proteção contra Injeção de Fórmulas (CSV/Formula Injection):** Qualquer texto que inicie com `=`, `+`, `-`, `@`, `\t` ou `\r` é automaticamente prefixado com apóstrofo (`'`), impedindo a execução maliciosa de comandos DDE no Excel do usuário final.
- **Sanitização de Caracteres XML:** Remoção de caracteres de controle ASCII ilegais (`\x00` a `\x08`, `\x0b`, `\x0c`, `\x0e` a `\x1f`) que comumente causam corrupção de arquivos em exportadores padrão.

---

## 6. Instalação e Execução

### Requisitos Mínimos
- Windows 10 ou Windows 11 (64 bits).
- Python 3.12 ou superior.

### Passos de Instalação no PowerShell

```powershell
# 1. Acesse o diretório do projeto
cd C:\Users\andre\Documents\Radar_Nacional_Licitacoes

# 2. Crie e ative o ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Inicie o aplicativo
python main.py
```

---

## 7. Geração do Executável Windows (.EXE)

O projeto inclui o script de build automatizado [scripts/build_windows.ps1](file:///c:/Users/andre/Documents/Radar_Nacional_Licitacoes/scripts/build_windows.ps1) com PyInstaller.

Para compilar o aplicativo:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

O script:
1. Executa a suíte completa de testes automatizados (`pytest`).
2. Se todos os testes passarem, invoca o PyInstaller com a flag `--windowed` (janela nativa sem console).
3. Gera o executável autônomo na pasta:
   ```
   dist\RadarNacionalLicitacoes\RadarNacionalLicitacoes.exe
   ```

---

## 8. Testes e Validação de Qualidade

A aplicação conta com uma suíte de 21 testes automatizados cobrindo todas as camadas sem dependência de internet:

```powershell
.\.venv\Scripts\pytest.exe -v
```

### Cobertura dos Testes:
- **Integração de Dados:** Respostas válidas, campos nulos/ausentes, cálculo de prazo e links oficiais.
- **Cliente HTTP:** Tratamento de HTTP 429 com retentativas e recuo exponencial, cancelamento cooperativo e timeouts.
- **Banco de Dados SQLite:** Inserção, deduplicação (upsert), preservação da data de inclusão, queries dinâmicas e métricas.
- **Localidades IBGE:** Carga de 27 UFs, fallback estático e cache de municípios.
- **Filtros:** Serialização JSON e consultas complexas compostas.
- **Sincronização:** Paginação contínua e cancelamento em execução.
- **Excel:** 25 colunas oficiais, duas abas, sanitização de fórmulas e integridade de tipos.

Além dos testes automatizados, o sistema foi validado em 5 cenários funcionais reais contra os servidores de produção do PNCP (coleta de GO e DF com 200 itens reais, Águas Lindas com código IBGE, re-coleta com zero duplicidades e exportação real). Os relatórios formais estão disponíveis em [docs/ARQUITETURA.md](file:///c:/Users/andre/Documents/Radar_Nacional_Licitacoes/docs/ARQUITETURA.md) e [docs/VALIDACAO.md](file:///c:/Users/andre/Documents/Radar_Nacional_Licitacoes/docs/VALIDACAO.md).

---

## 9. Licença e Uso

Este software é um aplicativo privado destinado ao monitoramento, análise de oportunidades e inteligência em contratações públicas brasileiras. Os dados consultados são públicos e oficiais, disponibilizados pelo Governo Federal nos termos da Lei nº 14.133/2021 e da Lei de Acesso à Informação (Lei nº 12.527/2011).
