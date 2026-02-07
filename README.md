# 📅 Mirassol FC - Calendário de Jogos

Extrai dados de todos os jogos do Mirassol FC (passados e futuros) do site ESPN e gera um arquivo de calendário (.ics) para importar no Google Calendar.

## 📊 O Que Faz

- Busca os resultados de jogos já realizados (com placar final)
- Busca o calendário de próximos jogos
- Gera arquivo `mirassol_futebol_clube.ics` com 45 eventos
- Pronto para importar em qualquer aplicativo de calendário (Google Calendar, Outlook, Apple Calendar, etc)

## 📁 Arquivos

- `scraper.py` - Script principal que faz a extração
- `requirements.txt` - Dependências Python
- `mirassol_futebol_clube.ics` - Arquivo de calendário gerado
- `run.sh` - Execute o scraper e faça commit de alterações

## ⚙️ Configuração Inicial

### 1. Criar Virtual Environment

```bash
python3 -m venv venv
```

### 2. Ativar Virtual Environment

```bash
source venv/bin/activate
```

Você saberá que está ativo quando aparecer `(venv)` no terminal.

### 3. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 4. Executar o Script

```bash
./run.sh
```

O script irá:

- ✅ Executar o scraper
- ✅ Extrair dados de jogos
- ✅ Gerar `mirassol_futebol_clube.ics`
- ✅ Fazer commit automático se houver mudanças
