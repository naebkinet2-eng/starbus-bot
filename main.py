import os
import telebot
import ftplib
import re
from flask import Flask, request

TOKEN = "8510832683:AAHMvIzskXXu0IaJHgV4m3O1BRbu8HJCfd4"
ADMIN_ID = 8125791280
bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)

def update_site_file(new_data, var_name):
    try:
        # Берем данные из настроек Render
        ftp = ftplib.FTP(os.getenv('FTP_HOST'))
        ftp.login(os.getenv('FTP_USER'), os.getenv('FTP_PASS'))
        
        # Скачиваем файл
        lines = []
        ftp.retrlines('RETR htdocs/data.js', lines.append)
        content = "\n".join(lines)
        
        # Умная замена через регулярки
        pattern = rf"(const {var_name} = )\[.*?\](?=;)"
        replacement = f"{var_name} = {new_data}" # упрощенно для теста
        # Для точности используем:
        new_content = re.sub(rf"const {var_name} = \[.*?\];", f"const {var_name} = {new_data};", content, flags=re.DOTALL)
        
        # Сохраняем и заливаем обратно
        with open("temp_data.js", "w", encoding="utf-8") as f:
            f.write(new_content)
        
        with open("temp_data.js", "rb") as f:
            ftp.storbinary('STOR htdocs/data.js', f)
            
        ftp.quit()
        return True
    except Exception as e:
        print(f"Ошибка FTP: {e}")
        return False

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and m.text.startswith('/routes'))
def handle_routes(message):
    json_data = message.text.replace('/routes', '').strip()
    if update_site_file(json_data, "trunkRoutes"):
        bot.reply_to(message, "✅ Маршруты на сайте обновлены!")
    else:
        bot.reply_to(message, "❌ Ошибка при обновлении файла через FTP.")

@server.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200

@server.route("/")
def webhook():
    return "Бот работает!", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
