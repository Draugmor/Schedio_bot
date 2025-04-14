#import datetime
import asyncio
import re
from aiogram import Bot, Dispatcher, types, Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.filters import Command
from google_calendar import authenticate_google_calendar, get_auth_url, reauthenticate_google_calendar, get_todays_events, get_tomorrows_events, get_current_event, get_next_event, generate_google_meet_link, get_upcoming_events, complete_authentication, get_calendar_service
from message_format import format_event
import logging
import os
from event_checker import check_and_notify_events
from config import active_users, user_settings, TIMEZONE, API_TOKEN
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiocron import crontab
from c_about import send_about_info

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,  # Уровень логирования (INFO, DEBUG, WARNING, ERROR, CRITICAL)
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # Формат сообщений
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),  # Логи будут записываться в файл bot.log
        logging.StreamHandler()  # Логи также будут выводиться в консоль
    ]
)

logger = logging.getLogger(__name__)
logger.info("✅ Логирование успешно настроено!")

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()  # Создаём роутер
dp.include_router(router)  # Подключаем роутер к диспетчеру

async def periodic_check():
    """Периодически вызывает check_and_notify_events каждые 60 секунд."""
    while True:
        try:
            await asyncio.sleep(60)
            await check_and_notify_events(bot)
        except Exception as e:
            logging.error(f"Ошибка в periodic_check: {str(e)}")

def escape_markdown_v2(text: str) -> str:
    # Экранируем специальные символы для MarkdownV2
    return re.sub(r'([_*[\]()~`>#+-=|{}.!])', r'\\\1', text)

class AuthStates(StatesGroup):
    waiting_for_code = State()

# Обработчик команды /start
@router.message(Command('start'))
async def send_welcome(message: types.Message, state: FSMContext):
    """Приветствие при старте бота"""
    user_id = message.from_user.id
    try:
        logger.info(f"Пользователь {user_id} запустил команду /start")
        # Извлекаем код из параметра команды (если есть)
        parts = message.text.split()
        code = parts[1] if len(parts) > 1 else None

        # Если передан код, завершаем аутентификацию
        if code:
            logger.info(f"Получен код авторизации: {code}")
            data = await state.get_data()
            flow = data.get("flow")
            
            if not flow:
                await message.reply("❌ Ошибка. Начните с команды /start без параметров.")
                return
            
            try:
                creds = complete_authentication(user_id, code)
                active_users[user_id] = creds
                await state.clear()
                await message.reply("✅ Авторизация успешна!")
                return
            except Exception as e:
                logger.error(f"Ошибка complete_authentication: {str(e)}")
                await message.reply(f"❌ Ошибка: {str(e)}")
                return
        
        creds = authenticate_google_calendar(user_id)
        # Если токен отсутствует или недействителен
        if not creds:
            auth_url, flow = get_auth_url(user_id)  # Получаем URL и flow
            await state.update_data(flow=flow)  # Сохраняем flow в состоянии
            await state.set_state(AuthStates.waiting_for_code)  # Устанавливаем состояние ожидания кода
            await message.reply(
                f"Привет\! Я очень рад Вас видеть\!\n\n 🔑 Для начала работы необходимо авторизоваться через [Google Authorization]({auth_url})\.\n\n"
                "После разрешения доступа вы будете перенаправлены обратно в бота\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        
        # Если токен действителен
        active_users[user_id] = creds
        await message.reply(
            "Привет\! Я Schedio и я помогу тебе управлять встречами\! "
            "Используй команды\:\n/today, чтобы узнать, что запланировано на сегодня, \n"
            "/tomorrow, чтобы узнать, что будет завтра, \n"
            "/now \- посмотреть текущую встречу,\n"
            "/next \- посмотреть следующую \(даже если она не сегодня\),\n"
            "/generate_meet_link \- создание ссылки на google meet, \n"
            "и /relogin для повторной аутентификации\.\n\n /about расскажет о всех возможностях бота\.\n\n",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        logger.error(f"Ошибка в /start: {str(e)}")
        await message.reply(f"❌ Ошибка аутентификации: {str(e)}")

@router.message(Command('today'))
async def send_todays_events(message: types.Message):
    """Команда для получения событий на сегодня"""
    user_id = message.from_user.id
    try:
        events = get_todays_events(user_id)  # Получение событий

        # Если событий нет
        if not events:
            await message.reply("Сегодня встреч нет.")
            return

        # Отправка каждого события пользователю
        for event in events:
            formatted_message, keyboard = format_event(event)  # Форматируем событие
            await message.reply(
                text=formatted_message,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=keyboard
            )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)}")

@router.message(Command('tomorrow'))
async def send_tomorrows_events(message: types.Message):
    """Команда для получения событий на завтра"""
    try:
        # Аутентификация в Google Calendar
        user_id = message.from_user.id
        events = get_tomorrows_events(user_id)  # Получение событий на завтра

        # Если событий нет
        if not events:
            await message.reply("Завтра встреч нет.")
            return

        # Отправка каждого события пользователю
        for event in events:
            formatted_message, keyboard = format_event(event)  # Форматируем событие
            await message.reply(
                text=formatted_message,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=keyboard
            )
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")

