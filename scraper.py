#!/usr/bin/env python3
"""Scraper via API para sincronizar jogos do Mirassol FC com Google Calendar.

Este módulo extrai dados de jogos do Mirassol FC da API pública da ESPN e gera
um arquivo iCalendar (.ics) que pode ser importado no Google Calendar. Inclui
suporte a resultados já realizados e jogos agendados.

Uso:
    python scraper.py

Exemplo:
    >>> scraper = MirassolScraper()
    >>> scraper.run()
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
from datetime import datetime, timedelta
import time
import hashlib
from typing import List, Optional, Dict, Any, Set
from zoneinfo import ZoneInfo

HEADERS: Dict[str, str] = {
    "Referer": "https://www.espn.com.br/",
    "User-Agent": "calendario-mirassolfc/1.0",
}

ESPN_TEAM_ID = "9169"
ESPN_DEFAULT_LEAGUES = (
    "bra.1",
    "bra.copa_do_brazil",
    "conmebol.libertadores",
    "bra.camp.paulista",
)
ESPN_REGION = "br"
ESPN_LANGUAGE = "pt"
SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")


class MirassolScraper:
    """Scraper para extrair dados de jogos do Mirassol FC da ESPN.

    Esta classe gerencia a coleta de dados da API JSON da ESPN e a geração do
    arquivo iCalendar.
    """

    def __init__(self) -> None:
        """Inicializa o scraper com sessão HTTP configurada."""
        self.session: requests.Session = requests.Session()
        self.session.headers.update(HEADERS)
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.games: List[Dict[str, Any]] = []

    def fetch_json(self, url: str) -> Dict[str, Any]:
        """Recupera JSON da API pública da ESPN com retry simples."""
        last_error = "nenhuma resposta recebida"
        headers = {
            "Accept": "application/json",
            "User-Agent": HEADERS["User-Agent"],
            "Referer": "https://www.espn.com.br/futebol/",
        }

        for attempt in range(3):
            try:
                response = self.session.get(url, timeout=20, headers=headers)
                content_type = response.headers.get("content-type", "")
                response.raise_for_status()

                if self._is_waf_blocked(response.text):
                    last_error = (
                        f"WAF detectado em JSON {url} "
                        f"(status={response.status_code}, content-type={content_type})"
                    )
                    print(f"  ⚠️  {last_error}")
                    continue

                return response.json()
            except Exception as e:
                last_error = str(e)
                print(f"  Erro JSON tentativa {attempt + 1}/3: {last_error[:140]}")
                if attempt < 2:
                    time.sleep(1 + attempt)

        raise requests.exceptions.RequestException(
            f"Falha ao recuperar JSON: {url}. Último erro: {last_error}"
        )

    def _is_waf_blocked(self, html: str) -> bool:
        """Verifica se a resposta indica bloqueio do AWS WAF."""
        waf_indicators = [
            "awsWafCookieDomainList",
            "AwsWafIntegration",
            "Verify you are a human",
            "JavaScript is disabled",
            "window.location.reload",
        ]
        return any(indicator in html for indicator in waf_indicators)

    def scrape_json_api(self, year: Optional[int] = None) -> None:
        """Scrapa jogos pela API JSON da ESPN, evitando o HTML protegido por WAF."""
        season_year = year or datetime.now(SAO_PAULO_TZ).year
        print(f"Buscando jogos pela ESPN JSON API ({season_year})")

        seen_event_ids: Set[str] = set()
        for league in ESPN_DEFAULT_LEAGUES:
            events_url = (
                "https://sports.core.api.espn.com/v2/sports/soccer/"
                f"leagues/{league}/seasons/{season_year}/teams/{ESPN_TEAM_ID}/events"
                f"?lang={ESPN_LANGUAGE}&region={ESPN_REGION}&limit=100"
            )
            print(f"  Liga {league}: buscando lista de eventos")
            data = self.fetch_json(events_url)
            items = data.get("items", [])
            print(f"    {len(items)} referência(s) encontrada(s)")

            for item in items:
                event_id = self._extract_event_id(item)
                if not event_id:
                    print(f"    ⚠️  Evento sem ID ignorado: {item}")
                    continue
                if event_id in seen_event_ids:
                    print(f"    ↪ Evento {event_id} duplicado ignorado")
                    continue

                summary_url = (
                    "https://site.api.espn.com/apis/site/v2/sports/soccer/"
                    f"{league}/summary?event={event_id}"
                    f"&region={ESPN_REGION}&lang={ESPN_LANGUAGE}"
                )
                summary = self.fetch_json(summary_url)
                game = self.parse_json_event(summary, event_id=event_id)
                if not game:
                    print(f"    ⚠️  Evento {event_id} sem dados suficientes")
                    continue

                seen_event_ids.add(event_id)
                self.games.append(game)
                self._print_json_game(game, event_id)

    def _extract_event_id(self, item: Dict[str, Any]) -> Optional[str]:
        """Extrai o ID do evento de uma referência Core da ESPN."""
        if item.get("id"):
            return str(item["id"])

        ref = item.get("$ref", "")
        match = re.search(r"/events/([^/?]+)", ref)
        return match.group(1) if match else None

    def parse_json_event(
        self, payload: Dict[str, Any], event_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Converte um resumo JSON da ESPN para o formato interno de jogo."""
        header = payload.get("header") or {}
        competitions = header.get("competitions") or []
        if not competitions:
            return None

        competition = competitions[0]
        competitors = competition.get("competitors") or []
        home = self._find_competitor(competitors, "home")
        away = self._find_competitor(competitors, "away")
        if not home or not away:
            return None

        date_text = competition.get("date") or header.get("date")
        local_datetime = self._parse_espn_datetime(date_text)
        if not local_datetime:
            return None
        event_date = local_datetime.replace(hour=0, minute=0, second=0, microsecond=0)

        status_type = (
            (competition.get("status") or {}).get("type")
            or (header.get("status") or {}).get("type")
            or {}
        )
        completed = bool(status_type.get("completed"))
        status_detail = " ".join(
            str(status_type.get(key) or "")
            for key in ("description", "detail", "shortDetail")
        )
        time_valid_values = [
            value
            for value in (competition.get("timeValid"), header.get("timeValid"))
            if value is not None
        ]
        time_invalid = any(value is False for value in time_valid_values)
        all_day = completed or time_invalid or "definir" in status_detail.lower()

        championship = self._normalise_championship(
            (header.get("league") or {}).get("name")
            or (payload.get("league") or {}).get("name")
            or ""
        )

        game: Dict[str, Any] = {
            "date": event_date,
            "team1": self._team_name(home),
            "team2": self._team_name(away),
            "championship": championship,
            "status": "finished" if completed else "scheduled",
            "all_day": all_day,
            "event_id": event_id,
        }

        if completed:
            home_score = self._score_value(home)
            away_score = self._score_value(away)
            if home_score is None or away_score is None:
                return None
            game["score"] = f"{home_score} - {away_score}"
        else:
            game["score"] = None
            game["time"] = "00:00" if all_day else local_datetime.strftime("%H:%M")

        return game

    def _find_competitor(
        self, competitors: List[Dict[str, Any]], home_away: str
    ) -> Optional[Dict[str, Any]]:
        for competitor in competitors:
            if competitor.get("homeAway") == home_away:
                return competitor
        return None

    def _team_name(self, competitor: Dict[str, Any]) -> str:
        team = competitor.get("team") or {}
        return team.get("displayName") or team.get("name") or ""

    def _score_value(self, competitor: Dict[str, Any]) -> Optional[str]:
        score = competitor.get("score")
        if score is None:
            return None
        return str(score)

    def _parse_espn_datetime(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.astimezone(SAO_PAULO_TZ).replace(tzinfo=None)
        except ValueError:
            return None

    def _normalise_championship(self, championship: str) -> str:
        return re.sub(r"^\d{4}\s+", "", championship).strip()

    def _print_json_game(self, game: Dict[str, Any], event_id: str) -> None:
        if game["status"] == "finished":
            print(
                f"    ✓ {event_id}: {game['team1']} {game['score']} "
                f"{game['team2']} ({game['championship']})"
            )
            return

        time_display = "A definir" if game.get("all_day") else game.get("time")
        print(
            f"    ✓ {event_id}: {game['team1']} x {game['team2']} "
            f"({game['championship']} - {time_display})"
        )

    def sort_games_for_ics(self) -> None:
        """Mantém ordem estável: resultados recentes primeiro, agenda em seguida."""
        self.games.sort(
            key=lambda game: (
                0 if game.get("status") == "finished" else 1,
                -game["date"].timestamp()
                if game.get("status") == "finished"
                else game["date"].timestamp(),
                game.get("team1", ""),
                game.get("team2", ""),
            )
        )

    def load_existing_events(
        self, ics_file: str = "mirassolfc.ics"
    ) -> Dict[str, Dict[str, str]]:
        """Carrega eventos existentes do arquivo .ics para preservar timestamps.

        Args:
            ics_file: Caminho do arquivo .ics

        Returns:
            Dicionário mapeando UID para dados do evento (summary, description, dtstamp)
        """
        existing_events = {}
        try:
            with open(ics_file, "r", encoding="utf-8") as f:
                content = f.read()
                # Extrai eventos
                events = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", content, re.DOTALL)
                for event in events:
                    # Extrai UID
                    uid_match = re.search(r"UID:([^\n]+)", event)
                    summary_match = re.search(r"SUMMARY:([^\n]+)", event)
                    description_match = re.search(r"DESCRIPTION:([^\n]+)", event)
                    dtstamp_match = re.search(r"DTSTAMP:([^\n]+)", event)

                    if uid_match:
                        uid = uid_match.group(1).strip()
                        existing_events[uid] = {
                            "summary": (
                                summary_match.group(1).strip() if summary_match else ""
                            ),
                            "description": (
                                description_match.group(1).strip()
                                if description_match
                                else ""
                            ),
                            "dtstamp": (
                                dtstamp_match.group(1).strip()
                                if dtstamp_match
                                else None
                            ),
                        }
        except FileNotFoundError:
            pass
        return existing_events

    def generate_ics(self, output_file: str = "mirassolfc.ics") -> str:
        """Gera arquivo iCalendar (.ics) com todos os jogos.

        Cria um arquivo iCalendar com eventos de todos os jogos, preservando
        timestamps de eventos que não foram alterados. Inclui suporte a fuso
        horário Brasil.

        Args:
            output_file: Caminho do arquivo .ics a gerar

        Returns:
            Caminho do arquivo gerado

        Raises:
            IOError: Se não conseguir escrever o arquivo
        """
        print(f"\nGerando arquivo iCalendar: {output_file}")

        # Carrega eventos existentes para preservar timestamps
        existing_events = self.load_existing_events(output_file)
        current_time = datetime.now().strftime("%Y%m%dT%H%M%SZ")

        # Cabeçalho iCalendar
        ics_content = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Mirassol FC Games//PT",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:Mirassol FC - Jogos",
            "X-WR-TIMEZONE:America/Sao_Paulo",
            "BEGIN:VTIMEZONE",
            "TZID:America/Sao_Paulo",
            "BEGIN:DAYLIGHT",
            "TZOFFSETFROM:-0300",
            "TZOFFSETTO:-0200",
            "TZNAME:BRST",
            "DTSTART:20231015T000000",
            "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=3SU",
            "END:DAYLIGHT",
            "BEGIN:STANDARD",
            "TZOFFSETFROM:-0200",
            "TZOFFSETTO:-0300",
            "TZNAME:BRT",
            "DTSTART:20240218T000000",
            "RRULE:FREQ=YEARLY;BYMONTH=2;BYDAY=3SU",
            "END:STANDARD",
            "END:VTIMEZONE",
        ]

        changes_detected = 0

        # Eventos
        for game in self.games:
            # Usa o ID estável da ESPN quando disponível. Datas e horários mudam
            # com frequência; se entrarem no UID, o Google Calendar fica com
            # eventos antigos órfãos após remarcações.
            event_id = self._stable_event_uid(game)
            uid = f"{event_id}@mirassol.local"

            # Verifica se é evento de dia inteiro (horário indefinido)
            all_day = game.get("all_day", False)

            if all_day:
                # Evento de dia inteiro: usa formato DATE (sem hora)
                dt_start_str = game["date"].strftime("%Y%m%d")
                # Para eventos de dia inteiro no iCalendar, DTEND é o dia seguinte
                dt_end_date = game["date"] + timedelta(days=1)
                dt_end_str = dt_end_date.strftime("%Y%m%d")
            else:
                # Evento com horário definido
                time_parts = game["time"].split(":")
                hour = time_parts[0] if time_parts else "18"
                minute = time_parts[1] if len(time_parts) > 1 else "00"
                dt_start = game["date"].replace(hour=int(hour), minute=int(minute))
                dt_start_str = dt_start.strftime("%Y%m%dT%H%M%S")
                dt_end = dt_start + timedelta(hours=2)  # Assume 2 horas de duração
                dt_end_str = dt_end.strftime("%Y%m%dT%H%M%S")

            # Descrição do evento
            if game["status"] == "finished":
                description = (
                    f"Resultado: {game['team1']} {game['score']} {game['team2']}"
                )
                # Incluir campeonato se disponível; caso contrário mostrar 'Finalizado'
                if game.get("championship"):
                    summary = f"{game['team1']} {game['score']} {game['team2']} - {game['championship']}"
                else:
                    summary = (
                        f"{game['team1']} {game['score']} {game['team2']} - Finalizado"
                    )
            else:
                description = f"{game['championship']} - Jogo agendado"
                summary = f"{game['team1']} x {game['team2']} - {game['championship']}"

            # Verifica se o evento já existe e se mudou
            dtstamp = current_time
            if uid in existing_events:
                old_event = existing_events[uid]
                # Se resumo e descrição são iguais, preserva o DTSTAMP antigo
                if (
                    old_event["summary"] == summary
                    and old_event["description"] == description
                ):
                    dtstamp = old_event["dtstamp"]
                else:
                    changes_detected += 1
            else:
                changes_detected += 1

            if all_day:
                event = [
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTAMP:{dtstamp}",
                    f"DTSTART;VALUE=DATE:{dt_start_str}",
                    f"DTEND;VALUE=DATE:{dt_end_str}",
                    f"SUMMARY:{summary}",
                    f"DESCRIPTION:{description}",
                    "STATUS:CONFIRMED",
                    "END:VEVENT",
                ]
            else:
                event = [
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTAMP:{dtstamp}",
                    f"DTSTART;TZID=America/Sao_Paulo:{dt_start_str}",
                    f"DTEND;TZID=America/Sao_Paulo:{dt_end_str}",
                    f"SUMMARY:{summary}",
                    f"DESCRIPTION:{description}",
                    "STATUS:CONFIRMED",
                    "END:VEVENT",
                ]

            ics_content.extend(event)

        # Rodapé
        ics_content.append("END:VCALENDAR")

        # Salva arquivo
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(ics_content))

        print(f"✓ Arquivo '{output_file}' gerado com {len(self.games)} jogos!")
        if changes_detected > 0:
            print(f"  ℹ️  {changes_detected} evento(s) novo(s) ou alterado(s)")
        else:
            print(f"  ℹ️  Nenhuma alteração necessária nos eventos")
        return output_file

    def _stable_event_uid(self, game: Dict[str, Any]) -> str:
        """Gera UID estável para reconciliação com Google Calendar."""
        espn_event_id = str(game.get("event_id") or "").strip()
        if espn_event_id:
            return f"espn-{espn_event_id}"

        fallback_key = (
            f"{game.get('team1', '')}|{game.get('team2', '')}|"
            f"{game.get('championship', '')}"
        )
        return hashlib.md5(fallback_key.encode()).hexdigest()

    def run(self) -> None:
        """Executa coleta pela API da ESPN e gera arquivo iCalendar.

        Executa todas as etapas da API JSON e gera o arquivo .ics. Exibe
        sumário do progresso durante execução.

        Raises:
            Exception: Se ocorrer erro crítico durante scraping
        """
        try:
            print("=" * 60)
            print("Mirassol FC - ESPN API Scraper")
            print("=" * 60)

            self.scrape_json_api()
            self.sort_games_for_ics()
            print(f"\nTotal de jogos encontrados: {len(self.games)}")
            self.generate_ics()

            print("\n" + "=" * 60)
            print("✓ Scraping concluído com sucesso!")
            print("=" * 60)

        except Exception as e:
            print(f"\n✗ Erro durante execução: {e}")
            raise


if __name__ == "__main__":
    """Ponto de entrada principal do script.

    Cria uma instância do scraper e executa o processo completo
    de coleta de dados.
    """
    scraper: MirassolScraper = MirassolScraper()
    scraper.run()
