import os
import telebot
import logging
import json
import re
import google.generativeai as genai
from telebot import types
from flask import Flask, request
import sys

# --- НАСТРОЙКИ ---
# Чтобы логи появлялись мгновенно
sys.stdout.reconfigure(encoding='utf-8')

# Токены
TOKEN = os.getenv("TOKENBOT")
API_KEY = os.getenv("GEMINI_API_KEY")
IMAGE_URL = "https://i.ibb.co/MxXv4XGC/Gemini-Generated-Image-wb2747wb2747wb27.png"

# Настраиваем Gemini
genai.configure(api_key=API_KEY)

# Инициализируем бота
bot = telebot.TeleBot(TOKEN, threaded=False)
server = Flask(__name__)
user_states = {}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def log(message):
    """Вывод в консоль Render без задержек"""
    print(f"[LOG] {message}")
    sys.stdout.flush()

def get_ai_response(prompt):
    """Функция, которая перебирает модели, пока не сработает"""
    # Список моделей от новой к старой
    models_to_try = ['gemini-1.5-flash', 'gemini-pro', 'gemini-1.0-pro']
    
    for model_name in models_to_try:
        try:
            log(f"Пробую модель: {model_name}")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text, model_name
        except Exception as e:
            log(f"Модель {model_name} не сработала: {e}")
            continue
            
    return None, "Все модели недоступны"

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Добавить рейс", "Поддержка")
    markup.add("Добавить домен", "Мануал")
    return markup

# --- ОБРАБОТЧИКИ БОТА ---

@bot.message_handler(commands=['start'])
def start_cmd(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="Я не робот 🤖", callback_data="pass_captcha"))
    bot.send_message(message.chat.id, "Для доступа к панели подтвердите, что вы человек:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "pass_captcha")
def on_captcha(call):
    try:
        bot.answer_callback_query(call.id, "Успешно!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass # Игнорируем ошибки удаления старых кнопок

    bot.send_photo(
        call.message.chat.id, 
        IMAGE_URL, 
        caption="✨ **Капча пройдена!**\n\nДобро пожаловать в StarBus Admin Panel.",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "Добавить рейс")
def ask_point_a(message):
    user_states[message.chat.id] = {}
    bot.send_message(message.chat.id, "📍 Введите **Пункт А** (откуда):", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, ask_point_b)

def ask_point_b(message):
    user_states[message.chat.id]['a'] = message.text
    bot.send_message(message.chat.id, "📍 Введите **Пункт Б** (куда):", parse_mode="Markdown")
    bot.register_next_step_handler(message, ask_stops)

def ask_stops(message):
    user_states[message.chat.id]['b'] = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Да", "Нет")
    bot.send_message(message.chat.id, "❓ Добавить точные промежуточные пункты?", reply_markup=markup)
    bot.register_next_step_handler(message, ask_time)

def ask_time(message):
    user_states[message.chat.id]['stops_choice'] = message.text
    bot.send_message(message.chat.id, "🕒 Введите дату и время отправления:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, call_ai_logic)

def call_ai_logic(message):
    chat_id = message.chat.id
    user_states[chat_id]['time'] = message.text
    data = user_states[chat_id]

    bot.send_message(chat_id, "🤖 Думаю... (перебираю доступные модели)")

    # Жесткий промпт, чтобы старая модель не болтала лишнего
    prompt = f"""
    Ты диспетчер автобусных рейсов.
    Задача: Создать JSON объект для рейса {data['a']} - {data['b']}.
    Время отправления: {data['time']}.
    
    1. Придумай 5-7 реальных промежуточных городов между этими точками.
    2. Придумай реальное расписание (время прибытия в каждый город).
    3. Придумай цены (от 0 до рыночной цены в конце).
    4. ОТВЕТЬ ТОЛЬКО ЧИСТЫМ JSON КОДОМ. БЕЗ MARKDOWN. БЕЗ СЛОВ "ВОТ JSON".
    
    Формат JSON:
    {{
        "id": "line-{data['a']}-{data['b']}",
        "stops": ["Город1", "Город2"],
        "times": ["10:00", "12:30"],
        "prices": [0, 500],
        "schedule": [0, 1, 2, 3, 4, 5, 6],
        "busType": "International Premium",
        "busInfo": "Van Hool (50 мест)",
        "amenities": ["wifi", "ac", "wc"],
        "takenSeats": [1, 2]
    }}
    """

    result_text, used_model = get_ai_response(prompt)

    if result_text:
        # Чистим ответ от возможных ```json ... ```
        clean_json = result_text.replace("```json", "").replace("```", "").strip()
        
        bot.send_message(chat_id, f"✅ **Готово!** (Использована модель: `{used_model}`)", parse_mode="Markdown")
        bot.send_message(chat_id, f"```javascript\n{clean_json}\n```", parse_mode="Markdown", reply_markup=get_main_menu())
    else:
        bot.send_message(chat_id, f"❌ Не удалось сгенерировать ответ. Ошибка: {used_model}", reply_markup=get_main_menu())

# --- SERVER ---
@server.route('/' + TOKEN, methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@server.route("/")
def index():
    return "Bot is running", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
