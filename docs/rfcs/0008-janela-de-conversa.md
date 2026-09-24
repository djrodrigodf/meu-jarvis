# RFC 0008: Janela de conversa após a ativação

- **Status:** Accepted
- **Data:** 2026-09-23
- **Autores:** Equipe JARVIS

## Contexto e motivação

Exigir “Hey Jarvis” em cada turno torna perguntas de acompanhamento artificiais. O problema aparece quando o assistente pergunta o nome ou a cidade e não aceita uma resposta curta sem nova ativação.

## Proposta

Uma ativação abre uma sessão de voz. Após cada resposta falada, o microfone permanece pronto por 30 segundos para o próximo pedido sem palavra de ativação; perguntas que aguardam nome ou cidade mantêm a janela por pelo menos 45 segundos. A janela reinicia após cada resposta e termina depois do silêncio ou com “tchau, Jarvis”. O painel mostra “CONVERSA ABERTA” e o tempo restante. A captura de um enunciado para depois de 1,2 segundo de silêncio ou 12 segundos de fala. A síntese termina antes de reabrir o microfone para evitar eco.

O núcleo mantém o tipo de resposta curta esperada. Depois de “Como você se chama?”, “Rodrigo” grava `name` no PostgreSQL. Depois de “Em qual cidade você mora?”, “Recife” grava `home_city`. Uma pergunta nova abandona a pendência e é tratada normalmente.

## Segurança e privacidade

O microfone já está ativo para detectar a palavra de ativação; durante a janela ele também reconhece comandos sem essa palavra. A janela é limitada e indicada visualmente. As mesmas validações e confirmações de ferramentas continuam obrigatórias. O áudio não é armazenado permanentemente.

## Alternativas consideradas

Um modo de escuta contínua aumentaria ativações acidentais. Exigir a palavra em todo turno interrompe perguntas de acompanhamento.

## Critérios de aceitação

- [x] Dois pedidos consecutivos podem ser feitos com uma ativação.
- [x] O painel indica a janela e seu encerramento por tempo.
- [x] Uma resposta curta a nome ou cidade é guardada entre sessões.
- [x] Após o tempo, um novo pedido volta a exigir a palavra de ativação.
