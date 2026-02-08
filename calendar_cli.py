#!/usr/bin/env python3
"""
CLI centralizada para gerenciar calendários do Mirassol FC
Comandos: list, create, delete, update, sync, share
"""

import argparse
import sys
import os
import urllib.parse

from calendar_utils import (
    CalendarAuth, CalendarManager, EventManager, ICSManager,
    CALENDAR_ID_FILE
)


class CalendarCLI:
    """Interface de linha de comando para gerenciar calendários"""
    
    def __init__(self):
        self.service = None
        self.cal_manager = None
        self.event_manager = None
    
    def _initialize(self):
        """Inicializa serviço quando necessário"""
        if self.service is None:
            try:
                self.service = CalendarAuth.authenticate()
                self.cal_manager = CalendarManager(self.service)
                self.event_manager = EventManager(self.service)
            except Exception as e:
                print(f"❌ Erro de autenticação: {e}")
                sys.exit(1)
    
    # ============ COMANDO: LIST ============
    def cmd_list(self, args):
        """Lista todos os calendários"""
        self._initialize()
        
        calendars = self.cal_manager.list_calendars()
        
        if not calendars:
            print("📭 Nenhum calendário encontrado")
            return
        
        print(f"\n📋 Total de calendários: {len(calendars)}\n")
        
        for i, cal in enumerate(calendars, 1):
            summary = cal.get('summary', 'Sem nome')
            cal_id = cal['id']
            owner = cal.get('dataOwner', False)
            
            owner_badge = " 👤 (seu)" if owner else ""
            print(f"{i}. {summary}{owner_badge}")
            print(f"   ID: {cal_id}")
            
            # Mostra quantidade de eventos
            events = self.event_manager.list_events(cal_id, max_results=1)
            total_events = len(events)
            if total_events > 0:
                print(f"   📌 {total_events} evento(s)")
            
            print()
    
    # ============ COMANDO: CREATE ============
    def cmd_create(self, args):
        """Cria um novo calendário"""
        self._initialize()
        
        name = args.name
        description = args.description or f"Calendário {name}"
        timezone = args.timezone or "America/Sao_Paulo"
        
        cal_id = self.cal_manager.create_calendar(
            name=name,
            description=description,
            timezone=timezone
        )
        
        if cal_id and args.share_email:
            role = args.share_role or 'reader'
            self.cal_manager.share_calendar(cal_id, args.share_email, role)
            
            # Gera link
            calendar_link = f"https://calendar.google.com/calendar/u/0?cid={urllib.parse.quote(cal_id)}"
            print(f"\n🔗 Link para adicionar: {calendar_link}")
    
    # ============ COMANDO: DELETE ============
    def cmd_delete(self, args):
        """Deleta um calendário"""
        self._initialize()
        
        cal_id = args.id
        
        if not args.force:
            cal_info = self.cal_manager.get_calendar_info(cal_id)
            if not cal_info:
                print("❌ Calendário não encontrado")
                return
            
            print(f"\n⚠️  Calendário: {cal_info.get('summary', 'Desconhecido')}")
            print(f"📝 ID: {cal_id}")
            
            confirm = input("\n⛔ Confirmar exclusão? (s/n): ").strip().lower()
            if confirm != 's':
                print("❌ Operação cancelada")
                return
        
        if self.cal_manager.delete_calendar(cal_id):
            # Remove arquivo de ID se existir
            if os.path.exists(CALENDAR_ID_FILE):
                with open(CALENDAR_ID_FILE, 'r') as f:
                    saved_id = f.read().strip()
                if saved_id == cal_id:
                    os.remove(CALENDAR_ID_FILE)
    
    # ============ COMANDO: UPDATE ============
    def cmd_update(self, args):
        """Atualiza calendário com eventos do arquivo .ics"""
        self._initialize()
        
        # Obtém ou cria o calendário MirassolFC
        cal_id = args.id
        
        if not cal_id:
            # Usa o método que garante MirassolFC (cria se não existir)
            cal_id = self.cal_manager.get_or_create_mirassol_calendar()
        
        if not cal_id:
            print("❌ Erro ao obter/criar calendário MirassolFC")
            return
        
        print(f"\n📅 Calendário: {cal_id}\n")
        
        # Limpa eventos antigos se solicitado
        if args.clear:
            if getattr(args, 'yes', False):
                # Auto-confirm for CI/non-interactive
                self.event_manager.delete_all_events(cal_id)
            else:
                confirm = input("⚠️  Deletar todos os eventos existentes? (s/n): ").strip().lower()
                if confirm == 's':
                    self.event_manager.delete_all_events(cal_id)
                else:
                    print("⏭️  Mantendo eventos existentes")
        
        # Faz upload dos novos eventos
        print("\n📖 Lendo arquivo .ics...")
        try:
            vevents = ICSManager.parse_ics_file()
            
            print("\n⬆️  Fazendo upload dos eventos...\n")
            successful, failed = self.event_manager.upload_events(cal_id, vevents)
            
            print(f"\n{'='*60}")
            print(f"✨ Sincronização concluída!")
            print(f"{'='*60}\n")
        
        except FileNotFoundError as e:
            print(f"❌ {e}")
    
    # ============ COMANDO: SHARE ============
    def cmd_share(self, args):
        """Compartilha um calendário com um email"""
        self._initialize()
        
        cal_id = args.id
        email = args.email
        role = args.role or 'reader'
        
        if not self.cal_manager.get_calendar_info(cal_id):
            print("❌ Calendário não encontrado")
            return
        
        if self.cal_manager.share_calendar(cal_id, email, role):
            # Gera link
            calendar_link = f"https://calendar.google.com/calendar/u/0?cid={urllib.parse.quote(cal_id)}"
            print(f"\n🔗 Link para importar: {calendar_link}")
    
    # ============ COMANDO: INFO ============
    def cmd_info(self, args):
        """Mostra informações de um calendário"""
        self._initialize()
        
        cal_id = args.id
        if not cal_id:
            # Se não informar ID, usa MirassolFC
            cal_id = self.cal_manager.get_or_create_mirassol_calendar()
        
        if not cal_id:
            print("❌ Erro ao obter/criar calendário MirassolFC")
            return
        
        cal_info = self.cal_manager.get_calendar_info(cal_id)
        if not cal_info:
            print("❌ Calendário não encontrado")
            return
        
        print(f"\n{'='*60}")
        print(f"📅 {cal_info.get('summary', 'Sem nome')}")
        print(f"{'='*60}")
        print(f"ID: {cal_info['id']}")
        print(f"TimeZone: {cal_info.get('timeZone', 'Padrão')}")
        print(f"Descrição: {cal_info.get('description', '-')}")
        
        # Lista eventos
        events = self.event_manager.list_events(cal_id, max_results=100)
        print(f"\n📌 Total de eventos: {len(events)}")
        
        if events and args.show_events:
            print("\nPrimeiros 10 eventos:")
            for i, event in enumerate(events[:10], 1):
                print(f"  {i}. {event.get('summary', 'Sem título')}")
            if len(events) > 10:
                print(f"  ... e mais {len(events) - 10}")
        
        print()


