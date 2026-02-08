# 📅 Calendar CLI - Documentação

## 🎯 Visão Geral

CLI centralizada para gerenciar o calendário do Mirassol FC no Google Calendar com automação garantida.

**Comportamento principal:**

- **Sempre usa um único calendário fixo: "MirassolFC"**
- Se não existir, cria automaticamente
- Se existir, reutiliza o mesmo calendário
- Salva o ID em `mirassolfc_calendar_id.txt` para referência rápida

## 🚀 Como Usar

### Via Python direto:

```bash
# Listar calendários
python calendar_cli.py list

# Criar calendário (manual)
python calendar_cli.py create MirassolFC

# Ver ajuda completa
python calendar_cli.py --help
```

### Via run.sh (recomendado):

```bash
# Ver ajuda
./run.sh

# Listar calendários
./run.sh list

# Criar calendário (manual)
./run.sh create MirassolFC -d "Calendário de jogos"

# Deletar calendário (com confirmação)
./run.sh delete <calendar_id>

# Deletar sem confirmação
./run.sh delete <calendar_id> -f

# Atualizar com eventos do .ics (usa MirassolFC automaticamente)
./run.sh update

# Atualizar deletando eventos antigos
./run.sh update -c

# Atualizar com confirmação automática (para CI)
./run.sh update -c -y

# Compartilhar calendário
./run.sh share <calendar_id> seu@email.com

# Compartilhar com permissão de escrita
./run.sh share <calendar_id> seu@email.com -r writer

# Ver informações do calendário (usa MirassolFC automaticamente)
./run.sh info

# Ver informações com lista de eventos
./run.sh info -e

# Usar calendário específico
./run.sh info <calendar_id>

# Executar web scraper
./run.sh scrape
```

## 📋 Referência de Comandos

### `list`

Lista todos os calendários disponíveis.

```bash
./run.sh list
```

**Saída:**

```
📋 Total de calendários: 2

1. MirassolFC 👤 (seu)
   ID: e1c0e757480864581bc95cf02f120f1a2d63a7568faa8451aab14fff55436bee@group.calendar.google.com

2. Pessoal
   ID: def456xyz...
```

---

### `create` <nome> [opções]

Cria um novo calendário.

```bash
./run.sh create MirassolFC
./run.sh create MirassolFC -d "Calendário de jogos" -s seu@email.com
```

**Opções:**

- `-d, --description` - Descrição do calendário
- `-s, --share-email` - Email para compartilhar automaticamente
- `-r, --share-role` - Tipo de permissão: `reader` (padrão), `writer`, `owner`
- `-z, --timezone` - Timezone (padrão: America/Sao_Paulo)

---

### `delete` <id> [opções]

Deleta um calendário.

```bash
./run.sh delete abc123xyz...
./run.sh delete abc123xyz... -f  # Sem confirmação
```

**Opções:**

- `-f, --force` - Não pedir confirmação

---

### `update` [opções]

Atualiza o calendário **MirassolFC** (cria se não existir) com eventos do arquivo `mirassolfc.ics`.
Automaticamente procura o calendário existente ou cria um novo, garantindo sempre o uso de um único calendário.

```bash
./run.sh update
./run.sh update -c  # Deletar eventos antigos primeiro
./run.sh update -c -y  # Deletar e confirmar automaticamente (ideal para CI)
./run.sh update -id abc123xyz...  # Usar calendário específico (opcional)
```

**Opções:**

- `-id, --id` - ID do calendário (usa MirassolFC por padrão, buscando ou criando se necessário)
- `-c, --clear` - Deletar todos os eventos antes de adicionar
- `-y, --yes` - Confirmar automaticamente deleção de eventos (útil para CI / execução não interativa)

**Processo:**

1. **Busca ou cria o calendário "MirassolFC":**
   - Primeiro tenta usar ID salvo em `mirassolfc_calendar_id.txt`
   - Se não existir o arquivo, procura por calendário com nome "MirassolFC"
   - Se não encontrar, cria um novo calendário
   - Salva o ID para próximas execuções

2. Lê eventos do arquivo .ics
3. Deleta eventos antigos (se `-c`)
4. Faz upload dos novos eventos
5. Mostra resumo de sucessos/falhas

---

### `share` <id> <email> [opções]

Compartilha um calendário com um email.

```bash
./run.sh share abc123xyz... seu@email.com
./run.sh share abc123xyz... seu@email.com -r writer
```

**Opções:**

- `-r, --role` - Tipo de permissão: `reader` (padrão), `writer`, `owner`

**Saída:**

```
✅ Calendário compartilhado com seu@email.com (reader)

🔗 Link para importar: https://calendar.google.com/calendar/u/0?cid=...
```

---

### `info` [id] [opções]

