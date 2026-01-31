import os
import telebot
import google.generativeai as genai
from telebot import types
from flask import Flask, request
import sys

# Настройка логирования
sys.stdout.reconfigure(encoding='utf-8')

TOKEN = os.getenv("TOKENBOT")
API_KEY = os.getenv("GEMINI_API_KEY")
IMAGE_URL = "https://i.ibb.co/MxXv4XGC/Gemini-Generated-Image-wb2747wb2747wb27.png"

# Инициализация Gemini
genai.configure(api_key=API_KEY)
# Используем стабильную модель 1.5 Flash
model = genai.GenerativeModel('gemini-1.5-flash')

bot = telebot.TeleBot(TOKEN, threaded=False)
server = Flask(__name__)
user_states = {}

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Добавить рейс", "Поддержка")
    markup.add("Добавить домен", "Мануал")
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="Я не робот 🤖", callback_data="pass_captcha"))
    bot.send_message(message.chat.id, "Для доступа к панели подтвердите, что вы человек:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "pass_captcha")
def on_captcha(call):
    try:
        bot.answer_callback_query(call.id)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    bot.send_photo(call.message.chat.id, IMAGE_URL, caption="✨ **Доступ разрешен!**", parse_mode="Markdown", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: m.text == "Добавить рейс")
def ask_point_a(message):
    user_states[message.chat.id] = {}
    bot.send_message(message.chat.id, "📍 Откуда едем? (Пункт А):", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, ask_point_b)

def ask_point_b(message):
    user_states[message.chat.id]['a'] = message.text
    bot.send_message(message.chat.id, "📍 Куда едем? (Пункт Б):")
    bot.register_next_step_handler(message, ask_time)

def ask_time(message):
    user_states[message.chat.id]['b'] = message.text
    bot.send_message(message.chat.id, "🕒 Укажите дату и время:")
    bot.register_next_step_handler(message, call_ai)

def call_ai(message):
    chat_id = message.chat.id
    time_info = message.text
    data = user_states[chat_id]
    
    bot.send_message(chat_id, "🤖 Генерирую маршрут через Gemini 1.5 Flash...")

    prompt = f"""
    Создай JSON для автобусного рейса {data['a']} - {data['b']}, выезд {time_info}.
    Добавь 5 остановок, время и рыночные цены. 
    Ответ дай ТОЛЬКО в формате JSON:
    {{
        "id": "line-1",
        "stops": ["...", "..."],
        "times": ["...", "..."],
        "prices": [0, 500, ...],
        "busType": "Premium",
        "busInfo": "Van Hool (50 мест)",
        "amenities": ["wifi", "ac", "wc"],
        "schedule": [0,1,2,3,4,5,6],
        "takenSeats": [1, 5, 10]
    }}
    """

    try:
        # Прямой вызов без лишних наворотов
        response = model.generate_content(prompt)
        
        if response and response.text:
            # Убираем возможные артефакты Markdown
            clean_json = response.text.replace("```json", "").replace("```", "").strip()
            bot.send_message(chat_id, "✅ **Рейс успешно создан!**", parse_mode="Markdown")
            bot.send_message(chat_id, f"```javascript\n{clean_json}\n```", parse_mode="Markdown", reply_markup=get_main_menu())
        else:
            bot.send_message(chat_id, "❌ ИИ вернул пустой ответ. Попробуйте еще раз.", reply_markup=get_main_menu())

    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        bot.send_message(chat_id, f"❌ Ошибка: {str(e)}\n\nПроверьте, не заблокирован ли ваш API ключ или регион.", reply_markup=get_main_menu())

# --- RUN ---
@server.route('/' + TOKEN, methods=['POST'])
def get_message():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@server.route("/")
def index(): return "OK", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
