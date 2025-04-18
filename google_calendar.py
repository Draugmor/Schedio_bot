# google_calendar.py
import os
import os.path
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

# Области действия с разрешениями на изменение событий
SCOPES = ["https://www.googleapis.com/auth/calendar"]
REDIRECT_URI = "https://schedio.ru/google-callback/google-callback.html"

# Глобальный словарь для хранения flow (объектов авторизации)
user_flows = {}

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def complete_authentication(user_id, code):
    try:
        if user_id not in user_flows:
            raise Exception("Flow для пользователя не найден. Начните авторизацию снова")
        
        flow = user_flows[user_id]
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Создаем папку, если её нет
        os.makedirs("user_tokens", exist_ok=True)
        token_path = f'user_tokens/token_{user_id}.pickle'
        
        logger.info(f"Пытаюсь сохранить токен по пути: {os.path.abspath(token_path)}")  # Логируем путь
        
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
            logger.info(f"Токен успешно сохранен для user_id: {user_id}")  # Подтверждение записи
            
        return creds
    except Exception as e:
        logger.error(f"Ошибка при сохранении токена: {str(e)}", exc_info=True)  # Подробное логирование
        raise Exception(f"Ошибка при завершении авторизации: {str(e)}")

def get_calendar_service(creds):
    """
    Создает сервис календаря из учетных данных
    """
    try:
        # Преобразуем OAuth2Token в Credentials если нужно
        if not isinstance(creds, Credentials):
            creds = Credentials(
                token=creds.token,
                refresh_token=creds.refresh_token,
                token_uri=creds.token_uri,
                client_id=creds.client_id,
                client_secret=creds.client_secret,
                scopes=SCOPES
            )
        return build('calendar', 'v3', credentials=creds)  # Возвращаем сервис
    except Exception as e:
        raise Exception(f"Ошибка при создании учетных данных: {str(e)}")

def get_auth_url(user_id):
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', 
        SCOPES,
        redirect_uri='https://schedio.ru/google-callback/google-callback.html'  # Исправлено
    )
    auth_url, _ = flow.authorization_url(prompt='consent')
    user_flows[user_id] = flow
    return auth_url, flow  # Добавлен возврат flow

def authenticate_google_calendar(user_id):
    """
    Аутентификация для Google Calendar API.
    """
    creds = None
    token_path = f'user_tokens/token_{user_id}.pickle'
    
    # Проверяем, есть ли сохранённый токен для этого пользователя
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    
    # Проверяем валидность токена
    if creds and creds.valid:
        return creds
    
    # Если токен отсутствует или просрочен
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Сохраняем обновленный токен
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
            return creds
        except Exception as e:
            # Если не удалось обновить токен, начинаем новую авторизацию
            pass
    
    # Если токена нет или он недействителен, возвращаем None
    return None
    
def reauthenticate_google_calendar(user_id):
    """
    Функция для повторной аутентификации пользователя
    """
    try:
        # Удаляем старый токен если он существует
        token_path = f'user_tokens/token_{user_id}.pickle'
        if os.path.exists(token_path):
            os.remove(token_path)
            
        # Возвращаем URL для новой авторизации
        return get_auth_url(user_id)
    except Exception as e:
        raise Exception(f"Ошибка при повторной аутентификации: {str(e)}")

def get_todays_events(user_id):
    """
    Получает встречи только на сегодня.
    """
    creds = authenticate_google_calendar(user_id)
    if not creds:
        return None
    service = build_calendar_service(creds)
    
    # Получаем текущую дату и время
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)  # Начало сегодняшнего дня
    today_end = today_start + timedelta(days=1)  # Конец сегодняшнего дня (наступит завтра)

    # Преобразуем в формат ISO 8601
    time_min = today_start.isoformat()
    time_max = today_end.isoformat()

    # Запрашиваем события только на сегодня
    events_result = service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    return events

def get_tomorrows_events(user_id):
    """
    Получает встречи только на завтра.
    """
    creds = authenticate_google_calendar(user_id)
    if not creds:
        return None
    service = build_calendar_service(creds)
    
    # Получаем текущую дату и время
    now = datetime.now(timezone.utc)
    tomorrow_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)  # Начало завтрашнего дня
    tomorrow_end = tomorrow_start + timedelta(days=1)  # Конец завтрашнего дня (наступит через 24 часа)

    # Преобразуем в формат ISO 8601
    time_min = tomorrow_start.isoformat()
    time_max = tomorrow_end.isoformat()

    # Запрашиваем события только на завтра
    events_result = service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    return events

