from aiogram import types
from aiogram.enums import ParseMode
import re

def escape_markdown_v2(text: str) -> str:
    """Экранирует специальные символы для MarkdownV2."""
    escape_chars = r"\_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

async def send_about_info(message: types.Message):
    """Команда для получения информации о боте и его создателе"""
    try:
        # Формируем сообщение с информацией о боте
        about_message = (
            "🤖 *О боте:*\n"
            "Я — Schedio, ваш помощник в управлении встречами и событиями\. "
            "Я интегрирован с Google Calendar и помогу вам:\n"
            "\- Получать уведомления о предстоящих встречах;\n"
            "\- Просматривать события на сегодня, завтра, текущие и следующие;\n"
            "\- Создавать ссылки на Google Meet\.\n\n"
            
            "📜 *Доступные команды:*\n"
            "/start \- Начать работу с ботом\n"
            "/today \- События на сегодня\n"
            "/tomorrow \- События на завтра\n"
            "/now \- Текущая встреча\n"
            "/next \- Следующая встреча\n"
            "/generate\_meet\_link \- Создать ссылку на Google Meet\n\n"
            "/set\_reminder\_0 \- Напоминать о встречах за 0 минут\n"
            "/set\_reminder\_5 \- Напоминать о встречах за 5 минут\n"
            "/set\_reminder\_10 \- Напоминать о встречах за 10 минут\n"
            "/set\_reminder\_15 \- Напоминать о встречах за 15 минут\n\n"
            "/relogin \- Повторная авторизация\n"
            "/logout \- Выйти из аккаунта Google и удалить токен из Schedio\n"
            "/about \- Информация о боте\n\n"
            
            f"💲Отправить донат: [{escape_markdown_v2('Cloudtips')}]({escape_markdown_v2('https://pay.cloudtips.ru/p/2258c26e')})\n\n"

            "👨‍💻 *Связь с создателем:*\n"
            "Если у вас есть вопросы или предложения, напишите мне:\n"
            f"\- Telegram: [{escape_markdown_v2('@IlyaDoroshev')}]({escape_markdown_v2('https://t.me/IlyaDoroshev')})\n"
            f"\- Email\: {escape_markdown_v2('feedback@schedio.ru')}\n\n"
            "Спасибо, что используете *Schedio*\! ❤️"
        )

        # Отправляем сообщение пользователю
        await message.reply(
            text=about_message,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True  # Отключаем предпросмотр ссылок
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)}")