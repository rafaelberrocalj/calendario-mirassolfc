# Copilot Instructions

Este projeto sincroniza jogos do Mirassol FC entre um scraper do ESPN, um arquivo `.ics` e um Google Calendar.

## O que o assistente deve entender antes de editar

- `scraper.py` gera `mirassolfc.ics`.
- `calendar_cli.py update` sincroniza o `.ics` com o Google Calendar.
- `calendar_utils.py` contém a lógica crítica de reconciliação de eventos.
- O sistema já teve bug de duplicação por inserir tudo de novo em cada atualização.

## Invariantes obrigatórios

- A sincronização deve ser idempotente.
- O `UID` de cada `VEVENT` precisa continuar sendo usado como chave estável.
- O Google Calendar deve usar `extendedProperties.private.mirassol_uid` para reconciliar eventos.
- `delete_all_events()` e `info` devem usar listagem completa com paginação.
- Eventos sem horário definido devem continuar como all-day.

## Como validar uma alteração

Sempre sugerir ou executar esta ordem:

```bash
./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
./.venv/bin/python scraper.py
./.venv/bin/python calendar_cli.py update
./.venv/bin/python calendar_cli.py info -e
```

Se a mudança tocar no fluxo de duplicação:

```bash
./.venv/bin/python calendar_cli.py info -e
./.venv/bin/python calendar_cli.py update -c -y
./.venv/bin/python calendar_cli.py info -e
./.venv/bin/python calendar_cli.py update
./.venv/bin/python calendar_cli.py info -e
```

## O que evitar

- Não reintroduzir `insert` cego para todos os eventos.
- Não depender de `--clear` no workflow diário para manter consistência.
- Não usar listagens parciais da API do Google Calendar para contar ou deletar eventos.
- Não alterar a estrutura do `README.md` sem revisar `stats_collector.py`.

## Quando tocar no workflow

Preservar em `.github/workflows/sync-google-calendar.yml`:

- execução de testes antes da sincronização;
- `concurrency` para evitar sobreposição;
- atualização via `python calendar_cli.py update`;
- commit apenas de `mirassolfc.ics` quando houver diff.
