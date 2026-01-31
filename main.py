import os
import telebot
import logging
import json
import re
import google.generativeai as genai
from telebot import types
from flask import Flask, request

TOKEN = "TOKEN"
IMAGE_URL = "https://i.ibb.co/MxXv4XGC/Gemini-Generated-Image-wb2747wb2747wb27.png"

# Инициализация ИИ - ИСПРАВЛЕНО НА gemini-1.5-flash
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
ai_model = genai.GenerativeModel('gemini-1.5-flash-latest')

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
    # ИСПРАВЛЕНО: callback_data
    markup.add(types.InlineKeyboardButton(text="Я не робот 🤖", callback_data="pass_captcha"))
    bot.send_message(message.chat.id, "Для доступа к панели управления подтвердите, что вы человек:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "pass_captcha")
def on_captcha(call):
    # Пытаемся ответить Telegram, что мы приняли нажатие
    try:
        bot.answer_callback_query(call.id, "Проверка пройдена!")
    except Exception as e:
        # Если запрос устарел, просто пишем об этом в консоль и идем дальше
        print(f"Запрос устарел, но это не критично: {e}")
    
    # Удаляем сообщение с кнопкой капчи
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

    # Отправляем приветственное фото и меню
    bot.send_photo(
        call.message.chat.id, 
        IMAGE_URL, 
        caption="✨ **Капча пройдена!**\n\nДобро пожаловать в StarBus Admin Panel. Используйте меню ниже для работы с рейсами.",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "Добавить рейс")
def ask_point_a(message):
    user_states[message.chat.id] = {}
    bot.send_message(message.chat.id, "📍 Введите **Пункт А** (отправление):", parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, ask_point_b)

def ask_point_b(message):
    user_states[message.chat.id]['a'] = message.text
    bot.send_message(message.chat.id, "📍 Введите **Пункт Б** (назначение):", parse_mode="Markdown")
    bot.register_next_step_handler(message, ask_stops)

def ask_stops(message):
    user_states[message.chat.id]['b'] = message.text
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Да", "Нет")
    bot.send_message(message.chat.id, "❓ Хотите добавить ТОЧНЫЕ промежуточные пункты?", reply_markup=markup)
    bot.register_next_step_handler(message, ask_time)

def ask_time(message):
    user_states[message.chat.id]['stops_choice'] = message.text
    bot.send_message(message.chat.id, "🕒 Введите время и дату отправления:", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, call_ai_logic)

def call_ai_logic(message):
    chat_id = message.chat.id
    user_states[chat_id]['time'] = message.text
    data = user_states[chat_id]

    bot.send_message(chat_id, "🤖 Нейросеть генерирует маршрут...")

    prompt = f"""
    Пропиши рейс из {data['a']} до {data['b']}. Время: {data['time']}.
    Добавь все адекватные остановки. Укажи корректную цену исходя из рыночных цен.
    В ответе пришли ТОЛЬКО код объекта в формате:
    {{
        id: 'line-{data['a'].lower()}-{data['b'].lower()}',
        stops: ['Город1', 'Город2'],
        times: ['17:00', '20:30'],
        prices: [0, 500],
        schedule: [0, 1, 2, 3, 4, 5, 6],
        busType: 'International Premium',
        busInfo: 'Van Hool (55 місць)',
        amenities: ['wifi', 'ac', 'toilet', 'charger', 'coffee', 'tv'],
        takenSeats: [5, 8, 12]
    }}
    """

    try:
        response = ai_model.generate_content(prompt)
        bot.send_message(chat_id, "✅ **Рейс сгенерирован!**", parse_mode="Markdown")
        bot.send_message(chat_id, f"```javascript\n{response.text}\n```", parse_mode="Markdown", reply_markup=get_main_menu())
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ Ошибка ИИ: {str(e)}", reply_markup=get_main_menu())

@server.route('/' + TOKEN, methods=['POST'])
def get_message():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@server.route("/")
def index():
    return "StarBus Bot is Live", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
