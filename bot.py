# Импортируем всё необходимое без дублирования

# Модули и пакеты
import asyncio
import logging
import os
import re

# Библиотеки и модули
from aiocron import crontab
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# Пользовательские модули
from c_about import send_about_info
from config import active_users, user_settings, TIMEZONE, API_TOKEN
from event_checker import check_and_notify_events
from event_creation import (
    create_google_calendar_event,
    normalize_date,
    validate_date,
    validate_duration,
    validate_time,
)

from event_keyboards import (
    get_cancel_keyboard,
    get_confirmation_keyboard,
    get_date_selection_keyboard,
    get_duration_selection_keyboard,
    get_edit_options_keyboard,
    get_time_selection_keyboard,
    get_description_keyboard,
    get_main_keyboard
)

from event_states import EventCreationStates

from google_calendar import (
    authenticate_google_calendar,
    complete_authentication,
    generate_google_meet_link,
    get_auth_url,
    get_calendar_service,
    get_current_event,
    get_next_event,
    get_todays_events,
    get_tomorrows_events,
    get_upcoming_events,
    reauthenticate_google_calendar,
)
from message_format import format_event

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

async def check_auth(user_id: int, message: Message = None) -> bool:
    """Проверяет аутентификацию пользователя"""
    # Сначала проверяем активных пользователей
    if user_id in active_users:
        return True
        
    # Затем пробуем загрузить токен из файла
    creds = authenticate_google_calendar(user_id)
    if creds:
        active_users[user_id] = creds
        return True
        
    # Если не авторизован и передан message - показываем кнопку авторизации
    if message:
        auth_url, _ = get_auth_url(user_id)
        await message.answer(
            "🔒 Требуется авторизация\n\n"
            f"Пожалуйста, авторизуйтесь через [Google Authorization]({auth_url})",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Авторизоваться", callback_data="request_auth")
            ]])
        )
    return False

async def is_in_event_creation(state: FSMContext) -> bool:
    """Проверяет, находится ли пользователь в процессе создания события"""
    current_state = await state.get_state()
    return current_state is not None and current_state.startswith("EventCreationStates")

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
        # Проверяем аутентификацию
        is_auth = check_auth(user_id)
        # Если пользователь уже аутентифицирован, просто показываем клавиатуру
        if is_auth:
            await message.answer(
                "Вы уже авторизованы! Выберите действие:",
                reply_markup=get_main_keyboard()
            )
            return
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
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка в /start: {str(e)}")
        await message.reply(f"❌ Ошибка аутентификации: {str(e)}")

@router.message(Command('today'))
async def send_todays_events(message: types.Message):
    """Команда для получения событий на сегодня"""
    user_id = message.from_user.id
    try:
        if not await check_auth(user_id, message):
            return
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
                reply_markup=get_main_keyboard()
            )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)}", reply_markup=get_main_keyboard())

@router.message(Command('tomorrow'))
async def send_tomorrows_events(message: types.Message):
    """Команда для получения событий на завтра"""
    user_id = message.from_user.id
    try:
        if not await check_auth(user_id, message):
            return        
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
                reply_markup=get_main_keyboard()
            )
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}", reply_markup=get_main_keyboard())

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
    user_id = message.from_user.id
    try:
        if not await check_auth(user_id, message):
            return
        current_event = get_current_event(user_id)  # Получение текущей встречи

        # Если встреча есть
        if current_event:
            formatted_message, keyboard = format_event(current_event)
            await message.reply(
                text=f"_Текущая встреча:_\n{formatted_message}",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=get_main_keyboard()
            )
        else:
            await message.reply("Сейчас встреч нет.", reply_markup=get_main_keyboard())
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}", reply_markup=get_main_keyboard())

@router.message(Command('next'))
async def send_next_event(message: types.Message):
    user_id = message.from_user.id
    try:
        if not await check_auth(user_id, message):
            return
        next_event = get_next_event(user_id)  # Получение следующей встречи

        # Если встреча есть
        if next_event:
            formatted_message, keyboard = format_event(next_event)
            await message.reply(
                text=f"_Следующая встреча_:\n{formatted_message}",
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=get_main_keyboard()
            )
        else:
            await message.reply("Следующих встреч не запланировано.", reply_markup=get_main_keyboard())
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}", reply_markup=get_main_keyboard())

@router.message(Command('generate_meet_link'))
async def generate_meet_link_command(message: types.Message):
    user_id = message.from_user.id
    try:
        if not await check_auth(user_id, message):
            return
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

# ===== Обработчики создания событий ===== #

@router.message(Command('create_event'))
async def start_event_creation(message: Message, state: FSMContext):
    """Начало процесса создания события"""
    await state.set_state(EventCreationStates.waiting_for_title)
    await message.answer(
        "📌 Введите название события:",
        reply_markup=get_cancel_keyboard()
    )

