#!/usr/bin/env python3
"""Web scraper para sincronizar jogos do Mirassol FC com Google Calendar.

Este módulo extrai dados de jogos do Mirassol FC do site ESPN e gera um arquivo
iCalendar (.ics) que pode ser importado no Google Calendar. Inclui suporte a
tanto resultados já realizados quanto jogos agendados.

Uso:
    python scraper.py

Atributos:
    HEADERS (dict): Headers HTTP para contornar proteção anti-bot do ESPN.

Exemplo:
    >>> scraper = MirassolScraper()
    >>> scraper.run()
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import time
import hashlib
import random
from typing import List, Optional, Dict, Any, Set
from zoneinfo import ZoneInfo

try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False

# Headers sofisticados para contornar proteção anti-bot do ESPN
# Simula um navegador moderno com comportamento realista
HEADERS: Dict[str, str] = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://www.espn.com.br/",
    "Sec-CH-UA": '"Not_A Brand";v="8", "Chromium";v="123", "Google Chrome";v="123"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
    "DNT": "1",
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
    """Scraper para extrair dados de jogos do Mirassol FC do ESPN.

    Esta classe gerencia o scraping de dados do ESPN, incluindo resultados
    e calendário de jogos do Mirassol FC, com suporte a geração de arquivo iCalendar.
    """

    def __init__(self) -> None:
        """Inicializa o scraper com sessão HTTP configurada.
        
        Configura retry strategy e headers sofisticados para contornar WAF.
        Usa cloudscraper como fallback se disponível.
        """
        self.session: requests.Session = requests.Session()
        self.session.headers.update(HEADERS)
        
        # Configurar retry strategy com backoff exponencial
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # Simular navegador com cookies e comportamento realista
        self.session.headers.update({
            "Referer": "https://www.espn.com.br/futebol/",
        })
        
        # Inicializar cloudscraper se disponível
        self.cloudscraper_session = None
        if CLOUDSCRAPER_AVAILABLE:
            try:
                self.cloudscraper_session = cloudscraper.create_scraper()
                print("  ✓ Cloudscraper inicializado para bypass de WAF")
            except Exception as e:
                print(f"  ⚠️  Falha ao inicializar cloudscraper: {e}")
        
        self.games: List[Dict[str, Any]] = []

    def fetch_page(self, url: str) -> str:
        """Recupera página com retry automático, delay variável e WAF bypass avançado.
        
        Tenta primeiro com requests normal, e se detectar WAF, tenta com cloudscraper.

        Args:
            url: URL da página a recuperar

        Returns:
            Conteúdo HTML da página

        Raises:
            requests.exceptions.RequestException: Se todas as tentativas falharem
        """
        max_retries_requests: int = 3
        max_retries_cloudscraper: int = 3
        last_error = "nenhuma resposta recebida"
        
        # Fase 1: Tentar com requests normal
        print(f"Tentando com requests normal...")
        for attempt in range(max_retries_requests):
            try:
                # Delay variável e mais longo entre requisições para parecer natural
                delay = random.uniform(2, 4) if attempt == 0 else random.uniform(5, 10)
                print(f"  Tentativa {attempt + 1}/{max_retries_requests}... aguardando {delay:.1f}s")
                time.sleep(delay)
                
                # Headers dinâmicos por requisição
                request_headers = self.session.headers.copy()
                request_headers.update({
                    "Referer": self._get_referer(url),
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                })
                
                response: requests.Response = self.session.get(
                    url,
                    timeout=20,
                    headers=request_headers,
                    allow_redirects=True,
                    verify=True
                )
                response.raise_for_status()
                
                # Verificar se AWS WAF bloqueou
                if self._is_waf_blocked(response.text):
                    last_error = (
                        f"WAF detectado em {url} "
                        f"(status={response.status_code}, tamanho={len(response.text)})"
                    )
                    print(f"  ⚠️  {last_error}")
                    if attempt == max_retries_requests - 1:
                        print(f"  → Tentaremos com cloudscraper...")
                    continue
                
                print(f"  ✓ HTML recuperado com sucesso (requests)")
                return response.text
                
            except requests.exceptions.RequestException as e:
                last_error = e
                print(f"  Erro: {str(e)[:100]}")
        
        # Fase 2: Se requests falhou, tentar com cloudscraper
        if self.cloudscraper_session:
            print(f"\nTentando com cloudscraper (bypass WAF)...")
            for attempt in range(max_retries_cloudscraper):
                try:
                    delay = random.uniform(3, 6)
                    print(f"  Tentativa {attempt + 1}/{max_retries_cloudscraper}... aguardando {delay:.1f}s")
                    time.sleep(delay)
                    
                    response = self.cloudscraper_session.get(
                        url,
                        timeout=30,
                        headers={"Referer": self._get_referer(url)},
                        allow_redirects=True
                    )
                    response.raise_for_status()
                    
                    # Verificar se ainda há WAF
                    if self._is_waf_blocked(response.text):
                        last_error = (
                            f"WAF ainda detectado em {url} "
                            f"(status={response.status_code}, tamanho={len(response.text)})"
                        )
                        print(f"  ⚠️  {last_error}")
                        if attempt < max_retries_cloudscraper - 1:
                            time.sleep(random.uniform(10, 20))
                        continue
                    
                    print(f"  ✓ HTML recuperado com sucesso (cloudscraper)")
                    return response.text
                    
                except Exception as e:
                    print(f"  Erro: {str(e)[:100]}")
                    last_error = e
        else:
            print(f"\n⚠️  Cloudscraper não disponível")
        
        # Levantou exceção após todas as tentativas
        raise requests.exceptions.RequestException(
            f"Falha ao recuperar página após todas as tentativas. Último erro: {last_error}"
        )

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
        """Verifica se a resposta indica bloqueio do AWS WAF.
        
        Args:
            html: Conteúdo HTML da resposta
            
        Returns:
            True se WAF bloqueou, False caso contrário
        """
        waf_indicators = [
            "awsWafCookieDomainList",
            "AwsWafIntegration",
            "Verify you are a human",
            "JavaScript is disabled",
            "window.location.reload",
        ]
        return any(indicator in html for indicator in waf_indicators)

    def _get_referer(self, url: str) -> str:
        """Retorna referer apropriado baseado na URL.
        
        Args:
            url: URL sendo acessada
            
        Returns:
            Referer apropriado para a requisição
        """
        if "calendario" in url:
            return "https://www.espn.com.br/futebol/"
        elif "resultados" in url:
            return "https://www.espn.com.br/futebol/"
        return "https://www.espn.com.br/"

    def parse_date(self, date_str: str) -> Optional[datetime]:
        """Analisa data no formato português para datetime.

        Suporta formatos como 'dom., 8 fev.' ou 'qua., 11 fev.' e converte
        para um objeto datetime. Se o ano não for especificado, assume 2026.

        Args:
            date_str: String de data em português para analisar

        Returns:
            Objeto datetime ou None se não conseguir analisar a data

        Exemplo:
            >>> scraper = MirassolScraper()
            >>> result = scraper.parse_date('dom., 8 fev.')
            >>> result.day
            8
        """
        # Remove o dia da semana
        date_str = re.sub(r"^[a-z]+\.,\s*", "", date_str, flags=re.IGNORECASE).strip()

        # Mapa de meses em português para números
        month_map: Dict[str, int] = {
            "jan": 1,
            "janeiro": 1,
            "fev": 2,
            "fevereiro": 2,
            "mar": 3,
            "março": 3,
            "abr": 4,
            "abril": 4,
            "mai": 5,
            "maio": 5,
            "jun": 6,
            "junho": 6,
            "jul": 7,
            "julho": 7,
            "ago": 8,
            "agosto": 8,
            "set": 9,
            "setembro": 9,
            "out": 10,
            "outubro": 10,
            "nov": 11,
            "novembro": 11,
            "dez": 12,
            "dezembro": 12,
        }

        try:
            # Extrai dia e mês usando regex
            match = re.search(r"(\d+)\s+([a-zç]+)", date_str, re.IGNORECASE)
            if not match:
                return None

            day = int(match.group(1))
            month_str = match.group(2).lower()

            # Encontra mês correspondente
            month_num = None
            for abbr, num in month_map.items():
                if month_str.startswith(abbr):
                    month_num = num
                    break

            if not month_num:
                return None

            # Extrai ano se disponível, senão usa 2026
            year_match = re.search(r"(\d{4})", date_str)
            year = int(year_match.group(1)) if year_match else 2026

            date_obj = datetime(year, month_num, day)
            return date_obj

        except Exception as e:
            print(f"Erro ao parse da data '{date_str}': {e}")
            return None

    def parse_time(self, time_str: str) -> tuple:
        """Analisa hora em formato 'HH:MM' ou detecta horário indefinido.

        Args:
            time_str: String de hora, ex: '18:30' ou 'A definir'

        Returns:
            Tupla (hora_str, all_day) onde all_day=True indica evento de dia inteiro
        """
        time_str = time_str.strip()
        if "definir" in time_str.lower() or not time_str:
            return ("00:00", True)  # Evento de dia inteiro
        try:
            return (time_str, False)
        except Exception:
            return ("00:00", True)

    def parse_score(self, score_str: str) -> Optional[str]:
        """Analisa placar no formato 'X - Y'.

        Args:
            score_str: String de placar, ex: '2 - 2'

        Returns:
            Placar formatado ou None se não houver placar válido

        Exemplo:
            >>> scraper = MirassolScraper()
            >>> scraper.parse_score('2 - 2')
            '2 - 2'
            >>> scraper.parse_score('') is None
            True
        """
        score_str = score_str.strip()
        if not score_str or "-" not in score_str:
            return None
        try:
            parts: List[str] = score_str.split("-")
            return f"{parts[0].strip()} - {parts[1].strip()}"
        except Exception:
            return None

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

    def scrape_html_fallback(self) -> None:
        """Executa o scraping HTML antigo como fallback explícito."""
        print("ESPN JSON API falhou; tentando fallback HTML legado.")
        self.scrape_results()
        print()
        self.scrape_calendar()

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

    def scrape_results(self) -> None:
        """Scrapa resultados já realizados de jogos do Mirassol FC.

        Acessa a página de resultados do ESPN e extrai informações como
        datas, times, placares e campeonatos.
        """
        url = "https://www.espn.com.br/futebol/time/resultados/_/id/9169/bra.mirassol"
        print(f"Buscando resultados de: {url}")

        html = self.fetch_page(url)
        soup = BeautifulSoup(html, "html.parser")

        # Encontra todas as linhas de resultados
        rows = soup.find_all("tr")

        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 5:
                try:
                    date_str = cols[0].get_text(strip=True)
                    team1 = cols[1].get_text(strip=True)
                    score = cols[2].get_text(strip=True)
                    team2 = cols[3].get_text(strip=True)
                    championship = cols[4].get_text(strip=True) if len(cols) > 4 else ""
                    # Heurística: às vezes a coluna contém o status (ex: 'Finalizado')
                    # e o campeonato real está na coluna seguinte. Detectar palavras
                    # de status e tentar obter o campeonato em cols[5].
                    status_words = (
                        "finalizado",
                        "final",
                        "encerrado",
                        "terminado",
                        "concluído",
                        "concluido",
                        "ft",
                    )
                    if (
                        championship
                        and championship.strip().lower() in status_words
                        and len(cols) > 5
                    ):
                        alt = cols[5].get_text(strip=True)
                        if alt and alt.strip().lower() not in status_words:
                            championship = alt
                    # Se ainda for só um status, limpar para não aparecer como campeonato
                    if championship and championship.strip().lower() in status_words:
                        championship = ""

                    # Skip se não tem informação válida
                    if not date_str or not team1 or not score:
                        continue

                    date_obj: Optional[datetime] = self.parse_date(date_str)
                    if not date_obj:
                        continue

                    game: Dict[str, Any] = {
                        "date": date_obj,
                        "team1": team1,
                        "team2": team2,
                        "score": score,
                        "championship": championship,
                        "status": "finished",
                        "all_day": True,
                    }
                    self.games.append(game)
                    print(f"  ✓ {team1} {score} {team2} ({date_str})")
                except Exception as e:
                    print(f"  Erro ao parse de linha: {e}")
                    continue

    def scrape_calendar(self) -> None:
        """Scrapa próximos jogos agendados do Mirassol FC.

        Acessa a página de calendário do ESPN e extrai informações sobre
        jogos já agendados.
        """
        url = "https://www.espn.com.br/futebol/time/calendario/_/id/9169/bra.mirassol"
        print(f"Buscando calendário de: {url}")

        html = self.fetch_page(url)
        soup = BeautifulSoup(html, "html.parser")

        # Encontra todas as linhas de calendário
        rows = soup.find_all("tr")

        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 5:
                try:
                    date_str = cols[0].get_text(strip=True)
                    team1 = cols[1].get_text(strip=True)
                    team2 = cols[3].get_text(strip=True)
                    time_str = cols[4].get_text(strip=True)
                    championship = cols[5].get_text(strip=True) if len(cols) > 5 else ""

                    # Skip se não tem informação válida
                    if not date_str or not team1 or not team2:
                        continue

                    date_obj: Optional[datetime] = self.parse_date(date_str)
                    if not date_obj:
                        continue

                    parsed_time, all_day = self.parse_time(time_str)
                    game: Dict[str, Any] = {
                        "date": date_obj,
                        "team1": team1,
                        "team2": team2,
                        "time": parsed_time,
                        "all_day": all_day,
                        "championship": championship,
                        "status": "scheduled",
                        "score": None,
                    }
                    self.games.append(game)
                    time_display = "A definir" if all_day else time_str
                    print(f"  ✓ {team1} vs {team2} ({date_str} {time_display})")
                except Exception as e:
                    print(f"  Erro ao parse de linha: {e}")
                    continue

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
            # Cria ID único para o evento
            event_id = hashlib.md5(
                f"{game['date']}{game['team1']}{game['team2']}".encode()
            ).hexdigest()
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

    def run(self) -> None:
        """Executa scraping completo e gera arquivo iCalendar.

        Executa todas as etapas: scraping de resultados, scraping de calendário
        e geração do arquivo .ics. Exibe sumário do progresso durante execução.

        Raises:
            Exception: Se ocorrer erro crítico durante scraping
        """
        try:
            print("=" * 60)
            print("Mirassol FC - Web Scraper")
            print("=" * 60)

            try:
                self.scrape_json_api()
            except Exception as json_error:
                print(f"\n⚠️  Falha na ESPN JSON API: {json_error}")
                self.games = []
                self.scrape_html_fallback()

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
    de extração de dados.
    """
    scraper: MirassolScraper = MirassolScraper()
    scraper.run()
