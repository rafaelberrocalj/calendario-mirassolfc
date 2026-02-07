#!/usr/bin/env python3
"""
Sincroniza eventos do arquivo .ics com o Google Calendar
Cria calendário 'MirassolFC' se não existir e sincroniza todos os eventos
"""

import os
import pickle
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.api_core.exceptions import GoogleAPIError
# Service account support
from google.oauth2 import service_account
import icalendar
from datetime import datetime, timezone
import pytz

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_FILE = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'
CALENDAR_NAME = 'MirassolFC'
ICS_FILE = 'mirassol_futebol_clube.ics'

class GoogleCalendarSync:
    def __init__(self):
        self.service = None
        self.calendar_id = None
        self.authenticate()
    
    def authenticate(self):
        """Autentica com Google Calendar API"""
        creds = None
        # 1) Prefer SERVICE_ACCOUNT_KEY env var (raw JSON) for GitHub Actions
        sa_key = os.environ.get('SERVICE_ACCOUNT_KEY')
        if sa_key:
            try:
                info = json.loads(sa_key)
                creds = service_account.Credentials.from_service_account_info(
                    info, scopes=SCOPES
                )
            except Exception as e:
                print(f"❌ Chave da Service Account em SERVICE_ACCOUNT_KEY inválida: {e}")
                exit(1)
        else:
            # 2) Fallback: check GOOGLE_APPLICATION_CREDENTIALS or service-account.json file
            sa_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') or 'service-account.json'
            if os.path.exists(sa_path):
                creds = service_account.Credentials.from_service_account_file(
                    sa_path, scopes=SCOPES
                )
            else:
                # Carrega token existente para fluxo OAuth interativo
                if os.path.exists(TOKEN_FILE):
                    with open(TOKEN_FILE, 'rb') as token:
                        creds = pickle.load(token)

                # Se não há credenciais válidas, faz login (fluxo interativo)
                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        if not os.path.exists(CREDENTIALS_FILE):
                            print(f"❌ Erro: Arquivo '{CREDENTIALS_FILE}' não encontrado!")
                            print("📝 Siga as instruções em SETUP.md para configurar")
                            exit(1)

                        flow = InstalledAppFlow.from_client_secrets_file(
                            CREDENTIALS_FILE, SCOPES)
                        creds = flow.run_local_server(port=0)

                    # Salva token para próxima vez
                    with open(TOKEN_FILE, 'wb') as token:
                        pickle.dump(creds, token)
        
        # Cria cliente do Google Calendar usando a biblioteca googleapiclient
        from googleapiclient.discovery import build
        self.service = build('calendar', 'v3', credentials=creds)
        
        print("✅ Autenticado com sucesso!")
    
    def get_or_create_calendar(self):
        """Obtém ou cria o calendário 'MirassolFC'"""
        try:
            # Busca calendários existentes
            calendars = self.service.calendarList().list(pageToken=None).execute()
            
            for calendar in calendars.get('items', []):
                if calendar['summary'] == CALENDAR_NAME:
                    self.calendar_id = calendar['id']
                    print(f"✅ Calendário '{CALENDAR_NAME}' encontrado: {self.calendar_id}")
                    return self.calendar_id
            
            # Calendário não existe, cria um novo
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
            print(f"✅ Calendário criado com sucesso: {self.calendar_id}")
            return self.calendar_id
        
        except GoogleAPIError as e:
            print(f"❌ Erro ao gerenciar calendário: {e}")
            exit(1)
    
    def delete_all_events(self):
        """Deleta todos os eventos do calendário"""
        try:
            events = self.service.events().list(
                calendarId=self.calendar_id,
                maxResults=2500
            ).execute()
            
            event_count = 0
            for event in events.get('items', []):
                self.service.events().delete(
                    calendarId=self.calendar_id,
                    eventId=event['id']
                ).execute()
                event_count += 1
            
            if event_count > 0:
                print(f"🗑️  Deletados {event_count} eventos")
            else:
                print("📭 Nenhum evento para deletar")
            
            return event_count
        
        except GoogleAPIError as e:
            print(f"❌ Erro ao deletar eventos: {e}")
            exit(1)
    
    def parse_ics_file(self):
        """Le e parseia o arquivo .ics"""
        if not os.path.exists(ICS_FILE):
            print(f"❌ Arquivo '{ICS_FILE}' não encontrado!")
            exit(1)
        
        with open(ICS_FILE, 'rb') as f:
            cal = icalendar.Calendar.from_ical(f.read())
        
        events = []
        for component in cal.walk():
            if component.name == "VEVENT":
                events.append(component)
        
        print(f"📄 Encontrados {len(events)} eventos no arquivo .ics")
        return events
    
    def convert_vevent_to_google_event(self, vevent):
        """Converte um evento iCalendar para formato do Google Calendar"""
        try:
            summary = vevent.get('summary', 'Sem título')
            description = vevent.get('description', '')
            
            # Processa datas
            dtstart = vevent.get('dtstart')
            dtend = vevent.get('dtend')
            
            if dtstart is None:
                return None
            
            # Extrai valores de data/hora
            start_dt = dtstart.dt
            end_dt = dtend.dt if dtend else start_dt
            
            # Cria o evento do Google Calendar
            event = {
                'summary': str(summary),
                'description': str(description) if description else '',
                'start': self._format_datetime(start_dt),
                'end': self._format_datetime(end_dt),
            }
            
            # Adiciona UID como ID externo (para sincronização)
            uid = vevent.get('uid')
            if uid:
                event['id'] = str(uid).replace('@', '_').replace('.', '_')[:32]
            
            return event
        
        except Exception as e:
            print(f"⚠️  Erro ao converter evento: {e}")
            return None
    
    def _format_datetime(self, dt):
        """Formata datetime para o formato esperado pelo Google Calendar"""
        if isinstance(dt, datetime):
            # Se tem timezone, converte para ISO format com timezone
            if dt.tzinfo:
                return {
                    'dateTime': dt.isoformat(),
                    'timeZone': 'America/Sao_Paulo'
                }
            else:
                # Se não tem timezone, assume Brasil
                br_tz = pytz.timezone('America/Sao_Paulo')
                dt_with_tz = br_tz.localize(dt)
                return {
                    'dateTime': dt_with_tz.isoformat(),
                    'timeZone': 'America/Sao_Paulo'
                }
        else:
            # É uma data sem hora
            return {'date': dt.isoformat()}
    
    def upload_events(self, vevents):
        """Faz upload dos eventos para o Google Calendar"""
        successful = 0
        failed = 0
        
        for vevent in vevents:
            try:
                event = self.convert_vevent_to_google_event(vevent)
                
                if event is None:
                    failed += 1
                    continue
                
                created_event = self.service.events().insert(
                    calendarId=self.calendar_id,
                    body=event
                ).execute()
                
                successful += 1
                print(f"✅ {created_event['summary']}")
            
            except GoogleAPIError as e:
                failed += 1
                print(f"❌ Erro ao criar evento: {e}")
            except Exception as e:
                failed += 1
                print(f"⚠️  Erro inesperado: {e}")
        
        print(f"\n📊 Resumo: {successful} eventos criados, {failed} falharam")
        return successful, failed
    
    def sync(self):
        """Executa a sincronização completa"""
        print(f"\n{'='*60}")
        print(f"🔄 Sincronizando Mirassol FC com Google Calendar")
        print(f"{'='*60}\n")
        
        # 1. Obtém ou cria calendário
        self.get_or_create_calendar()
        
        # 2. Deleta eventos existentes
        print("\n🔄 Limpando eventos antigos...")
        self.delete_all_events()
        
        # 3. Lê arquivo .ics
        print("\n📖 Lendo arquivo .ics...")
        vevents = self.parse_ics_file()
        
        # 4. Faz upload dos novos eventos
        print("\n⬆️  Fazendo upload dos eventos...\n")
        successful, failed = self.upload_events(vevents)
        
        print(f"\n{'='*60}")
        print(f"✨ Sincronização concluída!")
        print(f"{'='*60}\n")


if __name__ == '__main__':
    sync = GoogleCalendarSync()
    sync.sync()
