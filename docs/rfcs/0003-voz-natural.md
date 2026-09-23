# RFC 0003: Voz natural e configurável

- **Status:** Accepted
- **Data:** 2026-09-23
- **Autores:** Rodrigo e colaboradores

## Contexto e motivação

A síntese atual usa a voz padrão do Windows e soa mecânica. O projeto de referência `isair/jarvis` usa Piper com a voz britânica masculina `en_GB-alan-medium`. Queremos oferecer esse timbre e uma opção para português brasileiro sem alterar o núcleo nem a política de ferramentas.

## Proposta

Separar a síntese de fala do loop de microfone. Usar Piper local com `pt_BR-faber-medium` como padrão para respostas em português e disponibilizar `en_GB-alan-medium` para respostas em inglês. Oferecer uma voz neural online em português como opção, com velocidade e tom ajustáveis, e manter a síntese do Windows como alternativa. Configurar a voz por `config.json` e oferecer um comando de prévia que fala uma frase curta sem abrir o microfone. Durante uma resposta, suspender a captura do microfone para não ouvir o próprio áudio.

O Piper baixa o modelo uma vez e depois sintetiza localmente. A voz online recebe somente o texto da resposta. Áudio sintetizado permanece temporário e é descartado após a reprodução. Falhas de rede não devem encerrar o assistente: o sistema avisa e usa a voz do Windows.

## Segurança e privacidade

O backend online envia o texto falado a um serviço externo de síntese; o README deve explicar isso antes de ativá-lo. Piper e a voz do Windows preservam a operação sem rede após o download inicial. Nenhum backend recebe credenciais de ferramentas ou acesso ao sistema.

## Alternativas consideradas

- **Voz padrão do Windows:** funciona sem rede e já está instalada, mas motivou esta mudança pela qualidade limitada.
- **Voz britânica em inglês para tudo:** aproxima o sotaque esperado, mas pode prejudicar a pronúncia das respostas em português; por isso existe a opção `pt_BR-faber-medium`.
- **Clonar uma voz com Chatterbox:** exige uma amostra adequada e mais recursos de processamento; pode ser avaliado em uma RFC futura.

## Critérios de aceitação

- [x] A voz nova pode ser escolhida por configuração e testada sem wake word.
- [x] Uma resposta em português é sintetizada e reproduzida no Windows.
- [x] Falha de rede usa a voz local e mantém o loop ativo.
- [x] Os testes verificam configuração e fallback sem fazer chamadas externas.