def get_current_event(user_id):
    """
    Получает текущую встречу, если она сейчас активна.
    """
    creds = authenticate_google_calendar(user_id)
    if not creds:
        return None    
    service = build_calendar_service(creds)
    now = datetime.now(timezone.utc).isoformat()  # Текущее время в ISO 8601

    events_result = service.events().list(
        calendarId='primary',
        timeMin=now,
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    for event in events:
        start = event['start'].get('dateTime')
        end = event['end'].get('dateTime')

        if start and end:
            start_time = datetime.fromisoformat(start)
            end_time = datetime.fromisoformat(end)

            if start_time <= datetime.now(timezone.utc) <= end_time:
                return event  # Текущая встреча

    return None  # Нет текущей встречи


def get_next_event(user_id):
    """
    Получает следующую встречу.
    """
    creds = authenticate_google_calendar(user_id)
    if not creds:
        return None
    service = build_calendar_service(creds)
    now = datetime.now(timezone.utc).isoformat()  # Текущее время в ISO 8601

    events_result = service.events().list(
        calendarId='primary',
        timeMin=now,
        maxResults=10,  # Получаем до 10 ближайших событий для фильтрации
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    
    # Фильтруем события, чтобы найти следующее
    for event in events:
        start = event['start'].get('dateTime')
        if start:
            start_time = datetime.fromisoformat(start)
            # Если время начала события в будущем, это "следующее" событие
            if start_time > datetime.now(timezone.utc):
                return event

    return None  # Если следующих событий нет

def generate_google_meet_link(user_id):
    """
    Генерирует ссылку на Google Meet без создания события в календаре.
    """
    # Создаем сервис для работы с Google Calendar API
    creds = authenticate_google_calendar(user_id)
    if not creds:
        raise Exception("Пользователь не аутентифицирован. Пожалуйста, авторизуйтесь через команду /relogin.")
    service = build_calendar_service(creds)

    # Текущее время
    now = datetime.now(timezone.utc)  # Получаем текущее время в UTC
    start_time = (now + timedelta(minutes=15)).isoformat()  # Встреча через 15 минут
    end_time = (now + timedelta(minutes=45)).isoformat()  # Длительность 30 минут

    # Создаем запрос на создание конференции
    event = {
        "summary": "Google Meet Conference",  # Название
        "start": {"dateTime": start_time, "timeZone": "Europe/Moscow"},
        "end": {"dateTime": end_time, "timeZone": "Europe/Moscow"},
        "conferenceData": {
            "createRequest": {
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
                "requestId": "random-string-12345"
            }
        },
        "visibility": "private"  # Делаем событие скрытым
    }

    # Запрос на создание события с Google Meet
    created_event = service.events().insert(
        calendarId="primary",
        body=event,
        conferenceDataVersion=1  # Обязательно указываем эту версию для создания ссылки на Meet
    ).execute()

    # Извлекаем ссылку на Google Meet
    meet_link = created_event.get("hangoutLink", "Ссылка не создана")
    
    # Удаляем событие, чтобы оно не появилось в календаре
    service.events().delete(calendarId="primary", eventId=created_event['id']).execute()

    return meet_link

def get_upcoming_events(creds):
    """
    Получает предстоящие события из календаря.
    """
    try:
        service = build('calendar', 'v3', credentials=creds)

        # Получаем текущее время
        now = datetime.now(timezone.utc)  # UTC время

        # Форматируем timeMin в ISO 8601 (с временной зоной)
        timeMin = now.isoformat()  # Время в UTC формате ISO 8601

        events_result = service.events().list(
            calendarId='primary',
            timeMin=timeMin,  # Получаем события с текущего времени
            maxResults=10,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        return events_result.get('items', [])

    except HttpError as error:
        print(f"An error occurred: {error}")
        return []

def build_calendar_service(creds):
    """
    Создает сервис календаря из учетных данных
    """
    return build('calendar', 'v3', credentials=creds)
