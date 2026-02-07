#!/usr/bin/env python3
"""
Scraper para extrair dados de jogos do Mirassol FC do ESPN
Gera um arquivo iCalendar (.ics) para importar no Google Calendar
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import hashlib
from urllib.parse import urljoin

# Headers para contornar proteção anti-bot
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.espn.com.br/',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
}

class MirassolScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.games = []
        
    def fetch_page(self, url):
        """Fetch page com retry e delay para evitar bloqueio"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                # Delay entre requisições
                time.sleep(2)
                return response.text
            except requests.exceptions.RequestException as e:
                print(f"Erro na tentativa {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))  # Backoff exponencial
                else:
                    raise
    
    def parse_date(self, date_str):
        """Parse data no formato 'dom., 8 fev.' ou 'qua., 11 fev.' para datetime"""
        # Remove o dia da semana
        date_str = re.sub(r'^[a-z]+\.,\s*', '', date_str, flags=re.IGNORECASE).strip()
        
        # Mapa de meses em português
        month_map = {
            'jan': 1, 'janeiro': 1,
            'fev': 2, 'fevereiro': 2,
            'mar': 3, 'março': 3,
            'abr': 4, 'abril': 4,
            'mai': 5, 'maio': 5,
            'jun': 6, 'junho': 6,
            'jul': 7, 'julho': 7,
            'ago': 8, 'agosto': 8,
            'set': 9, 'setembro': 9,
            'out': 10, 'outubro': 10,
            'nov': 11, 'novembro': 11,
            'dez': 12, 'dezembro': 12
        }
        
        try:
            # Extrai dia e mês usando regex
            match = re.search(r'(\d+)\s+([a-zç]+)', date_str, re.IGNORECASE)
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
            year_match = re.search(r'(\d{4})', date_str)
            year = int(year_match.group(1)) if year_match else 2026
            
            date_obj = datetime(year, month_num, day)
            return date_obj
            
        except Exception as e:
            print(f"Erro ao parse da data '{date_str}': {e}")
            return None
    
    def parse_time(self, time_str):
        """Parse hora no formato '18:30' ou 'A definir'"""
        time_str = time_str.strip()
        if 'definir' in time_str.lower() or not time_str:
            return '18:00'  # Hora padrão
        try:
            return time_str
        except:
            return '18:00'
    
    def parse_score(self, score_str):
        """Parse placar no formato '2 - 2' ou retorna None se não há placar"""
        score_str = score_str.strip()
        if not score_str or '-' not in score_str:
            return None
        try:
            parts = score_str.split('-')
            return f"{parts[0].strip()} - {parts[1].strip()}"
        except:
            return None
    
    def scrape_results(self):
        """Scrape resultados já realizados"""
        url = 'https://www.espn.com.br/futebol/time/resultados/_/id/9169/bra.mirassol'
        print(f"Buscando resultados de: {url}")
        
        html = self.fetch_page(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        # Encontra todas as linhas de resultados
        rows = soup.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
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
                    status_words = ('finalizado', 'final', 'encerrado', 'terminado', 'concluído', 'concluido', 'ft')
                    if championship and championship.strip().lower() in status_words and len(cols) > 5:
                        alt = cols[5].get_text(strip=True)
                        if alt and alt.strip().lower() not in status_words:
                            championship = alt
                    # Se ainda for só um status, limpar para não aparecer como campeonato
                    if championship and championship.strip().lower() in status_words:
                        championship = ""
                    
                    # Skip se não tem informação válida
                    if not date_str or not team1 or not score:
                        continue
                    
                    date_obj = self.parse_date(date_str)
                    if not date_obj:
                        continue
                    
                    game = {
                        'date': date_obj,
                        'team1': team1,
                        'team2': team2,
                        'score': score,
                        'championship': championship,
                        'status': 'finished',
                        'time': '18:00'
                    }
                    self.games.append(game)
                    print(f"  ✓ {team1} {score} {team2} ({date_str})")
                except Exception as e:
                    print(f"  Erro ao parse de linha: {e}")
                    continue
    
    def scrape_calendar(self):
        """Scrape próximos jogos"""
        url = 'https://www.espn.com.br/futebol/time/calendario/_/id/9169/bra.mirassol'
        print(f"Buscando calendário de: {url}")
        
        html = self.fetch_page(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        # Encontra todas as linhas de calendário
        rows = soup.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
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
                    
                    date_obj = self.parse_date(date_str)
                    if not date_obj:
                        continue
                    
                    game = {
                        'date': date_obj,
                        'team1': team1,
                        'team2': team2,
                        'time': self.parse_time(time_str),
                        'championship': championship,
                        'status': 'scheduled',
                        'score': None
                    }
                    self.games.append(game)
                    print(f"  ✓ {team1} vs {team2} ({date_str} {time_str})")
                except Exception as e:
                    print(f"  Erro ao parse de linha: {e}")
                    continue
    
    def generate_ics(self, output_file='mirassol_futebol_clube.ics'):
        """Gera arquivo iCalendar (.ics) com todos os jogos"""
        print(f"\nGerando arquivo iCalendar: {output_file}")
        
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
        
        # Eventos
        for game in self.games:
            # Cria ID único para o evento
            event_id = hashlib.md5(
                f"{game['date']}{game['team1']}{game['team2']}".encode()
            ).hexdigest()
            
            # Parse time
            time_parts = game['time'].split(':')
            hour = time_parts[0] if time_parts else '18'
            minute = time_parts[1] if len(time_parts) > 1 else '00'
            
            # Data e hora do evento
            dt_start = game['date'].replace(hour=int(hour), minute=int(minute))
            dt_start_str = dt_start.strftime('%Y%m%dT%H%M%S')
            dt_end = dt_start.replace(hour=dt_start.hour + 2)  # Assume 2 horas de duração
            dt_end_str = dt_end.strftime('%Y%m%dT%H%M%S')
            
            # Descrição do evento
            if game['status'] == 'finished':
                description = f"Resultado: {game['team1']} {game['score']} {game['team2']}"
                # Incluir campeonato se disponível; caso contrário mostrar 'Finalizado'
                if game.get('championship'):
                    summary = f"{game['team1']} {game['score']} {game['team2']} - {game['championship']}"
                else:
                    summary = f"{game['team1']} {game['score']} {game['team2']} - Finalizado"
            else:
                description = f"{game['championship']} - Jogo agendado"
                summary = f"{game['team1']} x {game['team2']} - {game['championship']}"
            
            event = [
                "BEGIN:VEVENT",
                f"UID:{event_id}@mirassol.local",
                f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}",
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
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(ics_content))
        
        print(f"✓ Arquivo '{output_file}' gerado com {len(self.games)} jogos!")
        return output_file
    
    def run(self):
        """Executa scraping completo"""
        try:
            print("=" * 60)
            print("Mirassol FC - Web Scraper")
            print("=" * 60)
            
            self.scrape_results()
            print()
            self.scrape_calendar()
            
            print(f"\nTotal de jogos encontrados: {len(self.games)}")
            self.generate_ics()
            
            print("\n" + "=" * 60)
            print("✓ Scraping concluído com sucesso!")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n✗ Erro durante execução: {e}")
            raise

if __name__ == '__main__':
    scraper = MirassolScraper()
    scraper.run()