Mostra informações detalhadas de um calendário.

```bash
# Usa MirassolFC automaticamente
./run.sh info

# Usa MirassolFC com lista de eventos
./run.sh info -e

# Usa calendário específico
./run.sh info abc123xyz...

# Usa calendário específico com eventos
./run.sh info abc123xyz... -e
```

**Opções:**

- `id` - ID do calendário (usa MirassolFC automáticamente se omitido)
- `-e, --show-events` - Listar primeiros 10 eventos

---

### `scrape`

Executa web scraper para atualizar arquivo .ics.

```bash
./run.sh scrape
```

**Processo:**

1. Executa `scraper.py`
2. Se houver mudanças, faz commit no git

---

## 🔐 Autenticação

O projeto suporta **4 métodos de autenticação** (em ordem de prioridade):

1. **Service Account** (`service-account.json`)
   - Arquivo local na raiz do projeto
   - Usa CLI do Google Cloud

2. **Service Account via Env Var** (`SERVICE_ACCOUNT_KEY`)
   - JSON como string em variável de ambiente
   - Útil para CI/CD

3. **Google Application Credentials** (`GOOGLE_APPLICATION_CREDENTIALS`)
   - Caminho para arquivo de credenciais
   - Variável de ambiente padrão do Google

4. **OAuth Interativo** (`token.pickle`)
   - Fluxo de login no navegador
   - Fallback para autenticação pessoal

## 📁 Arquivos Importantes

- `calendar_cli.py` - CLI principal com argparse
- `calendar_utils.py` - Módulo com funções compartilhadas
- `mirassolfc_calendar_id.txt` - Cache do ID do calendário MirassolFC
- `mirassolfc.ics` - Arquivo com eventos do calendário
- `run.sh` - Script wrapper amigável
- `requirements.txt` - Dependências Python
- `.github/workflows/sync-google-calendar.yml` - CI/CD workflow

## 💡 Exemplos Práticos

### Fluxo completo (manualmente):

```bash
# 1. Listar calendários existentes
./run.sh list

# 2. Atualizar com eventos (usa ou cria MirassolFC)
./run.sh update -c

# 3. Verificar resultado
./run.sh info -e
```

### Automação CI/CD (GitHub Actions):

O workflow `.github/workflows/sync-google-calendar.yml` executa:

```bash
python3 scraper.py          # Busca novos jogos
python3 calendar_cli.py update -c -y  # Atualiza MirassolFC
```

Disparo automático:

- Via GitHub Actions: Menu "Actions" → "📅 Sincronizar Google Calendar" → "Run workflow"

## 🔄 Ciclo de Vida MirassolFC

Quando você executa `./run.sh update` ou `python calendar_cli.py info` sem argumentos:

```
┌─ Lê mirassolfc_calendar_id.txt
│  ├─ Existe? → Valida ID
│  │  ├─ Válido? → USA ID (sucesso!)
│  │  └─ Inválido? → Continua busca
│  └─ Não existe? → Continua busca
│
└─ Busca por nome "MirassolFC"
   ├─ Encontrado? → SALVA ID + USA (sucesso!)
   └─ Não encontrado? → CRIA NOVO + SALVA ID + USA
```

## 🔧 Configuração

### Variáveis de Ambiente

```bash
# Método 1: Service Account como JSON string
export SERVICE_ACCOUNT_KEY='{"type":"service_account",...}'

# Método 2: Caminho do arquivo
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

## 🐛 Troubleshooting

### "Nenhum método de autenticação encontrado"

- Certifique-se de que `service-account.json` existe
- Ou defina uma variável de ambiente de autenticação

### "Arquivo .ics não encontrado"

- Execute o scraper: `./run.sh scrape`
- Ou verifique se `mirassolfc.ics` existe

### "Calendário não encontrado"

- Use `./run.sh list` para ver IDs disponíveis
- O comando `update` e `info` criam automaticamente se não existir

### Deletar MirassolFC e começar do zero

```bash
# 1. Limpar o arquivo de cache
rm -f mirassolfc_calendar_id.txt

# 2. Deletar via CLI
./run.sh list  # Pegar o ID
./run.sh delete <calendar_id> -f
```

## 📚 Referência Rápida

| Ação         | Comando                          |
| ------------ | -------------------------------- |
| Listar       | `./run.sh list`                  |
| Criar        | `./run.sh create NomeCalendario` |
| Deletar      | `./run.sh delete <id>`           |
| Atualizar    | `./run.sh update`                |
| Atualizar CI | `./run.sh update -c -y`          |
| Compartilhar | `./run.sh share <id> email@com`  |
| Info         | `./run.sh info`                  |
| Scrape       | `./run.sh scrape`                |
| Ajuda        | `./run.sh` ou `./run.sh --help`  |
