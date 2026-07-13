#!/usr/bin/env python3
"""Interface de linha de comando para gerenciar calendários do Mirassol FC.

Fornece comandos para criar, listar, deletar, atualizar, compartilhar e
monitora calendários do Google Calendar com sincronização de eventos via iCalendar.

Comandos disponíveis:
    list: Lista todos os calendários
    create: Cria um novo calendário
    delete: Deleta um calendário
    update: Sincroniza eventos de arquivo .ics
    share: Compartilha calendário com um email
    info: Mostra informações de um calendário
    stats: Mostra estatísticas de uso (quantas pessoas usam)

Exemplos:
    python calendar_cli.py list
    python calendar_cli.py create MirassolFC
    python calendar_cli.py update --clear
    python calendar_cli.py share seu@email.com
    python calendar_cli.py stats

Autores:
    Desenvolvido para Mirassol FC
"""

import argparse
import sys
import os
import urllib.parse
from typing import Optional, Any

from calendar_utils import (
    CalendarAuth,
    CalendarManager,
    EventManager,
    ICSManager,
    CALENDAR_ID_FILE,
)


class CalendarCLI:
    """Interface de linha de comando para gerenciar calendários do Mirassol FC.

    Fornece métodos para todos os comandos de gerenciamento de calendários,
    incluindo autenticação lazy que só ocorre quando necessário.

    Attributes:
        service: Serviço Google Calendar API (inicializado sob demanda)
        cal_manager: Gerenciador de calendários
        event_manager: Gerenciador de eventos
    """

    def __init__(self) -> None:
        """Inicializa a CLI com serviço None (será inicializado sob demanda)."""
        self.service: Optional[Any] = None
        self.cal_manager: Optional[CalendarManager] = None
        self.event_manager: Optional[EventManager] = None

    def _initialize(self) -> None:
        """Inicializa o serviço e gerenciadores quando necessários.

        Raises:
            SystemExit: Se a autenticação falhar
        """
        if self.service is None:
            try:
                self.service = CalendarAuth.authenticate()
                self.cal_manager = CalendarManager(self.service)
                self.event_manager = EventManager(self.service)
            except Exception as e:
                print(f"❌ Erro de autenticação: {e}")
                sys.exit(1)

    # ============ COMANDO: LIST ============
    def cmd_list(self, args: argparse.Namespace) -> None:
        """Lista todos os calendários disponíveis.

        Args:
            args: Argumentos da linha de comando
        """
        self._initialize()

        calendars = self.cal_manager.list_calendars()

        if not calendars:
            print("📭 Nenhum calendário encontrado")
            return

        print(f"\n📋 Total de calendários: {len(calendars)}\n")

        for i, cal in enumerate(calendars, 1):
            summary: str = cal.get("summary", "Sem nome")
            cal_id: str = cal["id"]
            owner: bool = cal.get("dataOwner", False)

            owner_badge: str = " 👤 (seu)" if owner else ""
            print(f"{i}. {summary}{owner_badge}")
            print(f"   ID: {cal_id}")

            # Mostra quantidade de eventos
            events = self.event_manager.list_events(cal_id, max_results=1)
            total_events: int = len(events)
            if total_events > 0:
                print(f"   📌 {total_events} evento(s)")

            print()

    # ============ COMANDO: CREATE ============
    def cmd_create(self, args: argparse.Namespace) -> None:
        """Cria um novo calendário.

        Args:
            args: Argumentos contendo nome, descrição e timezone do calendário
        """
        self._initialize()

        name: str = args.name
        description: str = args.description or f"Calendário {name}"
        timezone: str = args.timezone or "America/Sao_Paulo"

        cal_id = self.cal_manager.create_calendar(
            name=name, description=description, timezone=timezone
        )

        if cal_id and args.share_email:
            role: str = args.share_role or "reader"
            self.cal_manager.share_calendar(cal_id, args.share_email, role)

            # Gera link
            calendar_link: str = (
                f"https://calendar.google.com/calendar/u/0?cid={urllib.parse.quote(cal_id)}"
            )
            print(f"\n🔗 Link para adicionar: {calendar_link}")

    # ============ COMANDO: DELETE ============
    def cmd_delete(self, args: argparse.Namespace) -> None:
        """Deleta um calendário com confirmação de segurança.

        Args:
            args: Argumentos contendo ID do calendário e flag force
        """
        self._initialize()

        cal_id: str = args.id

        if not args.force:
            cal_info = self.cal_manager.get_calendar_info(cal_id)
            if not cal_info:
                print("❌ Calendário não encontrado")
                return

            print(f"\n⚠️  Calendário: {cal_info.get('summary', 'Desconhecido')}")
            print(f"📝 ID: {cal_id}")

            confirm: str = input("\n⛔ Confirmar exclusão? (s/n): ").strip().lower()
            if confirm != "s":
                print("❌ Operação cancelada")
                return

        if self.cal_manager.delete_calendar(cal_id):
            # Remove arquivo de ID se existir
            if os.path.exists(CALENDAR_ID_FILE):
                with open(CALENDAR_ID_FILE, "r") as f:
                    saved_id: str = f.read().strip()
                if saved_id == cal_id:
                    os.remove(CALENDAR_ID_FILE)

    # ============ COMANDO: UPDATE ============
    def cmd_update(self, args: argparse.Namespace) -> None:
        """Atualiza calendário com eventos do arquivo .ics.

        Sincroniza eventos do arquivo mirassolfc.ics com o Google Calendar.

        Args:
            args: Argumentos contendo ID do calendário e flags clear/yes
        """
        self._initialize()

        # Obtém ou cria o calendário MirassolFC
        cal_id: str = args.id

        if not cal_id:
            # Usa o método que garante MirassolFC (cria se não existir)
            cal_id = self.cal_manager.get_or_create_mirassol_calendar()

        if not cal_id:
            print("❌ Erro ao obter/criar calendário MirassolFC")
            return

        print(f"\n📅 Calendário: {cal_id}\n")

        # Limpa eventos antigos se solicitado
        if args.clear:
            if getattr(args, "yes", False):
                # Auto-confirm for CI/non-interactive
                self.event_manager.delete_all_events(cal_id)
            else:
                confirm: str = (
                    input("⚠️  Deletar todos os eventos existentes? (s/n): ")
                    .strip()
                    .lower()
                )
                if confirm == "s":
                    self.event_manager.delete_all_events(cal_id)
                else:
                    print("⏭️  Mantendo eventos existentes")

        # Faz upload dos novos eventos
        print("\n📖 Lendo arquivo .ics...")
        try:
            vevents = ICSManager.parse_ics_file()

            print("\n⬆️  Fazendo upload dos eventos...\n")
            successful, failed = self.event_manager.upload_events(cal_id, vevents)

            if args.prune:
                print("\n🧹 Removendo eventos órfãos...\n")
                source_uids = ICSManager.source_uids(vevents)
                self.event_manager.prune_orphaned_events(cal_id, source_uids)

            print(f"\n{'='*60}")
            print(f"✨ Sincronização concluída!")
            print(f"{'='*60}\n")

        except FileNotFoundError as e:
            print(f"❌ {e}")

    # ============ COMANDO: SHARE ============
    def cmd_share(self, args: argparse.Namespace) -> None:
        """Compartilha calendário com um email.

        Args:
            args: Argumentos contendo email, ID do calendário e role
        """
        self._initialize()

        cal_id: str = args.id
        if not cal_id:
            # Se não informar ID, usa MirassolFC
            cal_id = self.cal_manager.get_or_create_mirassol_calendar()

        email: str = args.email
        role: str = args.role or "reader"

        if not self.cal_manager.get_calendar_info(cal_id):
            print("❌ Calendário não encontrado")
            return

        self.cal_manager.make_calendar_public(cal_id)
        links = self.cal_manager.get_public_calendar_links(cal_id)
        print(
            f"\n🔗 Links públicos para o calendário:"
            f"\n  HTML: {links.get('html', '-')}"
            f"\n  iCal: {links.get('ical', '-')}"
            f"\n  XML: {links.get('xml', '-')}"
        )

        if self.cal_manager.share_calendar(cal_id, email, role):
            # Gera link
            calendar_link: str = (
                f"https://calendar.google.com/calendar/u/0?cid={urllib.parse.quote(cal_id)}"
            )
            print(f"\n🔗 Link para importar: {calendar_link}")

    # ============ COMANDO: INFO ============
    def cmd_info(self, args: argparse.Namespace) -> None:
        """Mostra informações detalhadas de um calendário.

        Args:
            args: Argumentos contendo ID do calendário e flag show_events
        """
        self._initialize()

        cal_id: str = args.id
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

    # ============ COMANDO: STATS ============
    def cmd_stats(self, args: argparse.Namespace) -> None:
        """Mostra estatísticas de uso do calendário.

        Exibe informações sobre quantas pessoas estão usando o calendário,
        incluindo usuários diretos, grupos e acesso público.

        Args:
            args: Argumentos contendo ID do calendário (opcional)
        """
        self._initialize()

        cal_id: str = args.id
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

        users_info = self.cal_manager.get_calendar_users(cal_id)

        print(f"\n{'='*60}")
        print(f"📊 Estatísticas de Uso - {cal_info.get('summary', 'Sem nome')}")
        print(f"{'='*60}")
        print(f"\n👥 Usuários diretos: {users_info['total_users']}")
        print(f"👨‍💼 Grupos: {users_info['total_groups']}")
        print(f"🏢 Domínios: {users_info['total_domains']}")
        print(f"🌐 Acesso público: {'Sim' if users_info['public_access'] else 'Não'}")
        print(f"\n📈 Total de entradas de acesso: {users_info['total_entries']}")
        print(f"{'='*60}\n")



