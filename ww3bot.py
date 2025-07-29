import os
from flask import Flask, request
import telebot
from telebot import types

# تنظیمات اولیه
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OWNER_ID = int(os.getenv("OWNER_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # مثلا: https://your-bot-name.onrender.com

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# دیکشنری‌های مورد نیاز
countries = {}
statement_step = {}

# --- دستورات بات ---
@bot.message_handler(commands=["panel"])
def send_panel(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("بیانیه", callback_data="statement"))
    bot.send_message(message.chat.id, "خوش آمدید به پنل", reply_markup=markup)

@bot.message_handler(commands=["setcountry"])
def set_country(message):
    if message.from_user.id != OWNER_ID:
        return
    if not message.reply_to_message:
        bot.reply_to(message, "باید روی پیام بازیکن ریپلای کنی")
        return
    user_id = message.reply_to_message.from_user.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "باید اسم کشور رو هم بنویسی")
        return
    country_name = parts[1]
    countries[user_id] = country_name
    bot.reply_to(message, f"کشور {country_name} برای کاربر ست شد")

@bot.message_handler(commands=["delcountry"])
def delete_country(message):
    if message.from_user.id != OWNER_ID:
        return
    if not message.reply_to_message:
        bot.reply_to(message, "باید روی پیام بازیکن ریپلای کنی")
        return
    user_id = message.reply_to_message.from_user.id
    if user_id in countries:
        del countries[user_id]
        bot.reply_to(message, "کشور کاربر حذف شد")
    else:
        bot.reply_to(message, "برای این کاربر کشوری ثبت نشده")

@bot.callback_query_handler(func=lambda call: call.data == "statement")
def statement_start(call):
    statement_step[call.from_user.id] = True
    bot.send_message(call.message.chat.id, "متن بیانیه خود را وارد کنید")

@bot.message_handler(func=lambda m: m.from_user.id in statement_step)
def receive_statement(message):
    user_id = message.from_user.id
    country = countries.get(user_id, "کشور ناشناس")
    text = f"📢 بیانیه از {country}:\n\n{message.text}"
    bot.send_message(CHANNEL_ID, text)
    bot.send_message(message.chat.id, "بیانیه شما ارسال شد")
    del statement_step[user_id]

# --- Webhook Routes ---
@app.route('/')
def home():
    return "Bot is running! Use /setwebhook to activate.", 200

@app.route('/setwebhook', methods=['GET', 'POST'])
def set_webhook():
    # حذف وب‌هوک قبلی (اگر وجود دارد)
    bot.remove_webhook()
    # تنظیم وب‌هوک جدید
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    return "Webhook set successfully!", 200

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_data = request.get_data().decode('utf-8')
        update = types.Update.de_json(json_data)
        bot.process_new_updates([update])
        return "OK", 200
    return "Bad Request", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
