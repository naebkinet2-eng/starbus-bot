import os
import telebot
import google.generativeai as genai
from telebot import types
from flask import Flask, request
import sys
import json
import re
import ftplib

# --- НАСТРОЙКИ ---
sys.stdout.reconfigure(encoding='utf-8')

def log(msg):
    print(f"[LOG] {msg}", flush=True)

TOKEN = os.getenv("TOKENBOT")
API_KEY = os.getenv("GEMINI_API_KEY")

# Настройка старой доброй библиотеки
genai.configure(api_key=API_KEY)

# ВНИМАНИЕ: Если 'gemini-1.5-flash' дает 404, попробуй 'gemini-pro'
# Но Flash должен работать, если в названии нет лишних приставок
model = genai.GenerativeModel('gemini-1.5-flash')

bot = telebot.TeleBot(TOKEN, threaded=False)
server = Flask(__name__)
user_states = {}
IMAGE_URL = "https://i.ibb.co/MxXv4XGC/Gemini-Generated-Image-wb2747wb2747wb27.png"

# Настройки FTP
FTP_HOST = os.getenv('FTP_HOST')
FTP_USER = os.getenv('FTP_USER')
FTP_PASS = os.getenv('FTP_PASS')
DATA_FILE = "htdocs/CITY1.js" 
HTML_FILE = "htdocs/index.html"

# --- ИНИЦИАЛИЗАЦИЯ GEMINI ---
# Мы убираем http_options v1beta, так как новый SDK сам выбирает рабочий маршрут.
# Если 404 сохраняется, библиотека v2 лучше всего работает с коротким ID.
try:
    client = genai.Client(api_key=API_KEY)
    MODEL_ID = "gemini-1.5-flash"
    log("Клиент Gemini успешно инициализирован")
except Exception as e:
    log(f"Ошибка при инициализации клиента: {e}")

bot = telebot.TeleBot(TOKEN, threaded=False)
server = Flask(__name__)
user_states = {}
# --- КЛАВИАТУРЫ ---
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Добавить рейс", "Поддержка")
    markup.add("Добавить домен", "Мануал")
    return markup

