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
TOKEN = os.getenv("TOKENBOT")
API_KEY = os.getenv("GEMINI_API_KEY")
IMAGE_URL = "https://i.ibb.co/MxXv4XGC/Gemini-Generated-Image-wb2747wb2747wb27.png"

# Настройки FTP
FTP_HOST = os.getenv('FTP_HOST')
FTP_USER = os.getenv('FTP_USER')
FTP_PASS = os.getenv('FTP_PASS')
# Имя файла с данными и HTML файла, где меняем версию
DATA_FILE = "htdocs/CITY1.js" 
HTML_FILE = "htdocs/index.html"

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(model_name='models/gemini-1.5-flash')

bot = telebot.TeleBot(TOKEN, threaded=False)
server = Flask(__name__)
user_states = {}

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def log(msg):
    print(f"[LOG] {msg}")
    sys.stdout.flush()

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
    bot.send_photo(call.message.chat.id, IMAGE_URL, caption="✨ **Панель управления StarBus**\nВыбери действие:", parse_mode="Markdown", reply_markup=get_main_menu())

# --- ЛОГИКА ОПРОСА (STEP-BY-STEP) ---

@bot.message_handler(func=lambda m: m.text == "Добавить рейс")
def start_add(message):
    user_states[message.chat.id] = {}
    bot.send_message(message.chat.id, "📍 Введите **Пункт А** (Откуда):", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, ask_point_b)

def ask_point_b(message):
    user_states[message.chat.id]['a'] = message.text
    bot.send_message(message.chat.id, "📍 Введите **Пункт Б** (Куда):", parse_mode="Markdown")
    bot.register_next_step_handler(message, ask_stops_q)

# Промежуточные остановки
def ask_stops_q(message):
    user_states[message.chat.id]['b'] = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Да", "Нет")
    bot.send_message(message.chat.id, "🚏 Хотите добавить **обязательные** промежуточные остановки?", parse_mode="Markdown", reply_markup=markup)
    bot.register_next_step_handler(message, process_stops_decision)

def process_stops_decision(message):
    if message.text.lower() == "да":
        bot.send_message(message.chat.id, "Напишите названия городов через запятую (например: Житомир, Ровно):", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, save_stops_and_ask_time)
    else:
        user_states[message.chat.id]['stops'] = "Подбери логичные крупные города сам"
        ask_time_q(message)

def save_stops_and_ask_time(message):
    user_states[message.chat.id]['stops'] = message.text
    ask_time_q(message)

