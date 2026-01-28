import os
import telebot
from flask import Flask, request

TOKEN = "8510832683:AAHMvIzskXXu0IaJHgV4m3O1BRbu8HJCfd4"
bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "Python-бот на Render запущен и готов к работе!")

@server.route('/' + TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@server.route("/")
def webhook():
    bot.remove_webhook()
    # Сюда вставим твой URL от Render чуть позже
    return "Бот активен", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