# --- СТАРТ И КАПЧА ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="Я не робот 🤖", callback_data="pass_captcha"))
    bot.send_message(message.chat.id, "Для доступа подтвердите, что вы человек:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "pass_captcha")
def on_captcha(call):
    try:
        bot.answer_callback_query(call.id)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    bot.send_photo(call.message.chat.id, IMAGE_URL, caption="✨ **Панель управления StarBus**", reply_markup=get_main_menu())

# --- ЛОГИКА ОПРОСА ---

@bot.message_handler(func=lambda m: m.text == "Добавить рейс")
def start_add(message):
    user_states[message.chat.id] = {}
    bot.send_message(message.chat.id, "📍 Введите **Пункт А** (Откуда):", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, ask_point_b)

def ask_point_b(message):
    user_states[message.chat.id]['a'] = message.text
    bot.send_message(message.chat.id, "📍 Введите **Пункт Б** (Куда):", parse_mode="Markdown")
    bot.register_next_step_handler(message, ask_stops_q)

def ask_stops_q(message):
    user_states[message.chat.id]['b'] = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Да", "Нет")
    bot.send_message(message.chat.id, "🚏 Хотите добавить **обязательные** промежуточные остановки?", parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(message, process_stops_decision)

def process_stops_decision(message):
    if message.text.lower() == "да":
        bot.send_message(message.chat.id, "Напишите города через запятую:", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, save_stops_and_ask_time)
    else:
        user_states[message.chat.id]['stops'] = "Подбери логичные крупные города сам"
        ask_time_q(message)

def save_stops_and_ask_time(message):
    user_states[message.chat.id]['stops'] = message.text
    ask_time_q(message)

def ask_time_q(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Указать вручную", "Пусть решит ИИ")
    bot.send_message(message.chat.id, "🕒 Указать точное время отправления?", reply_markup=markup)
    bot.register_next_step_handler(message, process_time_decision)

def process_time_decision(message):
    if "вручную" in message.text.lower():
        bot.send_message(message.chat.id, "Напишите время (Пн, Ср в 18:00):", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, save_time_and_ask_price)
    else:
        user_states[message.chat.id]['time'] = "Вечерний рейс, ежедневно"
        ask_price_q(message)

def save_time_and_ask_price(message):
    user_states[message.chat.id]['time'] = message.text
    ask_price_q(message)

def ask_price_q(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Указать вручную", "Рыночная цена")
    bot.send_message(message.chat.id, "💰 Указать точную цену билета?", reply_markup=markup)
    bot.register_next_step_handler(message, process_price_decision)

def process_price_decision(message):
    if "вручную" in message.text.lower():
        bot.send_message(message.chat.id, "Введите цену в ГРН:", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, call_ai) # Здесь по умолчанию manual_price=True
    else:
        user_states[message.chat.id]['price'] = "Рассчитай рыночную в UAH"
        call_ai(message, manual_price=False) # Теперь функция примет этот аргумент

def call_ai(message, manual_price=True):
    chat_id = message.chat.id
    if manual_price:
        user_states[chat_id]['price'] = message.text
    
    data = user_states.get(chat_id)
    if not data:
        bot.send_message(chat_id, "❌ Ошибка сессии.")
        return

    bot.send_message(chat_id, "🤖 Нейросеть генерирует маршрут...")

    prompt = f"""
    Ты бэкенд-разработчик транспортной компании.
    Задача: Сгенерировать JSON объект, содержащий 3 части данных для сайта.
    
    Входные данные:
    - Маршрут: {data['a']} -> {data['b']}
    - Обязательные остановки: {data['stops']}
    - Время/Расписание: {data['time']}
    - Цена/Инструкция: {data['price']} (Валюта: UAH)

    ТРЕБОВАНИЯ К ФОРМАТУ (СТРОГО):
    Верни ОДИН JSON объект с тремя ключами: "new_cities", "route", "stations".

    1. "new_cities": Объект, где ключи - названия городов на английском/транслите (например 'Lviv', 'Kyiv'), а значения - координаты {{lat: ..., lng: ...}}. Добавь ВСЕ города маршрута.
    2. "route": Объект рейса. 
       - id: 'line-citya-cityb' (на английском)
       - stops: Массив названий городов на местном языке (например ['Київ', 'Житомир', ...]).
       - times: Массив времени. Если переход через полночь, пиши '+1 06:00'.
       - prices: Массив НАКОПИТЕЛЬНОЙ цены в гривнах. Начало 0, конец - полная цена. [0, 300, 800, ..., {data['price'] if 'UAH' not in data['price'] else 'полная_цена'}].
       - schedule: Массив дней [0,1,2,3,4,5,6].
       - busInfo: 'Van Hool (55 місць)'.
    3. "stations": Объект названий вокзалов для каждого города. 
       - Ключ: Название города (как в stops). 
       - Значение: {{ uk: '...', ru: '...', en: '...' }}.

    ПРИМЕР ОТВЕТА (JSON):
    {{
      "new_cities": {{ "Kyiv": {{ "lat": 50.45, "lng": 30.52 }} }},
      "route": {{ "id": "line-kyiv-lviv", "stops": ["Київ", "Львів"], "times": ["10:00", "18:00"], "prices": [0, 800], "busType": "Premium", "schedule": [0,1], "amenities": ["wifi"] }},
      "stations": {{ "Київ": {{ "uk": "Автовокзал", "ru": "Автовокзал", "en": "Bus Station" }} }}
    }}
    """
    try:
        # Это та самая версия генерации, где не было 404
        # Мы просто добавили таймаут, чтобы она не висела
        response = model.generate_content(
            prompt,
            request_options={'timeout': 30}
        )
        
        if not response or not response.text:
            raise Exception("Пустой ответ от ИИ")

        raw_text = response.text
        # Чистим JSON от Markdown
        clean_text = re.sub(r'```json|```javascript|```', '', raw_text).strip()
        result_json = json.loads(clean_text)
        
        user_states[chat_id]['generated_data'] = result_json

        # Вывод данных
        cities_js = "const citiesDatabase = " + json.dumps(result_json['new_cities'], indent=4, ensure_ascii=False) + ";"
        bot.send_message(chat_id, f"🏙 **Часть 1: Города**\n```javascript\n{cities_js}\n```", parse_mode="Markdown")

        route_js = json.dumps(result_json['route'], indent=4, ensure_ascii=False)
        bot.send_message(chat_id, f"🚌 **Часть 2: Маршрут**\n```javascript\n{route_js}\n```", parse_mode="Markdown")

        stations_js = "const stationNames = " + json.dumps(result_json['stations'], indent=4, ensure_ascii=False) + ";"
        bot.send_message(chat_id, f"🏢 **Часть 3: Вокзалы**\n```javascript\n{stations_js}\n```", parse_mode="Markdown")

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Добавить маршрут на сайт", callback_data="upload_route"))
        bot.send_message(chat_id, "✨ Готово! Проверь и нажимай кнопку.", reply_markup=markup)

  except Exception as e:
        log(f"Ошибка ИИ: {e}")
        # Добавлена недостающая скобка в конце:
        bot.send_message(chat_id, f"⚠️ Ошибка: {str(e)}", reply_markup=get_main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "upload_route")
def upload_route_handler(call):
    chat_id = call.message.chat.id
    data = user_states[chat_id].get('generated_data')
    if not data: return
    
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    bot.send_message(chat_id, "⏳ Подключаюсь к FTP...")

    try:
        ftp = ftplib.FTP(FTP_HOST)
        ftp.login(FTP_USER, FTP_PASS)
        
        # 1. Обновление CITY1.js
        lines = []
        ftp.retrlines(f'RETR {DATA_FILE}', lines.append)
        js_content = "\n".join(lines)

        # Проверка ID
        if f"id: '{data['route']['id']}'" in js_content:
            bot.send_message(chat_id, "⚠️ Такой ID уже есть на сайте!")
            ftp.quit(); return

        # Инъекции данных
        new_cities = json.dumps(data['new_cities'], ensure_ascii=False)[1:-1]
        js_content = re.sub(r'(const citiesDatabase\s*=\s*\{)', r'\1\n' + new_cities + ',', js_content)
        
        new_stations = json.dumps(data['stations'], ensure_ascii=False)[1:-1]
        js_content = re.sub(r'(const stationNames\s*=\s*\{)', r'\1\n' + new_stations + ',', js_content)
        
        new_route = json.dumps(data['route'], ensure_ascii=False)
        js_content = re.sub(r'(const trunkRoutes\s*=\s*\[)', r'\1\n' + new_route + ',', js_content)

        with open("temp.js", "w", encoding="utf-8") as f: f.write(js_content)
        with open("temp.js", "rb") as f: ftp.storbinary(f'STOR {DATA_FILE}', f)

        # 2. Обновление версии в index.html
        html_lines = []
        ftp.retrlines(f'RETR {HTML_FILE}', html_lines.append)
        html_content = "\n".join(html_lines)
        
        new_html = re.sub(r'\?v=(\d+)', lambda m: f"?v={int(m.group(1))+1}", html_content)
        
        with open("temp.html", "w", encoding="utf-8") as f: f.write(new_html)
        with open("temp.html", "rb") as f: ftp.storbinary(f'STOR {HTML_FILE}', f)

        ftp.quit()
        bot.send_message(chat_id, "✅ Рейс успешно добавлен и версия сайта обновлена!", reply_markup=get_main_menu())

    except Exception as e:
        log(f"FTP Error: {e}")
        bot.send_message(chat_id, f"❌ Ошибка FTP: {e}")

# --- ЗАПУСК ---
@server.route('/' + TOKEN, methods=['POST'])
def get_message():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@server.route("/")
def index(): return "StarBus Admin Online", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
