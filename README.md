# Mirassol FC Calendar CLI Tool

Este repositório contém uma ferramenta de linha de comando (CLI) que permite interagir com calendários do clube Mirassol Futebol Clube.

## Estrutura do Repositório

### Arquivos Principais:

- `calendar_cli.py`: Contém a classe principal `CalendarCLI` e funções para manipular o calendário.
- `calendar_utils.py`: Contém classes e métodos auxiliares como autenticação, criação de eventos e gerenciamento de calendários.
- `scraper.py`: Implementa um scraper que extrai informações do site do Mirassol FC e gera arquivos ICS.

### Arquivos Executáveis:

- `run.sh`: Script bash para iniciar a ferramenta CLI.
- `.github/workflows/sync-google-calendar.yml`: Configuração de fluxo de trabalho GitHub para sincronizar o calendário com Google Calendar.

## Funcionalidades Principais

### calendar_cli.py

A classe `CalendarCLI` fornece vários comandos:

- **Inicialização:** Inicializa a interface da linha de comando.
- **Comandos Disponíveis:**
  - `create`: Cria um novo calendário.
  - `delete`: Exclui um calendário existente.
  - `info`: Obtém informações sobre um calendário específico.
  - `list`: Lista todos os calendários disponíveis.
  - `share`: Compartilha um calendário com outros usuários.
  - `update`: Atualiza eventos em um calendário.

### calendar_utils.py

Esta biblioteca fornece classes e métodos para manipular a integração com o Google Calendar:

- **CalendarAuth:** Autentica o usuário no sistema do Google Calendar.
- **EventManager, ICSManager:** Gerenciam os eventos de calendário e convertem objetos VEVENT em eventos do Google.
- **CalendarManager:** Manipula operações CRUD (Create, Read, Update, Delete) relacionadas a calendários.

### scraper.py

O módulo `scraper` é responsável por extrair dados do site oficial do Mirassol FC e gerar um arquivo ICS com os horários de jogos:

- **MirassolScraper:** Classe principal que implementa métodos para coletar informações sobre jogos, gols e datas.
  - **Metódos principais:**
    - `fetch_page`: Recupera a página HTML do site.
    - `parse_date`, `parse_time`, `parse_score`: Extrai detalhes específicos das páginas.

## Requisitos

Para executar a ferramenta, você precisará instalar as dependências listadas em `requirements.txt`.

## Como Iniciar o Projeto

1. Certifique-se de ter um ambiente Python configurado.
2. Instale as dependências usando:
   ```
   pip install -r requirements.txt
   ```
3. Execute a ferramenta CLI com:

   ```sh
   ./run.sh
   ```

4. O projeto também inclui uma pipeline GitHub Actions para sincronizar o calendário ICS com um Google Calendar.

## Contribuições

Contribuições são bem-vindas! Se você encontrar problemas ou quiser sugerir melhorias, sinta-se à vontade para abrir uma issue ou pull request.