@router.message(Command('relogin'))
async def relogin(message: types.Message, state: FSMContext):
    """Команда для повторной аутентификации (релогин)"""
    try:
        user_id = message.from_user.id
        
        # Удаляем старый токен
        token_path = f'user_tokens/token_{user_id}.pickle'
        if os.path.exists(token_path):
            os.remove(token_path)
        
        # Запускаем процесс повторной авторизации
        auth_url, flow = get_auth_url(user_id)  # Получаем URL и flow
        await state.update_data(flow=flow)  # Сохраняем flow в состоянии
        await state.set_state(AuthStates.waiting_for_code)  # Устанавливаем состояние ожидания кода
        
        await message.reply(
            "Для повторной авторизации:\n"
            f"1\. Перейдите по ссылке: [Google Authorization]({auth_url})\n"
            "2\. Разрешите доступ к календарю\n"
            "3\. Скопируйте код и отправьте его мне",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        await message.reply(f"Ошибка при релогине: {str(e)}")

@router.message(Command('now'))
async def send_current_event(message: types.Message):
    """Команда для просмотра текущей встречи."""
    try:
        user_id = message.from_user.id
        current_event = get_current_event(user_id)  # Получение текущей встречи

        # Если встреча есть
        if current_event:
            formatted_message, keyboard = format_event(current_event)
            await message.reply(
                text=f"_Текущая встреча:_\n{formatted_message}",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=keyboard
            )
        else:
            await message.reply("Сейчас встреч нет.")
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")

@router.message(Command('next'))
async def send_next_event(message: types.Message):
    """Команда для просмотра следующей встречи."""
    try:
        user_id = message.from_user.id
        next_event = get_next_event(user_id)  # Получение следующей встречи

        # Если встреча есть
        if next_event:
            formatted_message, keyboard = format_event(next_event)
            await message.reply(
                text=f"_Следующая встреча_:\n{formatted_message}",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=keyboard
            )
        else:
            await message.reply("Следующих встреч не запланировано.")
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")

@router.message(Command('generate_meet_link'))
async def generate_meet_link_command(message: types.Message):
    try:
        user_id = message.from_user.id  # Получаем ID пользователя
        meet_link = generate_google_meet_link(user_id)
        if meet_link != "Ссылка на звонок не найдена":
            await message.reply(f"Ваша ссылка на Google Meet: {meet_link}")
        else:
            await message.reply("Не удалось создать ссылку. Проверьте настройки календаря.")
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")

@router.message(Command('set_reminder_15'))
async def set_reminder_15(message: types.Message):
    """Команда для включения/выключения напоминания за 15 минут"""
    user_id = message.from_user.id
    if user_settings.get(user_id) == 15:
        user_settings.pop(user_id)  # Удаляем настройку
        await message.reply("Вы отключили напоминания за 15 минут до начала встречи.")
    else:
        user_settings[user_id] = 15  # Включаем настройку
        await message.reply("Вы включили напоминания за 15 минут до начала встречи.")

@router.message(Command('set_reminder_10'))
async def set_reminder_10(message: types.Message):
    """Команда для включения/выключения напоминания за 10 минут"""
    user_id = message.from_user.id
    if user_settings.get(user_id) == 10:
        user_settings.pop(user_id)  # Удаляем настройку
        await message.reply("Вы отключили напоминания за 10 минут до начала встречи.")
    else:
        user_settings[user_id] = 10  # Включаем настройку
        await message.reply("Вы включили напоминания за 10 минут до начала встречи.")

@router.message(Command('set_reminder_5'))
async def set_reminder_5(message: types.Message):
    """Команда для включения/выключения напоминания за 5 минут"""
    user_id = message.from_user.id
    if user_settings.get(user_id) == 5:
        user_settings.pop(user_id)  # Удаляем настройку
        await message.reply("Вы отключили напоминания за 5 минут до начала встречи.")
    else:
        user_settings[user_id] = 5  # Включаем настройку
        await message.reply("Вы включили напоминания за 5 минут до начала встречи.")

@router.message(Command('set_reminder_0'))
async def set_reminder_0(message: types.Message):
    """Команда для включения/выключения напоминания за 0 минут"""
    user_id = message.from_user.id
    if user_settings.get(user_id) == 0:
        user_settings.pop(user_id)  # Удаляем настройку
        await message.reply("Вы отключили напоминания за 0 минут до начала встречи.")
    else:
        user_settings[user_id] = 0  # Включаем настройку
        await message.reply("Вы включили напоминания за 0 минут до начала встречи.")

@router.message(Command('logout'))
async def logout(message: types.Message):
    """Команда для выхода из аккаунта Google"""
    user_id = message.from_user.id
    token_path = f'user_tokens/token_{user_id}.pickle'
    
    if os.path.exists(token_path):
        os.remove(token_path)
        if user_id in active_users:
            del active_users[user_id]
        await message.reply("Вы успешно вышли из аккаунта Google.")
    else:
        await message.reply("Вы не были авторизованы.")

@router.message(Command('about'))
async def about_command(message: types.Message):
    await send_about_info(message)

@router.message(AuthStates.waiting_for_code)
async def process_auth_code(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        data = await state.get_data()
        flow = data.get("flow")
        
        if not flow:
            await message.reply("❌ Ошибка. Начните с команды /start")
            await state.clear()
            return
        
        # Завершаем аутентификацию
        creds = complete_authentication(user_id, message.text.strip())  # Исправлено
        active_users[user_id] = creds
        
        await state.clear()
        await message.reply(
            "✅ Авторизация успешна!\n\n Теперь вы можете:\n"
            "/today — посмотреть события на сегодня\n"
            "/tomorrow — посмотреть события на завтра\n"
            "/now — посмотреть текущую встречу\n"
            "/next — посмотреть следующую встречу\n"
            "/generate_meet_link — создать персональную ссылку на Google Meet\n\n"
            "/about — узнайте больше о возможностях бота, он может больше!\n"
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)}")
        await state.clear()

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем задачу каждые 60 секунд
    @crontab('*/1 * * * *')  # Каждую минуту
    async def cron_job():
        await check_and_notify_events(bot)
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())