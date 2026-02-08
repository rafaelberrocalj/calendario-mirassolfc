#!/bin/bash
# CLI para gerenciar calendários do Mirassol FC
# Uso: ./run.sh list | create | delete | update | share | info

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Se não houver argumentos, mostra ajuda
if [ $# -eq 0 ]; then
    echo -e "${BLUE}📅 Mirassol FC Calendar CLI${NC}"
    echo ""
    echo "Comandos disponíveis:"
    echo ""
    echo -e "${GREEN}  ./run.sh list${NC}"
    echo "    Listar todos os calendários"
    echo ""
    echo -e "${GREEN}  ./run.sh create <nome> [opções]${NC}"
    echo "    Criar novo calendário"
    echo "    Opções: -d 'descrição' -s email@exemplo.com"
    echo ""
    echo -e "${GREEN}  ./run.sh delete <id> [-f]${NC}"
    echo "    Deletar calendário (use -f para não pedir confirmação)"
    echo ""
    echo -e "${GREEN}  ./run.sh update [opções]${NC}"
    echo "    Atualizar calendário com eventos do .ics"
    echo "    Opções: -c para limpar eventos antigos"
    echo ""
    echo -e "${GREEN}  ./run.sh share <id> <email> [-r role]${NC}"
    echo "    Compartilhar calendário com um email"
    echo "    role: reader (padrão), writer, owner"
    echo ""
    echo -e "${GREEN}  ./run.sh info <id> [-e]${NC}"
    echo "    Ver informações de um calendário"
    echo "    Use -e para mostrar eventos"
    echo ""
    echo -e "${GREEN}  ./run.sh scrape${NC}"
    echo "    Executar web scraper e atualizar .ics"
    echo ""
    exit 0
fi

# Comando especial: scrape (executa scraper.py)
if [ "$1" = "scrape" ]; then
    echo "🕷️  Executando web scraper..."
    python scraper.py
    
    if ! git diff --quiet mirassol_futebol_clube.ics; then
        git add mirassol_futebol_clube.ics
        git commit -m "Update Mirassol FC games from scraper"
        echo "✅ Calendário .ics atualizado e commitado"
    else
        echo "ℹ️  Nenhuma mudança no arquivo .ics"
    fi
    exit 0
fi

# Passa todos os argumentos para calendar_cli.py
python calendar_cli.py "$@"
