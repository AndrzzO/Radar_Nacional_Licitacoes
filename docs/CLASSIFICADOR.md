# Classificador local — versão 1.0 do motor

O Radar 1.1 classifica exclusivamente pelo objeto oficial, usando Python e regras locais. Não envia textos para IA, LLMs ou serviços pagos. O catálogo inicial contém 10 categorias (incluindo Não Classificado), 44 subcategorias e 122 regras. `src/classification/default_catalog.json` é o recurso inicial; depois da criação do banco, o catálogo editável e suas versões ficam no SQLite. Alterar o arquivo inicial não sobrescreve personalizações existentes.

## Algoritmo e correspondências

1. Normalização NFKD, casefold, remoção de marcas diacríticas e pontuação e compactação de espaços. O texto oficial não é modificado. A correspondência trabalha com letras latinas e números; não é um classificador multilíngue.
2. Cada expressão e cada sinônimo possui um padrão escapado, com limites de palavra. Não são aceitas expressões regulares arbitrárias. Plurais e variações são cadastrados explicitamente em Sinônimos, sem radicalização que possa criar substrings indevidas.
3. Regras contextuais exigem pelo menos um termo de contexto dentro da janela configurada, inicialmente 12 palavras de cada lado do trecho. Não existe inferência semântica ou probabilística.
4. As correspondências são ordenadas pelo comprimento: expressões maiores têm precedência. Em igualdade, contextual precede inclusão, depois peso e ID. Trechos sobrepostos só pontuam uma vez, inclusive entre subcategorias. Uma regra pontua no máximo uma vez por objeto; um termo independente fora da expressão composta pode pontuar se corresponder a outra regra.
5. Exclusões só suprimem a evidência da mesma subcategoria quando seus trechos se sobrepõem. Uma referência a rede de esgoto não elimina uma evidência independente de infraestrutura de rede.
6. Somam-se pontos por subcategoria. Subcategorias abaixo do mínimo são descartadas; as restantes são consolidadas por categoria. As categorias elegíveis são preservadas em linhas relacionais, sem duplicar a licitação.
7. A categoria mais pontuada só vira principal se a diferença para a segunda atingir a margem. Caso contrário, o resultado principal é Não Classificado, com categorias candidatas auditáveis. Empate entre subcategorias da categoria vencedora gera “Revisar subcategoria”. A prioridade organiza candidatos de mesmo escore, mas não resolve arbitrariamente um conflito de evidência.

Exemplos: “compra de notebooks” → TI / Hardware; “licenciamento de software” → TI / Software; manutenção contextual de computadores → TI / Manutenção e Suporte. “Rede” e “sistema” isolados não fazem parte das inclusões padrão.

## Pontuação e confiança

Limiares iniciais editáveis: mínimo 4, Média a partir de 7, Alta a partir de 12, margem de 2. Baixa significa evidência suficiente para classificação, abaixo de Média. Alta também exige subcategoria sem conflito. Manual é uma indicação de decisão humana, com pontuação zero; não é uma estimativa de acerto.

Nenhum número é probabilidade ou percentual de precisão. A qualidade do catálogo não foi calibrada estatisticamente em um corpus rotulado. Ajuste pesos e termos no testador antes de reclassificar o acervo.

## Persistência e auditoria

- `categories`, `subcategories`, `classification_rules`: catálogo relacional com chaves e dependências.
- `classification_catalog`: snapshots JSON integrais, versionados e datados, contendo configurações e sinônimos.
- `classification_runs`: objeto identificado por SHA-256, versão do catálogo, origem, data, justificativa e evidências da decisão.
- `classifications`: uma linha por categoria elegível e execução, com categoria principal, subcategoria, pontuação e confiança.
- `classification_evidence`: regras, trechos normalizados, pontuações e snapshot da evidência. Os offsets referem-se ao texto normalizado, não ao texto oficial.
- `classification_state`: ponteiros separados para resultado automático e intervenção manual, além de falhas pendentes.
- `classification_events` e `reclassification_jobs`: intervenções e processamento em massa.

As versões antigas e evidências permanecem disponíveis para auditoria mesmo após editar uma regra. Exclusões e correspondências descartadas por sobreposição ficam no resultado da execução. O testador e o painel de detalhes mostram essas justificativas.

## Cadastro, exclusão e importação

A tela Classificação Automática oferece visão geral, categorias, subcategorias, regras, testador, reclassificação e revisão. Categorias e subcategorias podem ser criadas, renomeadas e desativadas; a subcategoria pode mudar de categoria. Regras oferecem expressão, sinônimos, contexto, tipo e peso. Há busca e filtro por categoria.

Excluir verifica dependências. Itens usados por outras entidades ou evidências devem ser desativados; itens sem dependências podem ser excluídos com backup. IDs excluídos não são reutilizados. A categoria reservada Não Classificado, ID 10, não pode ser removida ou receber subcategorias.

Importação JSON valida esquema, IDs, nomes, relacionamentos, tipos, limites e duplicações. Mostra prévia de novos/alterados e expressões compartilhadas, pede confirmação, cria snapshot consistente do banco e aplica em transação. Importações não podem omitir IDs atualmente existentes: desative-os ou use a exclusão verificada. Expressões repetidas em subcategorias diferentes são avisadas, pois podem representar contexto legítimo. Arquivos acima de 10 MB são rejeitados.

“Restaurar regras padrão” mostra prévia e exige confirmação. O catálogo anterior fica no backup e no histórico; itens personalizados fora do padrão são preservados desativados. A reversão integral pode ser feita restaurando o backup do banco.

## Integração e reclassificação

Cada lote da coleta é salvo antes da classificação. Uma falha do classificador não desfaz os registros oficiais; gera log e pendência. Se o objeto e a versão não mudaram, o resultado é reutilizado. Uma atualização concorrente do objeto impede que uma decisão sobre texto antigo substitua a atual.

A reclassificação não baixa dados. Opera em lotes de 100, com paginação por ID, snapshot do catálogo, progresso, cancelamento entre lotes e histórico de processados, alterados, inalterados e erros. Há modos Todos, Não classificados, Baixa confiança e Pendentes/regras atualizadas. Uma alteração de catálogo marca conservadoramente todos os resultados automáticos antigos como pendentes; não se tenta adivinhar um subconjunto menor.

Correção manual exige categoria, subcategoria e justificativa. Tem prioridade sobre o resultado automático e não é apagada por reclassificação. “Voltar à automática” recalcula o resultado, remove explicitamente a prioridade manual e registra o evento; o histórico permanece.

Filtros de categorias incluem secundárias/candidatas por padrão. “Somente categoria principal” restringe a vencedora. Filtros de subcategoria e confiança correspondem à mesma linha relacional da categoria selecionada. Origem também funciona para execuções automáticas sem categoria vencedora. A revisão mostra até 200 registros não classificados ou de baixa confiança; os demais continuam acessíveis pela pesquisa paginada.

## Limitações conhecidas

O contexto é uma janela lexical e não uma análise linguística de cláusulas, negação ou intenção. Objetos longos com muitos itens podem associar termos próximos de forma imprecisa. A cobertura inicial é deliberadamente conservadora; Não Classificado não representa erro da coleta. Termos e pesos devem evoluir com revisão humana.

Histórico de classificações e backups não é eliminado automaticamente; é necessário acompanhar espaço em disco. Exportação XLSX mantém o workbook em memória: arquivos muito grandes exigem memória proporcional ao volume. Testes de 10 mil registros não constituem garantia de desempenho para qualquer acervo.
