import os
import telebot
import google.generativeai as genai
from telebot import types
from flask import Flask, request
import sys

# Принудительный вывод логов
sys.stdout.reconfigure(encoding='utf-8')

TOKEN = os.getenv("TOKENBOT")
API_KEY = os.getenv("GEMINI_API_KEY")
IMAGE_URL = "https://i.ibb.co/MxXv4XGC/Gemini-Generated-Image-wb2747wb2747wb27.png"

# Настройка ИИ
genai.configure(api_key=API_KEY)

# Автоподбор рабочей модели
def get_working_model():
    try:
        print("--- Проверка доступных моделей ---")
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        print(f"Доступно: {available}")
        
        # Приоритет выбора
        for target in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']:
            if target in available:
                print(f"Выбрана модель: {target}")
                return genai.GenerativeModel(target)
        
        # Если ничего из списка не нашли, берем первую попавшуюся
        return genai.GenerativeModel(available[0])
    except Exception as e:
        print(f"Ошибка при поиске моделей: {e}")
        # Фолбэк на стандарт, если list_models упал
        return genai.GenerativeModel('gemini-1.5-flash')

model = get_working_model()

bot = telebot.TeleBot(TOKEN, threaded=False)
server = Flask(__name__)
user_states = {}

# --- КЛАВИАТУРЫ ---
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Добавить рейс", "Поддержка")
    markup.add("Добавить домен", "Мануал")
    return markup

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    markup = types.InlineKeyboardMarkup()
    # ИСПОЛЬЗУЕМ ТОЛЬКО callback_data ДЛЯ ИНЛАЙН КНОПОК
    markup.add(types.InlineKeyboardButton(text="Я не робот 🤖", callback_data="pass_captcha"))
    bot.send_message(message.chat.id, "Подтвердите, что вы человек:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "pass_captcha")
def on_captcha(call):
    try:
        bot.answer_callback_query(call.id)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    bot.send_photo(call.message.chat.id, IMAGE_URL, caption="✨ Доступ открыт!", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: m.text == "Добавить рейс")
def ask_point_a(message):
    user_states[message.chat.id] = {}
    bot.send_message(message.chat.id, "📍 Откуда отправляемся?", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, ask_point_b)

def ask_point_b(message):
    user_states[message.chat.id]['a'] = message.text
    bot.send_message(message.chat.id, "📍 Куда едем?")
    bot.register_next_step_handler(message, ask_time)

def ask_time(message):
    user_states[message.chat.id]['b'] = message.text
    bot.send_message(message.chat.id, "🕒 Дата и время:")
    bot.register_next_step_handler(message, call_ai)

def call_ai(message):
    chat_id = message.chat.id
    time_info = message.text
    data = user_states[chat_id]
    
    bot.send_message(chat_id, "🤖 Нейросеть генерирует маршрут...")

    prompt = f"Создай JSON для рейса {data['a']} - {data['b']}, выезд {time_info}. 5 остановок. Только чистый JSON по шаблону: {{'stops': [], 'times': [], 'prices': []}}"

    try:
        response = model.generate_content(prompt)
        if response.text:
            res = response.text.replace("```json", "").replace("```", "").strip()
            bot.send_message(chat_id, "✅ Рейс сгенерирован!")
            bot.send_message(chat_id, f"```javascript\n{res}\n```", parse_mode="Markdown", reply_markup=get_main_menu())
    except Exception as e:
        bot.send_message(chat_id, f"❌ Ошибка ИИ: {str(e)}", reply_markup=get_main_menu())

# --- SERVER ---
@server.route('/' + TOKEN, methods=['POST'])
def get_message():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@server.route("/")
def index(): return "Status: Online", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
