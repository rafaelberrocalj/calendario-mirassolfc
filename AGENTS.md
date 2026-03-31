# AGENTS.md

## Objetivo do Projeto

Este repositório mantém o calendário público do Mirassol FC.

O fluxo principal é:

1. `scraper.py` coleta jogos e resultados no ESPN.
2. O scraper gera `mirassolfc.ics` com `UID` estável por jogo.
3. `calendar_cli.py update` sincroniza o `.ics` com o Google Calendar.
4. O workflow em `.github/workflows/sync-google-calendar.yml` roda esse processo automaticamente.

O projeto precisa sempre garantir estas duas saídas:

- O arquivo `mirassolfc.ics` deve refletir os jogos atuais.
- O Google Calendar deve ficar sincronizado sem duplicar eventos.

## Arquitetura Resumida

- `scraper.py`
  Responsável por buscar jogos passados e futuros e gerar o `.ics`.
- `calendar_utils.py`
  Contém autenticação Google, operações de calendário e sincronização de eventos.
- `calendar_cli.py`
  Interface CLI para `list`, `create`, `update`, `share`, `info` e `stats`.
- `stats_collector.py`
  Coleta dados de uso do calendário e injeta estatísticas no `README.md`.
- `run.sh`
  Wrapper simples para uso manual.
- `tests/test_event_sync.py`
  Testes críticos de sincronização sem duplicação.

## Regras de Negócio que Não Podem Quebrar

### 1. A sincronização do Google Calendar deve ser idempotente

Rodar `python calendar_cli.py update` duas vezes seguidas não pode aumentar a quantidade de eventos.

Ao alterar a sincronização:

- preserve o `UID` do `.ics`;
- mantenha o uso de `extendedProperties.private.mirassol_uid`;
- continue fazendo `update` quando o evento já existir;
- use fallback para eventos legados quando necessário.

### 2. `--clear` precisa limpar tudo de verdade

Não use listagens parciais da API para remover eventos.
Ao mexer em exclusão ou listagem, preserve o uso da listagem completa com paginação.

### 3. O `.ics` não deve gerar duplicatas internas

Cada `VEVENT` precisa ter `UID` único e estável.
O `UID` é gerado a partir de data + times e é parte central da reconciliação com o Google Calendar.

### 4. Jogos sem horário definido continuam como evento de dia inteiro

Se o horário estiver indefinido, o evento deve permanecer all-day no `.ics` e no Google Calendar.

## Checklist Obrigatório Antes de Commit

Sempre que tocar em scraper, sincronização, workflow ou CLI:

1. Rode os testes locais:
   `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
2. Rode o scraper:
   `./.venv/bin/python scraper.py`
3. Verifique se `mirassolfc.ics` ficou coerente:
   `git diff -- mirassolfc.ics`
4. Rode a sincronização:
   `./.venv/bin/python calendar_cli.py update`
5. Verifique a contagem no calendário:
   `./.venv/bin/python calendar_cli.py info -e`

Se houver suspeita de duplicação:

1. confira a contagem atual;
2. rode `./.venv/bin/python calendar_cli.py update -c -y`;
3. confira a contagem novamente;
4. rode `./.venv/bin/python calendar_cli.py update`;
5. confirme que a contagem permaneceu estável.

## Passo a Passo do Workflow

O workflow correto é:

1. instalar dependências;
2. rodar testes;
3. escrever `service-account.json` a partir do secret;
4. rodar `scraper.py`;
5. rodar `calendar_cli.py update`;
6. remover credenciais locais;
7. commitar `mirassolfc.ics` apenas se houver diff.

Não volte para uma estratégia que dependa de `update -c -y` diariamente para esconder duplicação.
`--clear` é ferramenta de recuperação, não mecanismo principal de sincronização.

## Credenciais e Segurança

- Nunca commitar `service-account.json`, `credentials.json` ou `token.pickle`.
- Respeitar `.gitignore`.
- Em ambientes automatizados, usar `SERVICE_ACCOUNT_KEY` ou `GOOGLE_APPLICATION_CREDENTIALS`.

## Convenções para Futuras Edições

- Preserve a CLI atual; mudanças em argumentos devem ser justificadas.
- Prefira correções incrementais, sem refatorações amplas desnecessárias.
- Se alterar a estrutura do `README.md`, revise `stats_collector.py`, porque ele depende de padrões de seção para inserção.
- Se alterar scraping de data/hora, valide eventos com horário e eventos all-day.
- Se alterar o workflow, mantenha `concurrency` para evitar execuções sobrepostas.

## Comandos Úteis

```bash
./.venv/bin/python scraper.py
./.venv/bin/python calendar_cli.py update
./.venv/bin/python calendar_cli.py update -c -y
./.venv/bin/python calendar_cli.py info -e
./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

## Definição de Sucesso

Uma mudança está correta quando:

- os testes passam;
- o `.ics` continua consistente;
- a sincronização não duplica;
- a contagem final no Google Calendar permanece estável entre execuções repetidas.