# Время
def ask_time_q(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Указать вручную", "Пусть решит ИИ")
    bot.send_message(message.chat.id, "🕒 Хотите указать точное время и дни отправления?", reply_markup=markup)
    bot.register_next_step_handler(message, process_time_decision)

def process_time_decision(message):
    if "вручную" in message.text.lower():
        bot.send_message(message.chat.id, "Напишите время и дни (например: Ежедневно в 18:00):", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, save_time_and_ask_price)
    else:
        user_states[message.chat.id]['time'] = "Вечерний рейс, прибытие утром. Ежедневно."
        ask_price_q(message)

def save_time_and_ask_price(message):
    user_states[message.chat.id]['time'] = message.text
    ask_price_q(message)

# Цена
def ask_price_q(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Указать вручную", "Рыночная цена")
    bot.send_message(message.chat.id, "💰 Хотите указать точную цену билета?", reply_markup=markup)
    bot.register_next_step_handler(message, process_price_decision)

def process_price_decision(message):
    if "вручную" in message.text.lower():
        bot.send_message(message.chat.id, "Напишите цену в гривнах (например: 2200):", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, run_ai_generation)
    else:
        user_states[message.chat.id]['price'] = "Рассчитай рыночную цену в Гривнах (UAH)"
        # Переходим к генерации, так как message уже содержит ответ
        # Но нам нужен текст, поэтому просто вызываем функцию
        run_ai_generation(message, manual_price=False)

def run_ai_generation(message, manual_price=True):
    chat_id = message.chat.id
    if manual_price:
        user_states[chat_id]['price'] = message.text
    
    data = user_states[chat_id]
    bot.send_message(chat_id, "🤖 **Генерирую данные...**\n(Это может занять 10-15 секунд)", parse_mode="Markdown", reply_markup=get_main_menu())

    # --- ПРОМПТ ДЛЯ ИИ ---
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


def call_ai(message):
    chat_id = message.chat.id
    data = user_states.get(chat_id)
    if not data:
        bot.send_message(chat_id, "❌ Ошибка: сессия потеряна. Начните заново.")
        return

    log(f"--- ЗАПУСК ГЕНЕРАЦИИ ДЛЯ {chat_id} ---")
    bot.send_message(chat_id, "🤖 Начинаю генерацию... (Шаг 1: Запрос к Google)")

    prompt = f"""
    Сгенерируй JSON для автобусного рейса {data['a']} - {data['b']}.
    Остановки: {data.get('stops', 'на твой выбор')}. 
    Цена: {data.get('price', 'рыночная')}. 
    Верни ТОЛЬКО JSON с ключами 'new_cities', 'route', 'stations'.
    """

    try:
        log("Отправка промпта в Google Gemini...")
        # Устанавливаем короткий таймаут, чтобы не ждать вечно
        response = model.generate_content(prompt, request_options={"timeout": 40})
        
        log("Ответ от Google получен!")
        
        if not response or not response.text:
            log("Критическая ошибка: Ответ пустой!")
            bot.send_message(chat_id, "⚠️ ИИ вернул пустой ответ.")
            return

        log("Очистка и парсинг JSON...")
        raw_text = response.text
        # Чистим от markdown
        clean_text = re.sub(r'```json|```javascript|```', '', raw_text).strip()
        
        result_json = json.loads(clean_text)
        user_states[chat_id]['generated_data'] = result_json
        log("JSON успешно распарсен!")

        # Вывод данных в чат
        cities_str = json.dumps(result_json['new_cities'], indent=2, ensure_ascii=False)
        bot.send_message(chat_id, f"🏙 **Города:**\n```javascript\nconst citiesDatabase = {cities_str};\n```", parse_mode="Markdown")

        route_str = json.dumps(result_json['route'], indent=2, ensure_ascii=False)
        bot.send_message(chat_id, f"🚌 **Маршрут:**\n```javascript\n{route_str}\n```", parse_mode="Markdown")

        stations_str = json.dumps(result_json['stations'], indent=2, ensure_ascii=False)
        bot.send_message(chat_id, f"🏢 **Вокзалы:**\n```javascript\nconst stationNames = {stations_str};\n```", parse_mode="Markdown")

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Добавить маршрут на сайт", callback_data="upload_route"))
        bot.send_message(chat_id, "✨ Готово! Проверь данные и жми кнопку.", reply_markup=markup)

    except Exception as e:
        log(f"ОШИБКА В call_ai: {e}")
        bot.send_message(chat_id, f"❌ Произошла ошибка: {str(e)}", reply_markup=get_main_menu())
        
# --- ЛОГИКА FTP (ЗАГРУЗКА) ---

@bot.callback_query_handler(func=lambda call: call.data == "upload_route")
def upload_route_handler(call):
    chat_id = call.message.chat.id
    if 'generated_data' not in user_states.get(chat_id, {}):
        bot.answer_callback_query(call.id, "Данные устарели. Сгенерируйте заново.")
        return

    data = user_states[chat_id]['generated_data']
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None) # Убираем кнопку
    bot.send_message(chat_id, "⏳ Подключаюсь к серверу...")

    try:
        ftp = ftplib.FTP(FTP_HOST)
        ftp.login(FTP_USER, FTP_PASS)
        
        # 1. Скачиваем data.js
        lines = []
        ftp.retrlines(f'RETR {DATA_FILE}', lines.append)
        js_content = "\n".join(lines)

        # 2. Проверка дубликатов
        new_id = data['route']['id']
        if f"id: '{new_id}'" in js_content or f'id: "{new_id}"' in js_content:
            bot.send_message(chat_id, f"⚠️ Маршрут с ID `{new_id}` уже есть на сайте! Отмена.", parse_mode="Markdown")
            ftp.quit()
            return

        # 3. Инъекция данных (Самая хитрая часть)
        # Добавляем города в citiesDatabase
        # Ищем закрывающую скобку citiesDatabase };
        new_cities_str = json.dumps(data['new_cities'], ensure_ascii=False)[1:-1] # убираем {}
        if new_cities_str:
            js_content = re.sub(r'(const citiesDatabase\s*=\s*\{[\s\S]*?)(\};)', r'\1,\n' + new_cities_str + r'\n\2', js_content, count=1)

        # Добавляем станции в stationNames
        new_stations_str = json.dumps(data['stations'], ensure_ascii=False)[1:-1]
        if new_stations_str:
            js_content = re.sub(r'(const stationNames\s*=\s*\{[\s\S]*?)(\};)', r'\1,\n' + new_stations_str + r'\n\2', js_content, count=1)

        # Добавляем маршрут в trunkRoutes
        # Формируем строку JS объекта для массива
        new_route_js = json.dumps(data['route'], ensure_ascii=False)
        # Находим закрывающую скобку массива trunkRoutes ];
        js_content = re.sub(r'(const trunkRoutes\s*=\s*\[[\s\S]*?)(\];)', r'\1,\n' + new_route_js + r'\n\2', js_content, count=1)

        # Сохраняем и грузим data.js
        with open("temp_data.js", "w", encoding="utf-8") as f: f.write(js_content)
        with open("temp_data.js", "rb") as f: ftp.storbinary(f'STOR {DATA_FILE}', f)

        # 4. Обновление версии в index.html
        lines_html = []
        try:
            ftp.retrlines(f'RETR {HTML_FILE}', lines_html.append)
            html_content = "\n".join(lines_html)
            
            # Ищем v=8 и меняем на v=9
            def version_replacer(match):
                ver = int(match.group(1))
                return f'.js?v={ver + 1}'
            
            new_html = re.sub(r'\.js\?v=(\d+)', version_replacer, html_content)
            
            with open("temp_index.html", "w", encoding="utf-8") as f: f.write(new_html)
            with open("temp_index.html", "rb") as f: ftp.storbinary(f'STOR {HTML_FILE}', f)
            
            html_status = "Версия сайта обновлена (+1)."
        except Exception as html_e:
            html_status = f"Не удалось обновить версию HTML: {html_e}"

        ftp.quit()
        bot.send_message(chat_id, f"✅ **УСПЕХ!**\n\n1. Маршрут добавлен в `data.js`.\n2. Новые города и вокзалы прописаны.\n3. {html_status}", parse_mode="Markdown")

    except Exception as e:
        log(f"FTP Error: {e}")
        bot.send_message(chat_id, f"❌ Ошибка FTP: {str(e)}")

# --- ЗАПУСК ---
@server.route('/' + TOKEN, methods=['POST'])
def get_message():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@server.route("/")
def index(): return "StarBus Admin v2.0", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
