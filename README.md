# JARVIS

JARVIS é um agente local para Windows, escrito em Python, que entende pedidos por voz, consulta o estado do computador e executa ações por meio de ferramentas explícitas. O objetivo é abrir projetos e aplicativos, controlar tarefas de desenvolvimento e responder com clareza antes de qualquer ação sensível.

## Exemplo de uso

> **Você:** “Jarvis, abre o AgenciaFlow e sobe o Docker.”
> **JARVIS:** localiza o projeto cadastrado, abre o VS Code, inicia os serviços configurados e informa o resultado.

> **Você:** “Jarvis, meu PC está pesado.”
> **JARVIS:** consulta CPU, memória e processos; resume os maiores consumidores.

## Instalação no Windows

Pré-requisitos: Python 3.13 ou 3.14, Git e, para a memória completa, Docker Desktop. No PowerShell, dentro do repositório (troque `3.13` pela versão instalada, se necessário):

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[voice,windows,openai,anthropic,memory,dev]"
jarvis init
jarvis chat
```

`jarvis init` cria `%LOCALAPPDATA%\Jarvis\config.json`. Cadastre seus aplicativos, projetos e scripts ali, seguindo [`config.example.json`](config.example.json). O arquivo local e as chaves de API não devem entrar no Git. Para usar apenas comandos de texto, instale `pip install -e ".[dev]"`; os extras de voz, IA e memória são opcionais.

No Linux com Python 3.12+, o pacote `openWakeWord` não tem uma dependência `tflite-runtime` compatível. O modo de voz desta versão é direcionado ao Windows; o núcleo em texto e a infraestrutura de dados funcionam em Linux.

Para uma instalação fora do checkout, crie o ambiente em `%LOCALAPPDATA%\Jarvis\venv` e instale o pacote nele. Copie `infra.env` para `%LOCALAPPDATA%\Jarvis\infra.env` se quiser usar a memória; o arquivo contém a senha local e não deve ser compartilhado. O script [`scripts/Start-Jarvis.ps1`](scripts/Start-Jarvis.ps1) carrega essas conexões e inicia `chat` ou `voice` pelo ambiente instalado:

```powershell
.\scripts\Start-Jarvis.ps1 -Mode chat
.\scripts\Start-Jarvis.ps1 -Mode voice
```

O modo de voz inicia com `jarvis voice`. Ele baixa os modelos locais na primeira execução. O modelo público de ativação reconhece **“Hey Jarvis”**; apenas “Jarvis” pode funcionar com menor confiabilidade. Depois da ativação, fale o pedido. Confirmações de ações de nível 2 são digitadas no terminal como `sim`.

## Fluxo

```text
Wake word → transcrição → interpretação → política de permissões
          → ferramentas locais → resposta → síntese de voz
```

O núcleo separa a interpretação da execução. Pedidos simples são resolvidos pelo roteador local. Para usar IA, altere `provider` para `openai` ou `anthropic`, informe `model` com um modelo disponível na sua conta e defina `OPENAI_API_KEY` ou `ANTHROPIC_API_KEY` no ambiente. O pedido, resultados das ferramentas e, quando relevante, trechos recuperados da memória são enviados ao provedor. O modelo recebe ferramentas registradas com argumentos validados; ele não ganha acesso a um shell genérico.

## Ferramentas da v0.1

`jarvis tools` lista as dez ferramentas. Elas consultam sistema/processos, abrem aplicativos, URLs e projetos, ajustam volume, procuram arquivos em projetos, iniciam/param Docker Compose e executam scripts PowerShell cadastrados. `run_powershell` aceita apenas um alias de script `.ps1` sem argumentos; não executa texto arbitrário fornecido pelo modelo.

Visão da tela, mouse/teclado, SSH e Home Assistant ficam para RFCs futuras. Capturas de tela nunca devem ser enviadas a um provedor remoto sem ciência do usuário.

## Permissões

| Nível | Exemplos | Regra |
| --- | --- | --- |
| 0 | Estado do sistema, processos | Somente leitura |
| 1 | Abrir aplicativo, URL ou projeto; volume | Executar com argumentos validados |
| 2 | Docker e scripts PowerShell cadastrados | Mostrar o alvo e exigir `sim` no terminal |
| 3 | Exclusão, encerramento de processos, administração | Reservado para RFC futura; ainda não há ferramentas desse nível |

As permissões são aplicadas pelo núcleo, independentemente da resposta do modelo. Toda ferramenta deve declarar seu nível, validar os argumentos e devolver um resultado estruturado. Segredos ficam fora do repositório; logs devem evitar tokens, transcrições sensíveis e conteúdo de arquivos.

## Memória: PostgreSQL, Redis e OpenSearch

O PostgreSQL é a fonte dos aliases estruturados quando `JARVIS_DATABASE_URL` está definido. O Redis guarda até dez interações recentes com expiração de 24 horas. O OpenSearch guarda apenas fatos e registros adicionados explicitamente, com busca híbrida por texto e vetor local. A memória recuperada serve como contexto; somente o núcleo pode autorizar uma ferramenta.

Para iniciar a infraestrutura local, copie [`infra.env.example`](infra.env.example) para `infra.env`, troque a senha e execute `docker compose --env-file infra.env up -d`. Os serviços escutam somente em `127.0.0.1`. No PowerShell, defina `JARVIS_DATABASE_URL`, `JARVIS_REDIS_URL` e `JARVIS_OPENSEARCH_URL` com os valores do arquivo antes de executar `jarvis data init`. O OpenSearch pode precisar de `vm.max_map_count=262144` no WSL do Docker Desktop; veja a [instrução oficial](https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/).

```powershell
jarvis data init
jarvis data catalog import-config
jarvis data catalog list
jarvis data memory add decision "Projeto obrigatório no orçamento" --project AgenciaFlow
jarvis data memory search "problema com orçamento" --project AgenciaFlow
```

`jarvis data catalog add project AgenciaFlow C:\Projetos\agenciaflow --compose-file compose.yaml` cadastra outro projeto. Use `jarvis data memory delete <ID>` para remover um registro. No chat, “lembre que ...” grava um fato e “sempre que eu falar ...” grava uma preferência; perguntas como “lembra daquele problema?” pesquisam o OpenSearch. A primeira execução da busca vetorial baixa o modelo de embeddings.

## Desenvolvimento e limites

Rode `python -m pytest`, `ruff check .` e `ruff format --check .` antes de enviar mudanças. Os testes automatizados rodam em Linux e Windows; a ativação por voz com fala real, volume, VS Code, Docker Desktop e as APIs remotas ainda exigem verificação interativa no PC. O Compose local é para desenvolvimento; a configuração do OpenSearch desativa autenticação e não deve ser exposta na rede.

## Desenvolvimento orientado por RFC

Toda funcionalidade ou mudança de arquitetura começa com uma RFC em [`docs/rfcs/`](docs/rfcs/). A [RFC 0001](docs/rfcs/0001-arquitetura-inicial.md) define o núcleo; a [RFC 0002](docs/rfcs/0002-memoria.md) define a memória. Use o [modelo de RFC](docs/rfcs/TEMPLATE.md) nas próximas decisões.