def main() -> None:
    """Função principal que configura argparse e executa comandos.

    Configura o parser de argumentos com todos os subcomandos disponíveis
    e executa o comando especificado pelo usuário.

    Raises:
        KeyboardInterrupt: Se o usuário cancelar a operação (Ctrl+C)
        Exception: Para outros erros durante execução
    """
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
  python calendar_cli.py stats                         # Ver estatísticas
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    # ============ SUBCOMMAND: LIST ============
    list_parser = subparsers.add_parser("list", help="Listar todos os calendários")
    list_parser.set_defaults(func=lambda args: cli.cmd_list(args))

    # ============ SUBCOMMAND: CREATE ============
    create_parser = subparsers.add_parser("create", help="Criar novo calendário")
    create_parser.add_argument("name", help="Nome do calendário")
    create_parser.add_argument("-d", "--description", help="Descrição do calendário")
    create_parser.add_argument(
        "-z",
        "--timezone",
        default="America/Sao_Paulo",
        help="Timezone (padrão: America/Sao_Paulo)",
    )
    create_parser.add_argument("-s", "--share-email", help="Email para compartilhar")
    create_parser.add_argument(
        "-r",
        "--share-role",
        choices=["reader", "writer", "owner"],
        help="Tipo de permissão",
    )
    create_parser.set_defaults(func=lambda args: cli.cmd_create(args))

    # ============ SUBCOMMAND: DELETE ============
    delete_parser = subparsers.add_parser("delete", help="Deletar calendário")
    delete_parser.add_argument("id", help="ID do calendário")
    delete_parser.add_argument(
        "-f", "--force", action="store_true", help="Não pedir confirmação"
    )
    delete_parser.set_defaults(func=lambda args: cli.cmd_delete(args))

    # ============ SUBCOMMAND: UPDATE ============
    update_parser = subparsers.add_parser(
        "update", help="Atualizar calendário com eventos do .ics"
    )
    update_parser.add_argument(
        "-id", "--id", help="ID do calendário (opcional, usa MirassolFC por padrão)"
    )
    update_parser.add_argument(
        "-c",
        "--clear",
        action="store_true",
        help="Deletar eventos antigos antes de adicionar",
    )
    update_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Confirmar automaticamente deleção de eventos (não interativo)",
    )
    update_parser.add_argument(
        "--prune",
        action="store_true",
        help="Remover eventos gerenciados que não existem mais no .ics",
    )
    update_parser.set_defaults(func=lambda args: cli.cmd_update(args))

    # ============ SUBCOMMAND: SHARE ============
    share_parser = subparsers.add_parser("share", help="Compartilhar calendário")
    share_parser.add_argument("email", help="Email para compartilhar")
    share_parser.add_argument(
        "id",
        nargs="?",
        help="ID do calendário (opcional, usa MirassolFC se não fornecido)",
    )
    share_parser.add_argument(
        "-r",
        "--role",
        choices=["reader", "writer", "owner"],
        help="Tipo de permissão (padrão: reader)",
    )
    share_parser.set_defaults(func=lambda args: cli.cmd_share(args))

    # ============ SUBCOMMAND: INFO ============
    info_parser = subparsers.add_parser("info", help="Informações de um calendário")
    info_parser.add_argument("id", nargs="?", help="ID do calendário (opcional)")
    info_parser.add_argument(
        "-e", "--show-events", action="store_true", help="Mostrar lista de eventos"
    )
    info_parser.set_defaults(func=lambda args: cli.cmd_info(args))

    # ============ SUBCOMMAND: STATS ============
    stats_parser = subparsers.add_parser("stats", help="Estatísticas de uso do calendário")
    stats_parser.add_argument("id", nargs="?", help="ID do calendário (opcional)")
    stats_parser.set_defaults(func=lambda args: cli.cmd_stats(args))

    # Parse argumentos
    args = parser.parse_args()

    # Executa comando
    if hasattr(args, "func"):
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


if __name__ == "__main__":
    """Ponto de entrada principal do script.

    Cria uma instância da CLI e executa o programa.
    """
    cli: CalendarCLI = CalendarCLI()
    main()
