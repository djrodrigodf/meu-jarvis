# RFC 0002: Memória estruturada e busca híbrida

- **Status:** Accepted
- **Data:** 2026-09-23
- **Autores:** Rodrigo e colaboradores

## Contexto e motivação

O JARVIS precisa reconhecer projetos, máquinas e preferências sem enviar todo o histórico ao LLM. Dados operacionais exigem valores exatos; anotações e decisões pedem busca por significado. Memória incorreta ou maliciosa não pode virar uma ordem executável.

## Proposta

- **PostgreSQL:** fonte de verdade para aliases de aplicativos, projetos e scripts. Quando configurado, substitui os aliases do JSON. A importação inicial do JSON é explícita.
- **Redis:** até dez interações recentes por usuário local, com expiração de 24 horas. Serve apenas para contexto de curto prazo; não é memória permanente.
- **OpenSearch:** índice `jarvis-memory-v1` com tipo, projeto, conteúdo, data e vetor. O JARVIS gera embeddings localmente com `intfloat/multilingual-e5-small` e consulta texto e vetor por busca híbrida com RRF. Só trechos recuperados entram no contexto do LLM.
- **Memory Worker:** promove somente frases explícitas como “lembre que ...” e “sempre que eu falar ...”, ou registros inseridos via CLI. Classifica a segunda forma como preferência. Não indexa cada conversa automaticamente.

O núcleo faz a recuperação antes da interpretação quando há um pedido de lembrança. Resultados de memória são marcados como dados não confiáveis. Toda ação proposta continua passando pelo catálogo de ferramentas e pela política de permissões da RFC 0001. A interface de memória é opcional: o modo local continua funcionando sem os três serviços.

## Segurança e privacidade

Os serviços do Compose escutam somente em `127.0.0.1`; o exemplo local desativa a segurança do OpenSearch e não deve ser publicado em rede. Credenciais são passadas por variáveis de ambiente, fora do Git. O usuário pode buscar e apagar memórias por ID. Redis expira o contexto recente. Saídas de ferramentas e transcrições não são indexadas automaticamente. O uso de um LLM remoto envia apenas o pedido e os trechos recuperados necessários à resposta.

## Alternativas consideradas

- **Um único banco para tudo:** simplifica a implantação, mas enfraquece a separação entre dados exatos e busca semântica pedida para o projeto.
- **Salvar toda conversa:** facilitaria reconstruir histórico, mas adicionaria ruído e dados sensíveis sem valor duradouro.
- **Somente busca textual:** funciona para termos exatos, mas perde lembranças descritas com palavras diferentes.

## Critérios de aceitação

- [x] Aliases estruturados são lidos do PostgreSQL quando ele está configurado.
- [x] O Redis expira interações recentes e limita sua quantidade.
- [x] O OpenSearch indexa e recupera memória por texto e vetor, com filtro de projeto.
- [x] Apenas pedidos explícitos viram memórias permanentes.
- [x] Memória recuperada nunca executa uma ferramenta diretamente.
- [x] O usuário consegue inserir, buscar e excluir uma memória pela CLI.

## Referências técnicas

- [Busca híbrida e RRF no OpenSearch](https://docs.opensearch.org/latest/search-plugins/search-pipelines/score-ranker-processor/)
- [Filtro em consultas vetoriais do OpenSearch](https://docs.opensearch.org/latest/query-dsl/specialized/k-nn/index/)
- [Modelo multilíngue E5](https://huggingface.co/intfloat/multilingual-e5-small)