@router.message(EventCreationStates.waiting_for_title)
async def process_event_title(message: Message, state: FSMContext):
    """Обработка названия события"""
    if len(message.text) > 120:
        await message.answer("Название слишком длинное (макс. 120 символов). Введите снова:")
        return
    
    await state.update_data(title=message.text)
    await state.set_state(EventCreationStates.waiting_for_date)
    await message.answer(
        "📅 Выберите дату события:",
        reply_markup=get_date_selection_keyboard()
    )

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("select_date:"))
async def process_selected_date(callback: CallbackQuery, state: FSMContext):
    """Обработка выбранной даты из календаря"""
    date = callback.data.split(":")[1]
    await state.update_data(date=date)
    await state.set_state(EventCreationStates.waiting_for_time)
    await callback.message.edit_text(
        "⌚ Выберите время начала:",
        reply_markup=get_time_selection_keyboard()
    )

@router.callback_query(F.data == "manual_date_input")
async def request_manual_date(callback: CallbackQuery, state: FSMContext):
    """Запрос ручного ввода даты"""
    await state.set_state(EventCreationStates.waiting_for_date)
    await callback.message.edit_text(
        "📅 Введите дату в формате ДД.ММ.ГГГГ, ДД-ММ-ГГГГ или ДД/ММ/ГГГГ:",
        reply_markup=get_cancel_keyboard()
    )

@router.message(EventCreationStates.waiting_for_date)
async def process_event_date(message: Message, state: FSMContext):
    """Обработка ручного ввода даты"""
    if not validate_date(message.text):
        await message.answer("Неверный формат даты. Используйте ДД.ММ.ГГГГ, ДД-ММ-ГГГГ или ДД/ММ/ГГГГ")
        return
    
    normalized_date = normalize_date(message.text)
    await state.update_data(date=normalized_date)
    await state.set_state(EventCreationStates.waiting_for_time)
    await message.answer(
        "⌚ Выберите время начала:",
        reply_markup=get_time_selection_keyboard()
    )

@router.callback_query(F.data.startswith("select_time:"))
async def process_selected_time(callback: CallbackQuery, state: FSMContext):
    """Обработка выбранного времени"""
    time = callback.data.split(":")[1]
    if ':' not in time:
        time += ':00'
    await state.update_data(time=time)
    await state.set_state(EventCreationStates.waiting_for_duration)
    await callback.message.edit_text(
        "⏳ Выберите продолжительность:",
        reply_markup=get_duration_selection_keyboard()
    )

@router.callback_query(F.data == "manual_time_input")
async def request_manual_time(callback: CallbackQuery, state: FSMContext):
    """Запрос ручного ввода времени"""
    await state.set_state(EventCreationStates.waiting_for_time)
    await callback.message.edit_text(
        "⌚ Введите время в формате ЧЧ:ММ (например, 14:30):",
        reply_markup=get_cancel_keyboard()
    )

@router.message(EventCreationStates.waiting_for_time)
async def process_event_time(message: Message, state: FSMContext):
    """Обработка ручного ввода времени"""
    if not validate_time(message.text):
        await message.answer("Неверный формат времени. Используйте ЧЧ:ММ (например, 14:30)")
        return
    time = message.text
    if ':' not in time:
        time += ':00'

    await state.update_data(time=message.text)
    await state.set_state(EventCreationStates.waiting_for_duration)
    await message.answer(
        "⏳ Выберите продолжительность:",
        reply_markup=get_duration_selection_keyboard()
    )

@router.callback_query(F.data.startswith("select_duration:"))
async def process_selected_duration(callback: CallbackQuery, state: FSMContext):
    """Обработка выбранной продолжительности"""
    duration = callback.data.split(":")[1]
    await state.update_data(duration=duration)
    await state.set_state(EventCreationStates.waiting_for_description)
    await callback.message.edit_text(
        "📝 Введите описание события (или нажмите /skip чтобы пропустить):",
        reply_markup=get_description_keyboard()
    )

@router.callback_query(F.data == "manual_duration_input")
async def request_manual_duration(callback: CallbackQuery, state: FSMContext):
    """Запрос ручного ввода продолжительности"""
    await state.set_state(EventCreationStates.waiting_for_duration)
    await callback.message.edit_text(
        "⏳ Введите продолжительность в часах (например, 0.5 для 30 минут):\n"
        "Допустимые значения: от 0.25 (15 мин) до 8 часов.",
        reply_markup=get_cancel_keyboard()
    )

