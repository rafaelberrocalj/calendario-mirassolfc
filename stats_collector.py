#!/usr/bin/env python3
"""Script para coletar estatísticas de uso do calendário e atualizar o README.

Este script coleta dados sobre quantas pessoas estão utilizando o calendário
do Mirassol FC e atualiza o README com essas informações diariamente.

Uso:
    python stats_collector.py
"""

import os
import re
from datetime import datetime
from calendar_utils import CalendarAuth, CalendarManager


def update_readme_stats(users_info: dict) -> None:
    """Atualiza o README com estatísticas de uso.

    Args:
        users_info: Dicionário com informações de usuários do calendário
    """
    readme_path = "README.md"

    if not os.path.exists(readme_path):
        print(f"❌ Arquivo {readme_path} não encontrado!")
        return

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Cria o bloco de estatísticas
    timestamp = datetime.now().strftime("%d/%m/%Y às %H:%M")
    stats_block = f"""## 📊 Estatísticas de Uso

Última atualização: **{timestamp}** (Brasília)

- 👥 **Usuários diretos:** {users_info['total_users']}
- 👨‍💼 **Grupos:** {users_info['total_groups']}
- 🏢 **Domínios:** {users_info['total_domains']}
- 🌐 **Acesso público:** {'Sim ✅' if users_info['public_access'] else 'Não ❌'}
- 📈 **Total de entradas de acesso:** {users_info['total_entries']}

---"""

    # Remove qualquer bloco de estatísticas existente para evitar duplicação.
    # Az abordagem anterior só removia o primeiro bloco, deixando um segundo
    # antigo cair para trás; aqui removemos **todos** os blocos já existentes
    # antes de fazer qualquer inserção.
    remove_pattern = r"## 📊 Estatísticas de Uso[\s\S]*?---\n"
    content = re.sub(remove_pattern, "", content, flags=re.DOTALL)

    # Agora que não existem blocos, localizamos o separador que termina a
    # seção "Como Funciona a Automação" e inserimos o novo bloco imediatamente
    # após ele (mantendo a ordem original do README).
    sep_pattern = r"(## ⚙️ Como Funciona a Automação[\s\S]*?\n---\n)"
    if re.search(sep_pattern, content):
        content = re.sub(
            sep_pattern,
            r"\1" + stats_block + "\n",
            content,
            count=1,
        )
        print("✅ Estatísticas inseridas/atualizadas no README")
    else:
        # Se não encontrar o ponto esperado, colocamos o bloco no final como
        # fallback; isso garante que não haverá duplicações mesmo em casos
        # de formatação inesperada.
        content = content.strip() + "\n\n" + stats_block + "\n"
        print(
            "⚠️ Seção de automação não encontrada; estatísticas adicionadas ao fim do README"
        )

    # Salva o arquivo atualizado
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> None:
    """Função principal que coleta estatísticas e atualiza o README."""
    try:
        print("=" * 60)
        print("Coletor de Estatísticas - Mirassol FC")
        print("=" * 60)

        # Autentica e obtém o serviço
        service = CalendarAuth.authenticate()
        cal_manager = CalendarManager(service)

        # Obtém ou cria o calendário MirassolFC
        cal_id = cal_manager.get_or_create_mirassol_calendar()

        if not cal_id:
            print("❌ Erro ao obter/criar calendário MirassolFC")
            return

        # Coleta estatísticas de usuários
        print("\n📊 Coletando estatísticas...")
        users_info = cal_manager.get_calendar_users(cal_id)

        print(f"\n✅ Dados coletados:")
        print(f"   👥 Usuários diretos: {users_info['total_users']}")
        print(f"   👨‍💼 Grupos: {users_info['total_groups']}")
        print(f"   🏢 Domínios: {users_info['total_domains']}")
        print(
            f"   🌐 Acesso público: {'Sim' if users_info['public_access'] else 'Não'}"
        )
        print(f"   📈 Total de entradas: {users_info['total_entries']}")

        # Atualiza o README
        print("\n📝 Atualizando README...")
        update_readme_stats(users_info)

        print("\n" + "=" * 60)
        print("✓ Coleta de estatísticas concluída com sucesso!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Erro durante execução: {e}")
        raise


if __name__ == "__main__":
    """Ponto de entrada principal do script."""
    main()
