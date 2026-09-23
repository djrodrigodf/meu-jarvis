# RFC 0004: Credencial Claude no Windows

- **Status:** Accepted
- **Data:** 2026-09-23
- **Autores:** Rodrigo e colaboradores

## Contexto e motivação

O núcleo já suporta Claude por `ANTHROPIC_API_KEY`, mas a instalação do Windows precisa persistir a credencial entre sessões sem colocá-la no Git ou em um arquivo de texto simples.

## Proposta

`scripts/Set-ClaudeKey.ps1` lê a chave sem eco no terminal e a protege com o DPAPI do usuário atual do Windows. O arquivo cifrado fica em `%LOCALAPPDATA%\Jarvis\anthropic.key.dpapi`. `scripts/Start-Jarvis.ps1` descriptografa o valor apenas durante a execução e define `ANTHROPIC_API_KEY` para o processo filho. O provedor e o modelo continuam no `config.json`, sem a chave.

## Segurança e limites

O arquivo DPAPI só pode ser aberto pela mesma conta do Windows. O segredo ainda existe na memória do processo enquanto a API é usada. A entrada pelo terminal evita colocá-lo em argumentos de comando, histórico do shell ou logs do repositório. Chaves compartilhadas em outros canais devem ser rotacionadas conforme a política da conta.

## Alternativas consideradas

- **Arquivo `.env` em texto simples:** mais fácil de configurar, porém deixa a chave legível em disco.
- **Variável de ambiente permanente do usuário:** expõe o segredo no registro e a outros processos dessa conta.

## Critérios de aceitação

- [x] O arquivo cifrado é criado fora do repositório sem ecoar a chave.
- [x] O iniciador carrega a chave e uma chamada curta à API funciona.
- [x] A chave não aparece no commit nem na configuração JSON.
