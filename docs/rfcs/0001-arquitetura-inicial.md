# RFC 0001: Arquitetura inicial do JARVIS

- **Status:** Accepted
- **Data:** 2026-09-23
- **Autores:** Rodrigo e colaboradores

## Contexto e motivação

O JARVIS deve atender pedidos sobre o PC Windows e automatizar tarefas locais sem conceder ao modelo acesso irrestrito ao sistema. A experiência desejada inclui voz, projetos cadastrados, diagnóstico de desempenho e ações em aplicativos e Docker. A primeira entrega precisa permitir testar a política de execução sem depender de microfone, áudio ou um provedor de IA.

## Proposta

Construir um núcleo Python com cinco componentes:

1. **Entrada:** recebe uma solicitação por texto; entrada por voz será adicionada sobre a mesma interface.
2. **Interpretador:** converte o pedido em uma intenção e argumentos. Começa com rotas explícitas para os comandos iniciais; provedores de LLM usam o mesmo contrato depois.
3. **Catálogo de ferramentas:** declara nome, esquema de argumentos, nível de permissão e função executora. O interpretador só pode escolher ferramentas registradas.
4. **Política de execução:** valida argumentos e alvo, determina o nível e solicita confirmação antes de ações sensíveis.
5. **Resposta e auditoria:** devolve resultado estruturado e registra ferramenta, nível, horário e resultado sem guardar alvos, segredos ou conteúdo sensível.

Fluxo: `pedido → interpretação → validação → política → ferramenta → resultado`.

O primeiro marco será um protótipo de terminal que consulta estado e processos, abre URLs/aplicativos cadastrados e demonstra confirmação para ações de nível 2. O usuário poderá configurar aliases de projetos localmente. A v0.1 também inclui wake word, transcrição, TTS e provedores de IA como componentes opcionais. A memória é detalhada na RFC 0002.

## Segurança e privacidade

Nível 0 permite consultas; nível 1 permite ações locais simples com argumentos validados; nível 2 exige confirmação para Docker e scripts PowerShell cadastrados. O nível 3 fica reservado para uma RFC futura antes de qualquer exclusão, encerramento de processos ou alteração administrativa. A política é aplicada fora do modelo. A primeira versão não oferece uma ferramenta de shell arbitrário ao interpretador. Credenciais ficam fora do repositório. Logs devem evitar tokens, transcrições e conteúdo de arquivos.

## Alternativas consideradas

- **Começar diretamente com voz e LLM:** aproxima a experiência final, mas dificulta isolar falhas de interpretação, permissão e execução. O terminal valida o núcleo primeiro.
- **Expor PowerShell sem restrições:** cobre mais ações, porém torna a política de permissões difícil de aplicar. Ferramentas específicas oferecem alvos e efeitos verificáveis.

## Critérios de aceitação

- [x] Um pedido por texto seleciona somente uma ferramenta registrada com argumentos validados.
- [x] Consultas de nível 0 retornam dados sem confirmação.
- [x] Uma ação de nível 2 mostra ferramenta e alvo e só executa após confirmação explícita.
- [x] Cancelamento ou argumentos inválidos não produzem efeitos no sistema.
- [x] Testes automatizados cobrem seleção de ferramenta, validação e política de permissão.
- [x] O README documenta instalação, execução e testes no Windows.

## Decisões de implementação

- Configuração inicial em JSON local; PostgreSQL torna-se a fonte dos aliases quando habilitado.
- Voz usa openWakeWord, faster-whisper e pyttsx3 como extras opcionais.
- OpenAI e Anthropic são configurados individualmente por variável de ambiente e nome de modelo; o modo local não exige chave.
