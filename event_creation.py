import re
import asyncio
from datetime import datetime, timedelta
from typing import Tuple

async def create_google_calendar_event(user_id: int, event_data: dict) -> Tuple[bool, str]:
    try:
        from google_calendar import authenticate_google_calendar, get_calendar_service
        
        creds = await asyncio.to_thread(authenticate_google_calendar, user_id)
        if not creds:
            return False, "Ошибка: Не удалось подключиться к Google Calendar. Попробуйте /relogin"

        service = await asyncio.to_thread(get_calendar_service, creds)
        if not service:
            return False, "Ошибка: Не удалось создать сервис Google Calendar"

        time_str = event_data['time']
        if ':' not in time_str:
            time_str += ':00'
            
        start_datetime = datetime.strptime(
            f"{event_data['date']} {time_str}", 
            "%d.%m.%Y %H:%M"
        )
        end_datetime = start_datetime + timedelta(hours=float(event_data['duration']))

        event = {
            'summary': event_data['title'],
            'description': event_data.get('description', ''),
            'start': {
                'dateTime': start_datetime.isoformat(),
                'timeZone': 'Europe/Moscow',
            },
            'end': {
                'dateTime': end_datetime.isoformat(),
                'timeZone': 'Europe/Moscow',
            }
        }

        # Добавляем conferenceData только если пользователь выбрал создание ссылки
        if event_data.get('create_meet_link', False):
            event['conferenceData'] = {
                'createRequest': {
                    'requestId': f"{user_id}_{int(datetime.now().timestamp())}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                }
            }

        created_event = await asyncio.to_thread(
            lambda: service.events().insert(
                calendarId='primary', 
                body=event,
                conferenceDataVersion=1 if event_data.get('create_meet_link', False) else 0
            ).execute()
        )
        
        event_link = created_event.get('htmlLink')
        meet_link = created_event.get('hangoutLink', '')
        
        return True, format_success_message(event_data, event_link, meet_link)
    except Exception as e:
        return False, f"❌ Ошибка при создании события: {str(e)}"

def format_success_message(event_data: dict, event_link: str = None, meet_link: str = None) -> str:
    from html import escape
    time_str = event_data['time']
    if ':' not in time_str:
        time_str += ':00'
    
    start_datetime = datetime.strptime(
        f"{event_data['date']} {time_str}", 
        "%d.%m.%Y %H:%M"
    )
    end_datetime = start_datetime + timedelta(hours=float(event_data['duration']))
    
    event_time = f"{start_datetime.strftime('%H:%M')} - {end_datetime.strftime('%H:%M')}"
    
    title_link = f'<a href="{event_link}">{escape(event_data["title"])}</a>' if event_link else escape(event_data["title"])
    
    meet_info = ""
    if meet_link:
        meet_info = f"\n\n🔗 Ссылка на Google Meet: {meet_link}"
    else:
        meet_info = "\n\nℹ️ Ссылка на Google Meet не создавалась"
    
    return (
        f"✅ Событие создано!\n\n"
        f"🗓 {escape(event_data['date'])} {event_time} | {title_link}\n\n"
        f"📝 Описание: {escape(event_data.get('description', 'без описания'))}"
        f"{meet_info}"
    )

def validate_date(date_str: str) -> bool:
    """
    Проверяет корректность даты в разных форматах
    Args:
        date_str: Строка с датой
    Returns:
        bool: Валидна ли дата
    """
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            datetime.strptime(date_str, fmt)
            return True
        except ValueError:
            continue
    return False

def normalize_date(date_str: str) -> str:
    """
    Приводит дату к единому формату DD.MM.YYYY
    Args:
        date_str: Строка с датой
    Returns:
        str: Дата в формате DD.MM.YYYY
    """
    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%d.%m.%Y")
        except ValueError:
            continue
    return date_str

def validate_time(time_str: str) -> bool:
    """
    Проверяет корректность времени (допускает как ЧЧ:ММ, так и просто ЧЧ)
    """
    if ':' in time_str:
        return bool(re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', time_str))
    else:
        return bool(re.match(r'^([0-1]?[0-9]|2[0-3])$', time_str))
    
def validate_duration(duration_str: str) -> bool:
    """
    Проверяет корректность продолжительности
    Args:
        duration_str: Строка с продолжительностью
    Returns:
        bool: Валидна ли продолжительность
    """
    try:
        duration = float(duration_str)
        return 0.25 <= duration <= 8  # от 15 мин до 8 часов
    except ValueError:
        return False