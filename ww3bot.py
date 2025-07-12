import os
import telebot
from telebot import types
import flask
import json
import threading
import time

# محیط
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
OWNER_ID_2 = int(os.environ.get("OWNER_ID_2"))
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = telebot.TeleBot(TOKEN)
app = flask.Flask(__name__)

player_data = {}  # user_id -> country
player_assets = {}  # user_id -> asset
pending_statements = {}
allowed_chat_id = None
bot_enabled = True

# ابزار

def is_owner(message):
    return message.from_user.id in [OWNER_ID, OWNER_ID_2]

def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("\ud83d\udcc3 \u0627\u0631\u0633\u0627\u0644 \u0628\u06cc\u0627\u0646\u06cc\u0647", callback_data="statement"))
    markup.add(types.InlineKeyboardButton("\ud83d\udcbc \u062f\u0627\u0631\u0627\u06cc\u06cc", callback_data="assets"))
    markup.add(types.InlineKeyboardButton("\ud83d\udd25 \u062d\u0645\u0644\u0647", callback_data="attack"))
    return markup

# دستورات مدیریتی

@bot.message_handler(commands=['setcountry'])
def set_country(message):
    if not is_owner(message) or not message.reply_to_message:
        return
    try:
        target_id = message.reply_to_message.from_user.id
        country = message.text.split(None, 1)[1]
        player_data[target_id] = country
        global allowed_chat_id
        allowed_chat_id = message.chat.id
        bot.reply_to(message, f"\u06a9\u0634\u0648\u0631 {country} \u0628\u0631\u0627\u06cc {target_id} \u062b\u0628\u062a \u0634\u062f")
    except:
        bot.reply_to(message, "\u0641\u0631\u0645\u062a \u0635\u062d\u06cc\u062d: /setcountry \u0628\u0627 \u0631\u06cc\u067e\u0644\u0627\u06cc")

@bot.message_handler(commands=['setassets'])
def set_assets(message):
    if not is_owner(message) or not message.reply_to_message:
        return
    try:
        country = message.text.split(None, 1)[1]
        target_id = None
        for uid, cname in player_data.items():
            if cname == country:
                target_id = uid
                break
        if not target_id:
            bot.reply_to(message, "\u06a9\u0634\u0648\u0631 \u0645\u0648\u0631\u062f \u0646\u0638\u0631 \u067e\u06cc\u062f\u0627 \u0646\u0634\u062f")
            return
        text = message.reply_to_message.text
        player_assets[target_id] = text
        bot.send_message(message.chat.id, f"\u062f\u0627\u0631\u0627\u06cc\u06cc \u0628\u0631\u0627\u06cc {country} \u0628\u0627 \u0645\u0648\u0641\u0642\u06cc\u062a \u062b\u0628\u062a \u0634\u062f")
    except Exception as e:
        bot.reply_to(message, f"\u062e\u0637\u0627: {str(e)}")

@bot.message_handler(commands=['on'])
def turn_on(message):
    global bot_enabled
    if is_owner(message):
        bot_enabled = True
        bot.reply_to(message, "\u2705 \u0631\u0628\u0627\u062a \u0631\u0648\u0634\u0646 \u0634\u062f")

@bot.message_handler(commands=['off'])
def turn_off(message):
    global bot_enabled
    if is_owner(message):
        bot_enabled = False
        bot.reply_to(message, "\u26a0\ufe0f \u0631\u0628\u0627\u062a \u062e\u0627\u0645\u0648\u0634 \u0634\u062f")

@bot.message_handler(commands=['start', 'panel'])
def send_menu(message):
    if not bot_enabled:
        bot.reply_to(message, "\u26d4\ufe0f \u0631\u0628\u0627\u062a \u062e\u0627\u0645\u0648\u0634 \u0627\u0633\u062a")
        return
    if message.from_user.id in player_data and message.chat.id == allowed_chat_id:
        bot.send_message(message.chat.id, "\u0628\u0647 \u067e\u0646\u0644 \u06af\u06cc\u0645 \u0645\u062a\u0646\u06cc \u062e\u0648\u0634 \u0622\u0645\u062f\u06cc\u062f", reply_markup=main_menu())

# دارایی
@bot.callback_query_handler(func=lambda call: call.data == "assets")
def handle_assets(call):
    user_id = call.from_user.id
    text = player_assets.get(user_id, "\u26d4\ufe0f \u062f\u0627\u0631\u0627\u06cc\u06cc \u062b\u0628\u062a \u0646\u0634\u062f\u0647")
    bot.send_message(call.message.chat.id, f"\ud83d\udce6 \u062f\u0627\u0631\u0627\u06cc\u06cc \u0634\u0645\u0627:\n{text}", reply_markup=main_menu())

# بکاپ هر 10 دقیقه

def save_backup():
    while True:
        with open("backup_assets.json", "w", encoding="utf-8") as f1:
            json.dump(player_assets, f1, ensure_ascii=False)
        with open("backup_countries.json", "w", encoding="utf-8") as f2:
            json.dump(player_data, f2, ensure_ascii=False)
        time.sleep(600)  # 10 دقیقه

threading.Thread(target=save_backup, daemon=True).start()

# webhook
@app.route('/', methods=['POST'])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)

# راه‌اندازی وبهوک
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)
print("ربات با webhook راه‌اندازی شد...")

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
