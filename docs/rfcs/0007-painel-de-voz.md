# RFC 0007: Painel de estado da voz

- **Status:** Accepted
- **Data:** 2026-09-23
- **Autores:** Equipe JARVIS

## Contexto e motivação

Sem retorno visual, o usuário não sabe se a palavra de ativação foi reconhecida ou se a consulta continua em andamento.

## Proposta

No Windows, `jarvis voice` abre um painel flutuante, sempre visível e arrastável. A interface mostra os estados preparando, aguardando, ouvindo, transcrevendo, pensando, executando e respondendo, com um detalhe curto da operação. A captura e a síntese de voz rodam em outra thread; uma fila entrega eventos à interface Tk. Um sinal sonoro breve confirma a ativação. Fechar o painel encerra o loop após a leitura de áudio corrente. `jarvis voice --no-hud` mantém o terminal para diagnóstico.

## Segurança e privacidade

O painel mostra somente estado e uma descrição curta da ferramenta. Ele não mostra credenciais, caminhos de arquivos ou conteúdo de memória. Não altera níveis de permissão.

## Alternativas consideradas

Logs no terminal não são visíveis durante o uso por voz. Notificações temporárias não mostram o estado de uma consulta longa.

## Critérios de aceitação

- [x] O painel aparece antes do carregamento dos modelos.
- [x] A ativação e cada etapa demorada ficam visíveis.
- [x] A interface continua responsiva durante consulta e síntese.
