# RFC 0005: Hora local e memória sob demanda

- **Status:** Accepted
- **Data:** 2026-09-23
- **Autores:** Rodrigo e colaboradores

## Contexto e motivação

O pedido “Quantas horas?” foi enviado ao Claude, que não tinha ferramenta para consultar o relógio. Antes da resposta, o núcleo carregou o modelo de embeddings para pesquisar o OpenSearch mesmo sem pedido de memória, exibindo um aviso do Hugging Face Hub e acrescentando latência.

## Proposta

Adicionar `get_current_time` como ferramenta de nível 0. O roteador local responde diretamente a perguntas simples sobre hora e data, usando o relógio e o fuso do Windows. Claude também recebe a ferramenta para perguntas mais complexas sobre a hora local.

Consultar a memória longa somente quando o pedido fizer referência explícita a lembranças ou decisões anteriores. Continuar capturando frases explícitas como “lembre que ...”. Ao carregar o modelo de embeddings, tentar primeiro o cache local; fazer download apenas se ele ainda não estiver disponível.

## Segurança e impacto

O relógio é uma consulta sem efeito colateral. O novo gatilho reduz acesso ao OpenSearch, uso de CPU e chamadas de rede em pedidos comuns. Perguntas vagas que dependem de memória podem precisar ser formuladas como “você lembra...”; os exemplos do README explicam essa regra.

## Alternativas consideradas

- **Pesquisar memória para cada pedido:** mantém recuperação implícita, mas causa custo e avisos desnecessários em perguntas como hora e status do PC.
- **Pedir ao Claude para estimar a hora:** não fornece dados confiáveis sobre o relógio local.

## Critérios de aceitação

- [x] “Quantas horas?” responde com hora local sem chamar LLM ou embeddings.
- [x] Pedidos comuns não pesquisam memória longa.
- [x] Um pedido explícito de lembrança continua usando a busca híbrida.
- [x] Testes em Linux e Windows cobrem esses caminhos.
