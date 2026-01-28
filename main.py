import os
import telebot
import logging
from flask import Flask, request

TOKEN = "8510832683:AAHMvIzskXXu0IaJHgV4m3O1BRbu8HJCfd4"

# Включаем логи, чтобы видеть всё
telebot.logger.setLevel(logging.DEBUG)

# ВАЖНО: threaded=False заставляет бота отвечать СРАЗУ, не создавая новых потоков
bot = telebot.TeleBot(TOKEN, threaded=False)
server = Flask(__name__)

@bot.message_handler(commands=['start'])
def start(message):
    try:
        # Сразу шлем ответ
        bot.reply_to(message, f"Привет! Я живой! Твой ID: {message.chat.id}")
    except Exception as e:
        print(f"Ошибка отправки: {e}")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"Эхо: {message.text}")

@server.route('/' + TOKEN, methods=['POST'])
def getMessage():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        
        # Обрабатываем сообщение здесь и сейчас
        bot.process_new_updates([update])
        
        return "!", 200
    except Exception as e:
        print(f"Ошибка в Webhook: {e}")
        return "Error", 500

@server.route("/")
def webhook():
    return "Бот работает", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
