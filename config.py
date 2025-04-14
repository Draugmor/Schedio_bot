import pytz
from collections import defaultdict
import os

# Токен бота
API_TOKEN = '7971823219:AAEwiY-2yyY85Fa7DKB0bcuL8X4LRJRMEHI'

# Временная зона
TIMEZONE = pytz.timezone('Europe/Moscow')

# Создаем папку для хранения токенов пользователей
TOKENS_DIR = 'user_tokens'
if not os.path.exists(TOKENS_DIR):
    os.makedirs(TOKENS_DIR)

# Словари для управления состоянием
active_users = {}  # Хранит активных пользователей и их креды
user_settings = defaultdict(int)  # Напоминания по пользователю (в минутах)