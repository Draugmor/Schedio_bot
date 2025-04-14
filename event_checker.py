import logging
from datetime import datetime
from google_calendar import get_upcoming_events, authenticate_google_calendar  # Функция для получения событий из Google Calendar
from reminders import send_reminder  # Функция для отправки напоминаний
from config import TIMEZONE, active_users, user_settings, TOKENS_DIR  # Конфигурации и общие переменные
import os
from dateutil import parser  # Добавляем парсер даты из библиотеки dateutil

async def check_and_notify_events(bot):
    """
    Проверка событий и отправка уведомлений.
    Эта функция вызывается по расписанию через Cloud Scheduler.
    """
    try:
        now = datetime.now(TIMEZONE)  # `now` уже offset-aware
        logging.debug(f"Проверка событий на {now}")

        for filename in os.listdir(TOKENS_DIR):
            if filename.startswith('token_') and filename.endswith('.pickle'):
                user_id = int(filename.replace('token_', '').replace('.pickle', ''))

                creds = authenticate_google_calendar(user_id)
                if creds:
                    events = get_upcoming_events(creds)
                    for event in events:
                        event_id = event['id']
                        logging.debug(f"Проверяем событие {event_id}")

                        # Извлекаем время начала события
                        event_start_str = event['start'].get('dateTime', event['start'].get('date'))
                        event_start = parser.isoparse(event_start_str)  # Парсим строку в datetime

                        # Если event_start без таймзоны, добавляем её
                        if event_start.tzinfo is None:
                            event_start = event_start.replace(tzinfo=TIMEZONE)

                        reminder_time = user_settings.get(user_id, 0)
                        logging.debug(f"Настройка для {user_id}: {reminder_time} минут")
                        logging.debug(f"Событие: {event['summary']}")
                        logging.debug(f"Время начала события: {event_start}")
                        logging.debug(f"Текущее время: {now}")
                        logging.debug(f"До события осталось: {event_start - now}")

                        # Отправляем напоминание пользователю
                        await send_reminder(bot, user_id, event, event_start, reminder_time)

    except Exception as e:
        logging.error(f"Ошибка при проверке событий: {str(e)}")