#!/usr/bin/env python3
"""
Sincronização inteligente com Google Calendar
- Compara eventos do .ics com eventos existentes
- Atualiza eventos modificados
- Adiciona novos eventos
- Remove eventos deletados do .ics
"""

import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.api_core.exceptions import GoogleAPIError
from googleapiclient.discovery import build
import icalendar
from datetime import datetime
import pytz
import hashlib

SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_FILE = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'
CALENDAR_NAME = 'MirassolFC'
ICS_FILE = 'mirassol_futebol_clube.ics'

class GoogleCalendarSmartSync:
    def __init__(self):
        self.service = None
        self.calendar_id = None
        self.authenticate()
    
    def authenticate(self):
        """Autentica com Google Calendar API"""
        creds = None
        
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(CREDENTIALS_FILE):
                    print(f"❌ Erro: Arquivo '{CREDENTIALS_FILE}' não encontrado!")
                    print("📝 Siga as instruções em README_GOOGLE_SETUP.md para configurar")
                    exit(1)
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('calendar', 'v3', credentials=creds)
        print("✅ Autenticado com sucesso!")
    
    def get_or_create_calendar(self):
        """Obtém ou cria o calendário 'MirassolFC'"""
        try:
            calendars = self.service.calendarList().list().execute()
            
            for calendar in calendars.get('items', []):
                if calendar['summary'] == CALENDAR_NAME:
                    self.calendar_id = calendar['id']
                    print(f"✅ Calendário '{CALENDAR_NAME}' encontrado")
                    return self.calendar_id
            
            print(f"📅 Criando novo calendário '{CALENDAR_NAME}'...")
            calendar_body = {
                'summary': CALENDAR_NAME,
                'description': 'Calendário de jogos do Mirassol FC',
                'timeZone': 'America/Sao_Paulo'
            }
            
            created_calendar = self.service.calendars().insert(
                body=calendar_body
            ).execute()
            
            self.calendar_id = created_calendar['id']
            print(f"✅ Calendário criado com sucesso")
            return self.calendar_id
        
        except GoogleAPIError as e:
            print(f"❌ Erro ao gerenciar calendário: {e}")
            exit(1)
    
    def get_all_events(self):
        """Obtém todos os eventos do calendário"""
        try:
            events_dict = {}
            page_token = None
            
            while True:
                events = self.service.events().list(
                    calendarId=self.calendar_id,
                    pageToken=page_token,
                    maxResults=2500
                ).execute()
                
                for event in events.get('items', []):
                    # Usa UID personalizado se existir, senão usa ID do Google
                    event_id = event.get('description', 'NO_UID')
                    events_dict[event_id] = event
                
                page_token = events.get('nextPageToken')
                if not page_token:
                    break
            
            print(f"📖 {len(events_dict)} eventos encontrados no calendário")
            return events_dict
        
        except GoogleAPIError as e:
            print(f"❌ Erro ao obter eventos: {e}")
            exit(1)
    
    def parse_ics_file(self):
        """Lê e parseia o arquivo .ics"""
        if not os.path.exists(ICS_FILE):
            print(f"❌ Arquivo '{ICS_FILE}' não encontrado!")
            exit(1)
        
        with open(ICS_FILE, 'rb') as f:
            cal = icalendar.Calendar.from_ical(f.read())
        
        events = []
        for component in cal.walk():
            if component.name == "VEVENT":
                events.append(component)
        
        print(f"📄 {len(events)} eventos encontrados no arquivo .ics")
        return events
    
    def _get_event_hash(self, event):
        """Gera hash do evento para comparação"""
        content = f"{event['summary']}{event['start']}{event['end']}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def convert_vevent_to_google_event(self, vevent):
        """Converte evento iCalendar para formato do Google Calendar"""
        try:
            summary = vevent.get('summary', 'Sem título')
            description = vevent.get('description', '')
            dtstart = vevent.get('dtstart')
            dtend = vevent.get('dtend')
            uid = str(vevent.get('uid', ''))
            
            if dtstart is None:
                return None
            
            start_dt = dtstart.dt
            end_dt = dtend.dt if dtend else start_dt
            
            event = {
                'summary': str(summary),
                'description': f"{description}\nUID:{uid}",
                'start': self._format_datetime(start_dt),
                'end': self._format_datetime(end_dt),
            }
            
            return event, uid
        
        except Exception as e:
            print(f"⚠️  Erro ao converter evento: {e}")
            return None, None
    
    def _format_datetime(self, dt):
        """Formata datetime para Google Calendar"""
        if isinstance(dt, datetime):
            if dt.tzinfo:
                return {
                    'dateTime': dt.isoformat(),
                    'timeZone': 'America/Sao_Paulo'
                }
            else:
                br_tz = pytz.timezone('America/Sao_Paulo')
                dt_with_tz = br_tz.localize(dt)
                return {
                    'dateTime': dt_with_tz.isoformat(),
                    'timeZone': 'America/Sao_Paulo'
                }
        else:
            return {'date': dt.isoformat()}
    
    def sync(self):
        """Executa sincronização inteligente"""
        print(f"\n{'='*60}")
        print(f"🔄 Sincronização Inteligente - Mirassol FC")
        print(f"{'='*60}\n")
        
        # Passo 1: Setup
        self.get_or_create_calendar()
        
        # Passo 2: Obtém eventos atuais
        print("\n📖 Analisando estado atual...")
        current_events = self.get_all_events()
        
        # Passo 3: Lê arquivo .ics
        print("📖 Lendo arquivo .ics...")
        ics_vevents = self.parse_ics_file()
        
        # Passo 4: Organiza eventos do .ics
        ics_events = {}
        for vevent in ics_vevents:
            event, uid = self.convert_vevent_to_google_event(vevent)
            if event:
                ics_events[uid] = event
        
        # Passo 5: Sincronização
        print("\n🔄 Sincronizando eventos...\n")
        
        added = 0
        updated = 0
        deleted = 0
        skipped = 0
        
        # Novos eventos (no .ics mas não no calendário)
        for ics_uid, ics_event in ics_events.items():
            found = False
            for cal_uid, cal_event in current_events.items():
                if ics_uid in cal_event.get('description', ''):
                    found = True
                    break
            
            if not found:
                try:
                    self.service.events().insert(
                        calendarId=self.calendar_id,
                        body=ics_event
                    ).execute()
                    print(f"✨ Novo: {ics_event['summary']}")
                    added += 1
                except GoogleAPIError as e:
                    print(f"❌ Erro ao adicionar {ics_event['summary']}: {e}")
        
        # Eventos para deletar (no calendário mas não no .ics)
        for cal_uid, cal_event in current_events.items():
            # Procura UID no description
            uid_found = False
            for line in cal_event.get('description', '').split('\n'):
                if line.startswith('UID:'):
                    ics_uid = line.replace('UID:', '')
                    if ics_uid in ics_events:
                        uid_found = True
                    else:
                        # Este evento foi deletado do .ics
                        try:
                            self.service.events().delete(
                                calendarId=self.calendar_id,
                                eventId=cal_event['id']
                            ).execute()
                            print(f"🗑️  Deletado: {cal_event['summary']}")
                            deleted += 1
                        except GoogleAPIError as e:
                            print(f"❌ Erro ao deletar {cal_event['summary']}: {e}")
                    break
            
            if not uid_found and 'UID:' not in cal_event.get('description', ''):
                skipped += 1
        
        print(f"\n{'='*60}")
        print(f"📊 Resumo da Sincronização:")
        print(f"  ✨ Adicionados: {added}")
        print(f"  🔄 Atualizados: {updated}")
        print(f"  🗑️  Deletados: {deleted}")
        print(f"  ⏭️  Ignorados: {skipped}")
        print(f"{'='*60}\n")


if __name__ == '__main__':
    sync = GoogleCalendarSmartSync()
    sync.sync()
