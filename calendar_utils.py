#!/usr/bin/env python3
"""
Módulo com funções compartilhadas para Google Calendar API
Centraliza autenticação, gerenciamento de calendários e eventos
"""

import os
import json
import pickle
import icalendar
import pytz
from datetime import datetime
from typing import Optional, List, Tuple

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configurações
SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN_FILE = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'
SERVICE_ACCOUNT_FILE = 'service-account.json'
ICS_FILE = 'mirassolfc.ics'
CALENDAR_ID_FILE = 'mirassolfc_calendar_id.txt'


class CalendarAuth:
    """Gerencia autenticação com Google Calendar API"""
    
    @staticmethod
    def authenticate() -> any:
        """
        Tenta múltiplos métodos de autenticação (em ordem):
        1. service-account.json (arquivo local)
        2. SERVICE_ACCOUNT_KEY (variável de ambiente - JSON string)
        3. GOOGLE_APPLICATION_CREDENTIALS (variável de ambiente - caminho)
        4. OAuth interativo com token.pickle
        """
        creds = None
        
        # 1) Prioriza service-account.json
        if os.path.exists(SERVICE_ACCOUNT_FILE):
            try:
                creds = service_account.Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_FILE, scopes=SCOPES
                )
                print("✅ Autenticado com service-account.json")
                return build('calendar', 'v3', credentials=creds)
            except Exception as e:
                print(f"❌ Erro ao ler service-account.json: {e}")
                raise
        
        # 2) SERVICE_ACCOUNT_KEY (JSON string em variável de ambiente)
        if os.environ.get('SERVICE_ACCOUNT_KEY'):
            try:
                sa_key = os.environ.get('SERVICE_ACCOUNT_KEY')
                info = json.loads(sa_key)
                creds = service_account.Credentials.from_service_account_info(
                    info, scopes=SCOPES
                )
                print("✅ Autenticado com SERVICE_ACCOUNT_KEY (env var)")
                return build('calendar', 'v3', credentials=creds)
            except Exception as e:
                print(f"❌ Erro na SERVICE_ACCOUNT_KEY: {e}")
                raise
        
        # 3) GOOGLE_APPLICATION_CREDENTIALS
        if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
            try:
                sa_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
                creds = service_account.Credentials.from_service_account_file(
                    sa_path, scopes=SCOPES
                )
                print(f"✅ Autenticado com GOOGLE_APPLICATION_CREDENTIALS ({sa_path})")
                return build('calendar', 'v3', credentials=creds)
            except Exception as e:
                print(f"❌ Erro na GOOGLE_APPLICATION_CREDENTIALS: {e}")
                raise
        
        # 4) OAuth interativo com token.pickle
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(CREDENTIALS_FILE):
                    raise FileNotFoundError(
                        f"Arquivo '{CREDENTIALS_FILE}' não encontrado. "
                        "Use service-account.json ou execute a autenticação OAuth."
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        
        print("✅ Autenticado com OAuth")
        return build('calendar', 'v3', credentials=creds)


class CalendarManager:
    """Gerencia operações com calendários"""
    
    def __init__(self, service=None):
        self.service = service or CalendarAuth.authenticate()
    
    def list_calendars(self) -> List[dict]:
        """Lista todos os calendários disponíveis"""
        try:
            calendars = self.service.calendarList().list(pageToken=None).execute()
            return calendars.get('items', [])
        except HttpError as e:
            print(f"❌ Erro ao listar calendários: {e}")
            return []
    
    def find_calendar(self, name: str) -> Optional[str]:
        """Busca ID de um calendário pelo nome"""
        calendars = self.list_calendars()
        for cal in calendars:
            if cal.get('summary', '').lower() == name.lower():
                return cal['id']
        return None
    
    def get_or_create_mirassol_calendar(self) -> Optional[str]:
        """
        Obtém ou cria o calendário "MirassolFC".
        Ordem de busca:
        1. Tenta usar ID salvo em mirassolfc_calendar_id.txt
        2. Procura por calendário com nome "MirassolFC"
        3. Se não encontrar, cria um novo
        Retorna o ID do calendário ou None em caso de erro
        """
        # Tenta usar ID salvo
        if os.path.exists(CALENDAR_ID_FILE):
            try:
                with open(CALENDAR_ID_FILE, 'r') as f:
                    saved_id = f.read().strip()
                
                if saved_id:
                    # Valida se o calendário ainda existe
                    cal_info = self.get_calendar_info(saved_id)
                    if cal_info:
                        print(f"✅ Calendário MirassolFC encontrado (ID salvo): {saved_id}")
                        return saved_id
            except Exception as e:
                print(f"⚠️  Erro ao ler ID salvo: {e}")
        
        # Procura por nome
        found_id = self.find_calendar('MirassolFC')
        if found_id:
            # Salva o ID para próxima vez
            with open(CALENDAR_ID_FILE, 'w') as f:
                f.write(found_id)
            print(f"✅ Calendário MirassolFC encontrado (busca por nome): {found_id}")
            return found_id
        
        # Cria novo calendário
        print("📅 Calendário MirassolFC não encontrado. Criando novo...")
        new_id = self.create_calendar(
            name='MirassolFC',
            description='Calendário de jogos do Mirassol FC',
            timezone='America/Sao_Paulo'
        )
        
        return new_id
    
    def create_calendar(self, name: str, description: str = "", timezone: str = "America/Sao_Paulo") -> Optional[str]:
        """
        Cria um novo calendário
        Retorna o ID do calendário criado ou None em caso de erro
        """
        try:
            calendar_body = {
                'summary': name,
                'description': description,
                'timeZone': timezone
            }
            
            created_calendar = self.service.calendars().insert(
                body=calendar_body
            ).execute()
            
            cal_id = created_calendar['id']
            
            # Salva em arquivo se for MirassolFC
            if name.lower() == 'mirassolfc':
                with open(CALENDAR_ID_FILE, 'w') as f:
                    f.write(cal_id)
                # Aplica cor Banana (amarelo) automaticamente
                self.set_calendar_color(cal_id, '4')
            
            print(f"✅ Calendário '{name}' criado: {cal_id}")
            return cal_id
        except HttpError as e:
            print(f"❌ Erro ao criar calendário: {e}")
            return None
    
    def delete_calendar(self, calendar_id: str) -> bool:
        """
        Deleta um calendário
        Retorna True se successfully, False caso contrário
        """
        try:
            self.service.calendars().delete(calendarId=calendar_id).execute()
            print(f"✅ Calendário deletado: {calendar_id}")
            return True
        except HttpError as e:
            print(f"❌ Erro ao deletar calendário: {e}")
            return False
    
    def get_calendar_info(self, calendar_id: str) -> Optional[dict]:
        """Retorna informações de um calendário"""
        try:
            cal = self.service.calendars().get(calendarId=calendar_id).execute()
            return cal
        except HttpError as e:
            print(f"❌ Erro ao obter calendário: {e}")
            return None
    
    def set_calendar_color(self, calendar_id: str, color_id: str = '4') -> bool:
        """
        Define a cor do calendário
        color_id: 4 = Banana (Amarelo)
        """
        try:
            body = {"colorId": color_id}
            self.service.calendarList().update(calendarId=calendar_id, body=body).execute()
            return True
        except HttpError as e:
            return False
    
    def share_calendar(self, calendar_id: str, email: str, role: str = 'reader') -> bool:
        """
        Compartilha calendário com um email
        role: 'reader', 'writer', 'owner'
        """
        try:
            rule = {
                'scope': {
                    'type': 'user',
                    'value': email
                },
                'role': role
            }
            
            self.service.acl().insert(calendarId=calendar_id, body=rule).execute()
            print(f"✅ Calendário compartilhado com {email} ({role})")
            return True
        except HttpError as e:
            print(f"❌ Erro ao compartilhar: {e}")
            return False


class EventManager:
    """Gerencia operações com eventos"""
    
    def __init__(self, service=None):
        self.service = service or CalendarAuth.authenticate()
    
    def list_events(self, calendar_id: str, max_results: int = 50) -> List[dict]:
        """Lista eventos de um calendário"""
        try:
            events = self.service.events().list(
                calendarId=calendar_id,
                maxResults=max_results
            ).execute()
            return events.get('items', [])
        except HttpError as e:
            print(f"❌ Erro ao listar eventos: {e}")
            return []
    
    def delete_all_events(self, calendar_id: str) -> int:
        """Deleta todos os eventos de um calendário"""
        try:
            events = self.service.events().list(
                calendarId=calendar_id,
                maxResults=2500
            ).execute()
            
            event_count = 0
            for event in events.get('items', []):
                self.service.events().delete(
                    calendarId=calendar_id,
                    eventId=event['id']
                ).execute()
                event_count += 1
            
            print(f"🗑️  Deletados {event_count} eventos")
            return event_count
        except HttpError as e:
            print(f"❌ Erro ao deletar eventos: {e}")
            return 0
    
    def create_event(self, calendar_id: str, event: dict) -> Optional[str]:
        """Cria um evento no calendário"""
        try:
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            return created_event.get('id')
        except HttpError as e:
            print(f"❌ Erro ao criar evento: {e}")
            return None
    
    def upload_events(self, calendar_id: str, vevents: List) -> Tuple[int, int]:
        """
        Faz upload de vários eventos (formato iCalendar)
        Retorna (sucessos, falhas)
        """
        successful = 0
        failed = 0
        
        for idx, vevent in enumerate(vevents, 1):
            try:
                event = self._convert_vevent_to_google_event(vevent)
                
                if event is None:
                    failed += 1
                    print(f"⚠️  [{idx}/{len(vevents)}] Evento inválido ou sem data")
                    continue
                
                created_event = self.service.events().insert(
                    calendarId=calendar_id,
                    body=event
                ).execute()
                
                successful += 1
                print(f"✅ [{idx}/{len(vevents)}] {created_event.get('summary', 'Sem título')}")
            
            except HttpError as e:
                failed += 1
                print(f"❌ [{idx}/{len(vevents)}] Erro Google Calendar: {e}")
            except Exception as e:
                failed += 1
                print(f"⚠️  [{idx}/{len(vevents)}] Erro: {e}")
        
        print(f"\n📊 Resumo: {successful} eventos criados, {failed} falharam")
        return successful, failed
    
    @staticmethod
    def _convert_vevent_to_google_event(vevent) -> Optional[dict]:
        """Converte evento iCalendar para formato Google Calendar"""
        try:
            summary = vevent.get('summary', 'Sem título')
            description = vevent.get('description', '')
            
            dtstart = vevent.get('dtstart')
            dtend = vevent.get('dtend')
            
            if dtstart is None:
                return None
            
            start_dt = dtstart.dt
            end_dt = dtend.dt if dtend else start_dt
            
            event = {
                'summary': str(summary),
                'description': str(description) if description else '',
                'start': EventManager._format_datetime(start_dt),
                'end': EventManager._format_datetime(end_dt),
            }
            
            return event
        except Exception as e:
            print(f"Erro ao converter evento: {e}")
            return None
    
    @staticmethod
    def _format_datetime(dt) -> dict:
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


class ICSManager:
    """Gerencia arquivos ICS"""
    
    @staticmethod
    def parse_ics_file(filename: str = ICS_FILE) -> List:
        """Lê e parseia arquivo .ics"""
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Arquivo '{filename}' não encontrado!")
        
        with open(filename, 'rb') as f:
            cal = icalendar.Calendar.from_ical(f.read())
        
        events = []
        for component in cal.walk():
            if component.name == "VEVENT":
                events.append(component)
        
        print(f"📄 Encontrados {len(events)} eventos no arquivo .ics")
        return events
