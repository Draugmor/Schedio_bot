import pytz
from collections import defaultdict
import os

# Токен бота
API_TOKEN = '7551196196:AAHa0NSUUa8p-uMVoezLgqWpzxk-SdQroOU'

# Временная зона
TIMEZONE = pytz.timezone('Europe/Moscow')

# Создаем папку для хранения токенов пользователей
TOKENS_DIR = 'user_tokens'
if not os.path.exists(TOKENS_DIR):
    os.makedirs(TOKENS_DIR)

# Словари для управления состоянием
active_users = {}  # Хранит активных пользователей и их креды
user_settings = defaultdict(int)  # Напоминания по пользователю (в минутах)