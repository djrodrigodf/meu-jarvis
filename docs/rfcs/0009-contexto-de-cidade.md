# RFC 0009: Contexto de cidade sem repetir a previsão

- **Status:** Accepted
- **Data:** 2026-09-23
- **Autores:** Equipe JARVIS

## Contexto e motivação

O histórico recente mostrou “Brasília” sendo interpretada repetidamente como um pedido de previsão. A transcrição imperfeita de “previsão do tempo” deixou a pergunta fora do roteador local, e perguntas sobre a cidade consultaram apenas `home_city`, ignorando `weather_city` já salva.

## Proposta

Reconhecer variantes comuns de transcrição de perguntas meteorológicas e perguntar a cidade antes da consulta. Tratar perguntas como “de qual cidade eu falei?” como consulta ao perfil: responder com cidade de residência quando conhecida ou distinguir a cidade usada para previsão. Uma cidade isolada que já está no perfil recebe confirmação contextual e não aciona nova previsão. Incluir ambos os campos de cidade no contexto fornecido ao LLM para outros pedidos; referências curtas recebem até três turnos recentes como dados. Manter `home_city` e `weather_city` separados: uma previsão não afirma onde o usuário mora.

## Segurança e privacidade

O histórico curto permanece no Redis por até 24 horas e dez turnos. O log de ações registra apenas ferramenta, nível, estado e horário, sem transcrições. A consulta ao LLM recebe somente os fatos de perfil necessários. Memória não executa ações sem validação do núcleo.

## Alternativas consideradas

Usar somente contexto recente do LLM já produziu a repetição. Tratar uma cidade consultada na previsão como residência criaria um fato pessoal incorreto.

## Critérios de aceitação

- [x] “De qual cidade eu falei?” reconhece a cidade usada na previsão.
- [x] “Brasília” isolado, quando já conhecido, não consulta a previsão.
- [x] Uma transcrição imperfeita de “previsão do tempo” ainda pede cidade.
- [x] A cidade de previsão não é descrita como residência.