@router.message(EventCreationStates.waiting_for_duration)
async def process_event_duration(message: Message, state: FSMContext):
    """Обработка ручного ввода продолжительности"""
    if not validate_duration(message.text):
        await message.answer(
            "Неверный формат продолжительности. Введите число в часах (например, 0.5 для 30 минут).\n"
            "Допустимые значения: от 0.25 (15 мин) до 8 часов."
        )
        return
    
    await state.update_data(duration=message.text)
    await state.set_state(EventCreationStates.waiting_for_description)
    await message.answer(
        "📝 Введите описание события (или нажмите /skip чтобы пропустить):",
        reply_markup=get_cancel_keyboard()
    )

@router.message(EventCreationStates.waiting_for_description, Command('skip'))
@router.message(EventCreationStates.waiting_for_description, F.text == '')
async def skip_event_description(message: Message, state: FSMContext):
    """Пропуск ввода описания"""
    await state.update_data(description='')
    await show_event_summary(message, state)

@router.message(EventCreationStates.waiting_for_description)
async def process_event_description(message: Message, state: FSMContext):
    """Обработка ввода описания"""
    if len(message.text) > 1000:
        await message.answer("Описание слишком длинное (макс. 1000 символов). Введите снова:", reply_markup=get_description_keyboard())
        return
    
    await state.update_data(description=message.text)
    await show_event_summary(message, state)

async def show_event_summary(message: Message, state: FSMContext):
    """Показывает сводку события перед подтверждением"""
    from datetime import datetime, timedelta  # Добавляем импорт
    from event_keyboards import get_meet_link_keyboard  # Добавляем импорт клавиатуры
    
    data = await state.get_data()
    
    # Формируем время окончания
    time_str = data['time']
    if ':' not in time_str:
        time_str += ':00'
    start_datetime = datetime.strptime(f"{data['date']} {time_str}", "%d.%m.%Y %H:%M")
    end_datetime = start_datetime + timedelta(hours=float(data['duration']))
    time_range = f"{time_str} - {end_datetime.strftime('%H:%M')}"
    
    summary = (
        "📌 *Название:* {title}\n\n"
        "📅 *Дата:* {date}\n"
        "⌚ *Время:* {time_range}\n"
        "📝 *Описание:* {description}\n\n"
        "Создать ссылку на Google Meet?"
    ).format(
        title=escape_markdown_v2(data.get('title', 'не указано')),
        date=escape_markdown_v2(data.get('date', 'не указана')),
        time_range=escape_markdown_v2(time_range),
        description=escape_markdown_v2(data.get('description', 'нет описания'))
    )
    
    await state.set_state(EventCreationStates.meet_link_choice)
    await message.answer(
        summary,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=get_meet_link_keyboard()
    )

@router.callback_query(F.data == "confirm_event")
async def confirm_event_creation(callback: CallbackQuery, state: FSMContext):
    """Подтверждение создания события"""
    data = await state.get_data()
    success, message = await create_google_calendar_event(callback.from_user.id, data)
    
    await callback.message.edit_text(
        message, 
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard()  # Возвращаем основную клавиатуру
    )
    await state.clear()

@router.callback_query(F.data == "edit_event")
async def edit_event_data(callback: CallbackQuery, state: FSMContext):
    """Редактирование данных события"""
    await callback.message.edit_text(
        "Что вы хотите изменить?",
        reply_markup=get_edit_options_keyboard()
    )

@router.callback_query(F.data == "cancel_creation")
async def cancel_event_creation(callback: CallbackQuery, state: FSMContext):
    """Отмена создания события"""
    await state.clear()
    await callback.message.edit_text(
        "Создание события отменено.",
        reply_markup=get_main_keyboard()  # Возвращаем основную клавиатуру
    )

# Обработчики редактирования отдельных полей
@router.callback_query(F.data == "edit_title")
async def edit_event_title(callback: CallbackQuery, state: FSMContext):
    """Редактирование названия события"""
    await state.set_state(EventCreationStates.waiting_for_title)
    await callback.message.edit_text(
        "📌 Введите новое название события:",
        reply_markup=get_cancel_keyboard()
    )

@router.callback_query(F.data == "edit_date")
async def edit_event_date(callback: CallbackQuery, state: FSMContext):
    """Редактирование даты события"""
    await state.set_state(EventCreationStates.waiting_for_date)
    await callback.message.edit_text(
        "📅 Выберите новую дату события:",
        reply_markup=get_date_selection_keyboard()
    )

@router.callback_query(F.data == "edit_time")
async def edit_event_time(callback: CallbackQuery, state: FSMContext):
    """Редактирование времени события"""
    await state.set_state(EventCreationStates.waiting_for_time)
    await callback.message.edit_text(
        "⌚ Выберите новое время начала:",
        reply_markup=get_time_selection_keyboard()
    )

