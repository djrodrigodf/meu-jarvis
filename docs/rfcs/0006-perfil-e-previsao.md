# RFC 0006: Perfil aprendido e previsão do tempo

- **Status:** Accepted
- **Data:** 2026-09-23
- **Autores:** Equipe JARVIS

## Contexto e motivação

O JARVIS precisa responder à previsão sem abrir uma busca e aprender nome e cidade durante a conversa. Uma cidade fixa na configuração não acompanha mudanças do usuário.

## Proposta

Guardar fatos estáveis e explícitos do perfil em uma tabela `user_profile` no PostgreSQL. Frases como “meu nome é Ana” e “moro em Recife” atualizam, respectivamente, `name` e `home_city`. O usuário pode substituir esses valores declarando novos fatos ou apagá-los com “esqueça meu nome/minha cidade”. Perguntas sobre o próprio perfil consultam essa tabela. Para previsão, usar a cidade dita na pergunta; na ausência dela, usar `home_city` ou a última cidade fornecida como preferência de previsão. Se não houver cidade conhecida, perguntar e usar a próxima resposta como cidade, salvando `weather_city` após geocodificação válida. Consultar a API estruturada Open-Meteo com prazo de resposta limitado e atribuir a fonte. Pedidos com cidade explícita não alteram a cidade de residência.

## Segurança e privacidade

Nome e cidade ficam no PostgreSQL local, nunca no repositório. Somente declarações claras ou resposta a uma pergunta de cidade são promovidas automaticamente. Uma memória recuperada não autoriza ferramentas. A previsão é uma consulta de nível 0 e envia apenas a cidade à Open-Meteo.

## Alternativas consideradas

Uma cidade em `config.json` exigiria edição manual. Gravar toda conversa como memória permanente criaria fatos incorretos e excesso de dados.

## Critérios de aceitação

- [x] O JARVIS aprende e recupera nome e cidade entre sessões.
- [x] A previsão usa a cidade conhecida e pergunta quando falta contexto.
- [x] A resposta inclui temperatura, condição, chuva e fonte, sem abrir navegador.
- [x] Cidade inválida ou serviço indisponível produz erro compreensível.
