import os
import telebot
import logging
from flask import Flask, request

# Твой токен
TOKEN = "8510832683:AAHMvIzskXXu0IaJHgV4m3O1BRbu8HJCfd4"

# 1. Включаем подробные логи, чтобы видеть ошибки в консоли Render
telebot.logger.setLevel(logging.DEBUG)

bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)

# 2. Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    print(f"LOG: Получена команда START от {message.chat.id}") # Пишем в консоль
    try:
        bot.reply_to(message, "Привет! Бот видит тебя. Связь установлена ✅")
    except Exception as e:
        print(f"LOG: Ошибка при отправке ответа: {e}")

# 3. Обработчик ВСЕХ остальных сообщений (эхо)
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    print(f"LOG: Получено сообщение: {message.text}")
    bot.reply_to(message, f"Я получил твоё сообщение: {message.text}")

# 4. Точка входа для Telegram (Webhook)
@server.route('/' + TOKEN, methods=['POST'])
def getMessage():
    try:
        # Получаем данные
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        
        # Передаем боту на обработку
        bot.process_new_updates([update])
        return "!", 200
    except Exception as e:
        print(f"LOG: Ошибка внутри Webhook: {e}")
        return "Error", 500

# 5. Главная страница (для проверки в браузере)
@server.route("/")
def webhook():
    return "Бот работает! Жду сообщений в Telegram.", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