@router.callback_query(F.data == "edit_duration")
async def edit_event_duration(callback: CallbackQuery, state: FSMContext):
    """Редактирование продолжительности события"""
    await state.set_state(EventCreationStates.waiting_for_duration)
    await callback.message.edit_text(
        "⏳ Выберите новую продолжительность:",
        reply_markup=get_duration_selection_keyboard()
    )

@router.callback_query(F.data == "edit_description")
async def edit_event_description(callback: CallbackQuery, state: FSMContext):
    """Редактирование описания события"""
    await state.set_state(EventCreationStates.waiting_for_description)
    await callback.message.edit_text(
        "📝 Введите новое описание события (или нажмите /skip чтобы пропустить):",
        reply_markup=get_description_keyboard()
    )

@router.callback_query(F.data == "skip_description")
async def skip_description_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки пропуска описания"""
    await state.update_data(description='')
    await callback.answer("Описание пропущено")
    await show_event_summary(callback.message, state)

@router.callback_query(F.data.startswith("create_meet_link:"))
async def process_meet_link_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора создания Google Meet ссылки"""
    choice = callback.data.split(":")[1]
    await state.update_data(create_meet_link=(choice == "yes"))
    await show_confirmation(callback.message, state)  # Изменено на show_confirmation

async def show_confirmation(message: Message, state: FSMContext):
    """Показывает финальное подтверждение перед созданием события"""
    from datetime import datetime, timedelta
    
    data = await state.get_data()
    
    # Формируем время окончания
    time_str = data['time']
    if ':' not in time_str:
        time_str += ':00'
    start_datetime = datetime.strptime(f"{data['date']} {time_str}", "%d.%m.%Y %H:%M")
    end_datetime = start_datetime + timedelta(hours=float(data['duration']))
    time_range = f"{time_str} - {end_datetime.strftime('%H:%M')}"
    
    meet_status = "Да" if data.get('create_meet_link', False) else "Нет"
    
    summary = (
        "📌 *Название:* {title}\n\n"
        "📅 *Дата:* {date}\n"
        "⌚ *Время:* {time_range}\n"
        "📝 *Описание:* {description}\n"
        "🔗 *Google Meet:* {meet_status}\n\n"
        "Подтверждаете создание события?"
    ).format(
        title=escape_markdown_v2(data.get('title', 'не указано')),
        date=escape_markdown_v2(data.get('date', 'не указана')),
        time_range=escape_markdown_v2(time_range),
        description=escape_markdown_v2(data.get('description', 'нет описания')),
        meet_status=escape_markdown_v2(meet_status)
    )
    
    await state.set_state(EventCreationStates.confirmation)
    await message.answer(
        summary,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=get_confirmation_keyboard()
    )

@router.callback_query(F.data == "create_event")
async def create_event_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки создания события"""
    await start_event_creation(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "next_event")
async def next_event_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        # Проверяем аутентификацию без отправки сообщения
        if user_id not in active_users:
            creds = authenticate_google_calendar(user_id)
            if creds:
                active_users[user_id] = creds
            else:
                await callback.answer("🔒 Требуется авторизация", show_alert=True)
                return

        await send_next_event(callback.message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in next_event_callback: {str(e)}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(F.data == "today_events")
async def today_events_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        # Проверяем аутентификацию без отправки сообщения
        if user_id not in active_users:
            creds = authenticate_google_calendar(user_id)
            if creds:
                active_users[user_id] = creds
            else:
                await callback.answer("🔒 Требуется авторизация", show_alert=True)
                return
            
        await send_todays_events(callback.message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in today_events_callback: {str(e)}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data == "tomorrow_events")
async def tomorrow_events_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        # Проверяем аутентификацию без отправки сообщения
        if user_id not in active_users:
            creds = authenticate_google_calendar(user_id)
            if creds:
                active_users[user_id] = creds
            else:
                await callback.answer("🔒 Требуется авторизация", show_alert=True)
                return
    
        await send_tomorrows_events(callback.message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in tomorrow_events_callback: {str(e)}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.callback_query(F.data == "generate_meet")
async def generate_meet_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        # Проверяем аутентификацию без отправки сообщения
        if user_id not in active_users:
            creds = authenticate_google_calendar(user_id)
            if creds:
                active_users[user_id] = creds
            else:
                await callback.answer("🔒 Требуется авторизация", show_alert=True)
                return
        
        await generate_meet_link_command(callback.message)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in generate_meet_callback: {str(e)}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.message()
async def handle_other_messages(message: Message, state: FSMContext):
    """Обработчик всех сообщений с показом основной клавиатуры"""
    if not await is_in_event_creation(state):
        if await check_auth(message.from_user.id, message):
            await message.answer(
                "Выберите действие:",
                reply_markup=get_main_keyboard()
            )

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Переносим cron job внутрь main
    @crontab('*/1 * * * *')  # Каждую минуту
    async def cron_job():
        await check_and_notify_events(bot)
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())