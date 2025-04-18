import re
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot
from message_format import escape_markdown
#from c_about import escape_markdown_v2
import logging
import pytz
import base64
from config import TIMEZONE

#Ищем ссылку на звонок если она внутри описания
def find_meeting_link(text: str) -> str:
    """
    Searches for Google Meet, Zoom, or Microsoft Teams links in the provided text.
    """
    if not text:
        return None

    # Define patterns for Google Meet, Zoom, and Microsoft Teams
    meet_pattern = r"https?://meet\.google\.com/[a-zA-Z0-9\-]+"
    zoom_pattern = r"https?://[a-z0-9\-\.]*zoom\.us/[a-zA-Z0-9\-/?=&]+"
    teams_pattern = r"https?://teams\.microsoft\.com/l/meetup-join/[0-9a-zA-Z\-]+"

    # Search for links in the text
    for pattern in [meet_pattern, zoom_pattern, teams_pattern]:
        match = re.search(pattern, text)
        if match:
            return match.group(0)

    return None

def get_video_call_link(event: dict) -> str:
    """
    Tries to find a video call link from event's description or event's hangoutLink.
    """
    description_text = event.get('description', '')  # Забираем описание
    video_call_link = find_meeting_link(description_text) or event.get('hangoutLink')
    return video_call_link or "Ссылка на звонок не найдена"

async def send_reminder(bot: Bot, user_id: int, event, event_start, minutes_before: int):

    # Проверяем, нужно ли отправить напоминание
    now = datetime.now(event_start.tzinfo)
    remaining_time = event_start - now  # Время до начала события
    # Логируем информацию
    logging.debug(f"Сейчас: {now}, начало события: {event_start}, осталось: {remaining_time}")
    
    # Если событие начинается через нужное количество минут
    if timedelta(minutes=minutes_before) <= remaining_time <= timedelta(minutes=minutes_before + 1):
        summary = escape_markdown(event.get('summary', 'Без названия'))
        hangout_link = event.get('hangoutLink')
        start = event['start'].get('dateTime', event['start'].get('date'))  # Время начала
        end = event['end'].get('dateTime', event['end'].get('date'))  # Время окончания
        location = event.get('location', 'Локация не указана')  # Локация встречи
        attendees = event.get('attendees', [])  # Участники
        description = escape_markdown(event.get('description', 'без описания')[:150])  # Truncate description
        video_call_link = get_video_call_link(event)
        
        #забираем номер события из календаря
        event_id = event['id']
        calendar_id = "primary"  # Replace with the actual calendar ID if available
        encoded_event_id = base64.urlsafe_b64encode(f"{event_id} {calendar_id}".encode()).decode()

        # Build the calendar event link
        calendar_event_link = f"https://calendar.google.com/calendar/event?eid={encoded_event_id}"

        tomorrow = now + timedelta(days=1)

        # Формируем клавиатуру, если есть ссылка
        keyboard = None
        if video_call_link and video_call_link != "Ссылка на звонок не найдена":
            button = InlineKeyboardButton(text="Перейти к звонку", url=video_call_link.strip())
            keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

        if start:
            # Конвертируем время начала из UTC в нужную временную зону
            start_time = datetime.fromisoformat(start).astimezone(pytz.utc)  # Приводим к UTC
            start_time = start_time.astimezone(TIMEZONE)  # Преобразуем в локальную временную зону
            # Если встреча завтра, добавляем и дату
            start_time_str = start_time.strftime("%d.%m.%Y %H:%M") if start_time.date() == tomorrow.date() else start_time.strftime("%H:%M")
        else:
            start_time_str = "Время не указано"

        if end:
            end_time = datetime.fromisoformat(end).astimezone(pytz.utc)  # Приводим к UTC
            end_time = end_time.astimezone(TIMEZONE)  # Преобразуем в локальную временную зону
            end_time_str = end_time.strftime("%H:%M")
        else:
            end_time_str = ""

        # Форматирование списка участников
        attendees_list = [a.get('email', 'Неизвестный участник') for a in attendees]
        attendees_str = "; ".join([f"{a}" for a in attendees_list]) if attendees_list else "Участники не указаны"

        # Ограничиваем длину списка участников до 150 символов
        if len(attendees_str) > 150:
            attendees_str = attendees_str[:150] + "..."  # Обрезаем и добавляем троеточие

        summary = escape_markdown(summary)
        start_time_str = escape_markdown(start_time_str)
        end_time_str = escape_markdown(end_time_str)
        location = escape_markdown(location)
        attendees_str = escape_markdown(attendees_str)

        notification_message = (
            f"⏰ Напоминание\!\nВаша встреча *{summary}* начинается через {minutes_before} минут\!\n"
            f"🗓 {start_time_str} \- {end_time_str} \| "
            f"*[{summary}]({calendar_event_link})*\n\n"
            f"📍 Место: {location}\n"
            f"👨‍💻 Участники: {attendees_str}\n"
            f"📝 Описание: {description}\n"
        )
       
        # Отправляем сообщение
        await bot.send_message(
            chat_id=user_id,
            text=notification_message,
            parse_mode="MarkdownV2",
            reply_markup=keyboard
        )
    else:
        logging.debug("Напоминание не отправлено: условие времени не выполнено.")
