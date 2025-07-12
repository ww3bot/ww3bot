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
OWNER_ID_2 = int(os.environ.get("OWNER_ID_2", "0"))  # اگر تنظیم نشده باشه صفر میشه
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = telebot.TeleBot(TOKEN)
app = flask.Flask(__name__)

player_data = {}
pending_statements = {}
pending_assets = {}
player_assets = {}
allowed_chat_id = None
bot_enabled = True

# ابزار
def is_owner(message):
    return message.from_user.id in [OWNER_ID, OWNER_ID_2]

def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📃 ارسال بیانیه", callback_data="statement"))
    markup.add(types.InlineKeyboardButton("💼 دارایی", callback_data="assets"))
    markup.add(types.InlineKeyboardButton("🔥 حمله", callback_data="attack"))
    return markup

# دستورات مدیریتی
@bot.message_handler(commands=['setcountry'])
def set_country(message):
    if not is_owner(message): return
    global allowed_chat_id
    try:
        args = message.text.split()
        user_id = int(args[1])
        country = args[2]
        player_data[user_id] = country
        allowed_chat_id = message.chat.id
        bot.reply_to(message, f"کشور {country} برای بازیکن تنظیم شد.")
    except:
        bot.reply_to(message, "فرمت صحیح: /setcountry [user_id] [country]")

@bot.message_handler(commands=['setassets'])
def set_assets(message):
    if not is_owner(message): return
    try:
        args = message.text.split()
        user_id = int(args[1])
        text = message.text.split(None, 2)[2]
        pending_assets[user_id] = text
        markup = types.InlineKeyboardMarkup()
        markup.add(types=types.InlineKeyboardButton("✅ تایید", callback_data=f"confirm_assets:{user_id}"))
        markup.add(types=types.InlineKeyboardButton("❌ لغو", callback_data=f"cancel_assets:{user_id}"))
        bot.send_message(message.chat.id, f"متن دارایی:\n{text}\n\nمورد تایید هست؟", reply_markup=markup)
    except:
        bot.reply_to(message, "فرمت: /setassets [user_id] [text]")

@bot.message_handler(commands=['on'])
def turn_on(message):
    global bot_enabled
    if is_owner(message):
        bot_enabled = True
        bot.reply_to(message, "✅ ربات روشن شد")

@bot.message_handler(commands=['off'])
def turn_off(message):
    global bot_enabled
    if is_owner(message):
        bot_enabled = False
        bot.reply_to(message, "⚠️ ربات خاموش شد")

@bot.message_handler(commands=['start', 'panel'])
def send_menu(message):
    if not bot_enabled:
        bot.reply_to(message, "⛔ ربات خاموش است")
        return
    if message.from_user.id in player_data and message.chat.id == allowed_chat_id:
        bot.send_message(message.chat.id, "به پنل گیم متنی خوش آمدید", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_assets") or c.data.startswith("cancel_assets"))
def confirm_assets_handler(call):
    parts = call.data.split(":")
    user_id = int(parts[1])
    if call.data.startswith("confirm_assets"):
        player_assets[user_id] = pending_assets.get(user_id, "ثبت نشده")
        bot.send_message(call.message.chat.id, "✅ دارایی ثبت شد", reply_markup=main_menu())
    else:
        bot.send_message(call.message.chat.id, "❌ دارایی لغو شد", reply_markup=main_menu())
    pending_assets.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: call.data == "assets")
def handle_assets(call):
    user_id = call.from_user.id
    text = player_assets.get(user_id, "⛔ دارایی ثبت نشده")
    bot.send_message(call.message.chat.id, f"📦 دارایی شما:\n{text}", reply_markup=main_menu())

@bot.message_handler(commands=['up'])
def update_production(message):
    user_id = message.from_user.id
    if user_id not in player_assets:
        bot.reply_to(message, "⛔ دارایی برای شما ثبت نشده")
        return
    updated_lines = []
    lines = player_assets[user_id].split("\n")
    for line in lines:
        if ":" in line and "[" in line and "]" in line:
            try:
                before_bracket = line.split("[")[0]
                inside_bracket = int(line.split("[")[1].split("]")[0])
                after_colon = int(line.split(":")[1].strip())
                new_value = after_colon + inside_bracket
                updated_lines.append(f"{before_bracket}[{inside_bracket}]: {new_value}")
            except:
                updated_lines.append(line)
        else:
            updated_lines.append(line)
    player_assets[user_id] = "\n".join(updated_lines)
    bot.reply_to(message, "✅ بازدهی به دارایی شما اضافه شد")

# Webhook route
@app.route('/', methods=['POST'])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)

# Webhook
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

print("ربات با webhook راه‌اندازی شد...")

# بکاپ هر ۱۰ دقیقه

def backup_data():
    while True:
        try:
            data = {
                'player_data': player_data,
                'player_assets': player_assets
            }
            with open("backup.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[!] Backup failed: {e}")
        time.sleep(600)

threading.Thread(target=backup_data, daemon=True).start()

# اجرا
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