def main():
    parser = argparse.ArgumentParser(
        description="CLI para gerenciar calendários do Mirassol FC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python calendar_cli.py list                          # Listar calendários
  python calendar_cli.py create MirassolFC             # Criar calendário
  python calendar_cli.py delete <calendar_id>         # Deletar calendário
  python calendar_cli.py update --clear                # Atualizar com .ics
  python calendar_cli.py share <id> seu@email.com    # Compartilhar
  python calendar_cli.py info <calendar_id>           # Ver informações
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponíveis')
    
    # ============ SUBCOMMAND: LIST ============
    list_parser = subparsers.add_parser('list', help='Listar todos os calendários')
    list_parser.set_defaults(func=lambda args: cli.cmd_list(args))
    
    # ============ SUBCOMMAND: CREATE ============
    create_parser = subparsers.add_parser('create', help='Criar novo calendário')
    create_parser.add_argument('name', help='Nome do calendário')
    create_parser.add_argument('-d', '--description', help='Descrição do calendário')
    create_parser.add_argument('-z', '--timezone', default='America/Sao_Paulo', help='Timezone (padrão: America/Sao_Paulo)')
    create_parser.add_argument('-s', '--share-email', help='Email para compartilhar')
    create_parser.add_argument('-r', '--share-role', choices=['reader', 'writer', 'owner'], help='Tipo de permissão')
    create_parser.set_defaults(func=lambda args: cli.cmd_create(args))
    
    # ============ SUBCOMMAND: DELETE ============
    delete_parser = subparsers.add_parser('delete', help='Deletar calendário')
    delete_parser.add_argument('id', help='ID do calendário')
    delete_parser.add_argument('-f', '--force', action='store_true', help='Não pedir confirmação')
    delete_parser.set_defaults(func=lambda args: cli.cmd_delete(args))
    
    # ============ SUBCOMMAND: UPDATE ============
    update_parser = subparsers.add_parser('update', help='Atualizar calendário com eventos do .ics')
    update_parser.add_argument('-id', '--id', help='ID do calendário (opcional, usa MirassolFC por padrão)')
    update_parser.add_argument('-c', '--clear', action='store_true', help='Deletar eventos antigos antes de adicionar')
    update_parser.add_argument('-y', '--yes', action='store_true', help='Confirmar automaticamente deleção de eventos (não interativo)')
    update_parser.set_defaults(func=lambda args: cli.cmd_update(args))
    
    # ============ SUBCOMMAND: SHARE ============
    share_parser = subparsers.add_parser('share', help='Compartilhar calendário')
    share_parser.add_argument('id', help='ID do calendário')
    share_parser.add_argument('email', help='Email para compartilhar')
    share_parser.add_argument('-r', '--role', choices=['reader', 'writer', 'owner'], help='Tipo de permissão (padrão: reader)')
    share_parser.set_defaults(func=lambda args: cli.cmd_share(args))
    
    # ============ SUBCOMMAND: INFO ============
    info_parser = subparsers.add_parser('info', help='Informações de um calendário')
    info_parser.add_argument('id', nargs='?', help='ID do calendário (opcional)')
    info_parser.add_argument('-e', '--show-events', action='store_true', help='Mostrar lista de eventos')
    info_parser.set_defaults(func=lambda args: cli.cmd_info(args))
    
    # Parse argumentos
    args = parser.parse_args()
    
    # Executa comando
    if hasattr(args, 'func'):
        try:
            args.func(args)
        except KeyboardInterrupt:
            print("\n\n⛔ Operação cancelada pelo usuário")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Erro: {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == '__main__':
    cli = CalendarCLI()
    main()
