from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta

def get_date_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора даты
    Returns:
        InlineKeyboardMarkup: Клавиатура с датами
    """
    today = datetime.now()
    kb = InlineKeyboardBuilder()
    
    # Кнопки для ближайших дат
    for i in range(0, 5):
        date = today + timedelta(days=i)
        kb.button(
            text=date.strftime("%d.%m"),
            callback_data=f"select_date:{date.strftime('%d.%m.%Y')}"
        )
    
    # Кнопка для ручного ввода
    kb.button(text="📅 Ввести дату вручную", callback_data="manual_date_input")
    kb.adjust(3, 3)
    return kb.as_markup()

def get_time_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора времени
    Returns:
        InlineKeyboardMarkup: Клавиатура с временами
    """
    kb = InlineKeyboardBuilder()
    
    for hour in range(8, 22):
        for minute in (0, 30):
            time_str = f"{hour:02d}:{minute:02d}"
            kb.button(text=time_str, callback_data=f"select_time:{time_str}")
    
    # Кнопка для ручного ввода
    kb.button(text="⌚ Ввести время вручную", callback_data="manual_time_input")
    kb.adjust(4)
    return kb.as_markup()

def get_duration_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора продолжительности
    Returns:
        InlineKeyboardMarkup: Клавиатура с вариантами продолжительности
    """
    durations = [
        ("15 мин", "0.25"),
        ("30 мин", "0.5"),
        ("45 мин", "0.75"),
        ("1 час", "1"),
        ("1.5 часа", "1.5"),
        ("2 часа", "2")
    ]
    
    kb = InlineKeyboardBuilder()
    for text, value in durations:
        kb.button(text=text, callback_data=f"select_duration:{value}")
    
    # Кнопка для ручного ввода
    kb.button(text="⏳ Ввести вручную", callback_data="manual_duration_input")
    kb.adjust(3, 3, 1)
    return kb.as_markup()

def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру подтверждения
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопками подтверждения
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Создать событие", callback_data="confirm_event")
    kb.button(text="✏️ Изменить данные", callback_data="edit_event")
    kb.adjust(1)
    return kb.as_markup()

def get_edit_options_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора редактируемого поля
    Returns:
        InlineKeyboardMarkup: Клавиатура с вариантами редактирования
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="📌 Название", callback_data="edit_title")
    kb.button(text="📅 Дата", callback_data="edit_date")
    kb.button(text="⌚ Время", callback_data="edit_time")
    kb.button(text="⏳ Продолжительность", callback_data="edit_duration")
    kb.button(text="📝 Описание", callback_data="edit_description")
    kb.adjust(1, 2, 2)
    return kb.as_markup()

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой отмены и возврата в меню"""
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отменить", callback_data="cancel_creation")
    kb.button(text="🏠 В меню", callback_data="back_to_menu")
    return kb.as_markup()

def get_description_keyboard() -> InlineKeyboardMarkup:
    """
    Специальная клавиатура для состояния ввода описания
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить описание", callback_data="skip_description")],
        [InlineKeyboardButton(text="❌ Отменить создание", callback_data="cancel_creation")]
    ])

def get_meet_link_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора создания Google Meet ссылки
    """
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, создать ссылку", callback_data="create_meet_link:yes")
    kb.button(text="❌ Нет, не нужно", callback_data="create_meet_link:no")
    kb.adjust(1)
    return kb.as_markup()

def get_auth_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для запроса авторизации"""
    kb = InlineKeyboardBuilder()
    kb.button(text="🔒 Авторизоваться", callback_data="request_auth")
    return kb.as_markup()

def get_main_keyboard() -> InlineKeyboardMarkup:
    """Основная клавиатура с главными командами"""
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Создать встречу", callback_data="create_event")
    kb.button(text="⏭ Следующая встреча", callback_data="next_event")
    kb.button(text="☀️ Сегодня", callback_data="today_events")
    kb.button(text="🌙 Завтра", callback_data="tomorrow_events")
    kb.button(text="🔗 Создать Meet", callback_data="generate_meet")
    kb.adjust(1, 2, 2)
    return kb.as_markup()