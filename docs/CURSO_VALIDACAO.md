# Curso de Licitações - implementação e validação

Data: 08/10/2026. Edição do conteúdo: 1.0.

## Entrega

- Menu **Curso de Licitações**, com 15 módulos de leitura offline.
- Constituição e cadastro da empresa, habilitação, edital, formação de preço, proposta e pregão, recursos, contratação, execução, medição, nota fiscal, pagamento e encerramento.
- Módulo específico de leilão de alienação, separado do fornecimento de bens e serviços.
- Exercícios com resposta comentada, marcação de leitura e progresso no banco local. A marcação é de leitura, não certificação.
- Apostila PDF de 37 páginas, sumário e referências clicáveis, exercícios e gabarito.
- Três links externos EV.G fornecidos pelo usuário, com títulos conferidos e endereço alternativo para o curso 887.

## Fontes e manutenção

Conteúdo autoral baseado em legislação e orientações oficiais. Base principal: Lei nº 14.133/2021; complementos LC nº 123/2006, Lei nº 4.320/1964, IN SEGES/ME nº 73/2022 e nº 77/2022, REDESIM, SICAF e Compras.gov.br. Referências por módulo constam no aplicativo e no PDF. A aplicação federal das instruções normativas é explicitada. O curso tem data de revisão, não atualização jurídica automática, e não representa formação oficial da Enap.

A fonte única está em `src/learning/course.json`. A geração da apostila usa ReportLab apenas no ambiente de autoria. O aplicativo copia atomicamente o PDF já empacotado, sem rede, impressora ou biblioteca PDF adicional. Um manifesto com hashes verifica correspondência entre conteúdo e apostila; divergências impedem exportar material desatualizado.

## Verificações

- Suíte completa: **105 aprovados, 2 opcionais online ignorados, nenhuma falha**, conforme `scratch/build_course.log`.
- Testes do curso: navegação, tentativa sem resposta, resposta incorreta/correta, reabertura com progresso salvo, marcar/desmarcar leitura, exportar e cancelar, rejeição de PDF desatualizado, preservação de arquivo em falha de escrita, tolerância a progresso malformado e abertura dos links oficiais.
- PDF: 37 páginas, 15 módulos, três cursos externos e 45 links externos. Conferidos integralmente 261 trechos de objetivos, conceitos, passos, exemplos, listas e exercícios/gabarito.
- Revisão visual: todas as páginas renderizadas; interface inspecionada em 1380×880 e 1024×680. Não observados cortes, sobreposições ou caracteres ausentes nas revisões.
- Build verifica o curso no executável, inclusive integridade do PDF, e mantém o teste de instância única. Resultado em `scratch/packaged_smoke_result.json`.

## Limites

Não houve homologação em outro computador ou em todos os níveis de DPI. Links e legislação podem mudar após a revisão. O progresso pertence ao banco local, compartilhado por quem utiliza esse mesmo banco; não há autenticação de alunos. O curso é introdutório e não substitui a leitura integral do edital ou a análise jurídica/contábil do caso concreto. Inscrição e certificação dos cursos gratuitos são realizadas exclusivamente na EV.G.
