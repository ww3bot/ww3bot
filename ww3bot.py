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
OWNER_ID_2 = int(os.environ.get("OWNER_ID_2", "0"))
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = telebot.TeleBot(TOKEN)
app = flask.Flask(__name__)

player_data = {}  # user_id -> country
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
    markup.add(types.InlineKeyboardButton("🌍 رول و خرابکاری", callback_data="sabotage"))
    return markup

# دستورات مدیریتی
@bot.message_handler(commands=['setcountry'])
def set_country(message):
    if not is_owner(message) or not message.reply_to_message:
        return
    country = message.text.split(None, 1)[1] if len(message.text.split()) > 1 else None
    if not country:
        bot.reply_to(message, "⛔ لطفا کشور را وارد کنید. مثلا: /setcountry Iran")
        return
    user_id = message.reply_to_message.from_user.id
    player_data[user_id] = country
    global allowed_chat_id
    allowed_chat_id = message.chat.id
    bot.reply_to(message, f"کشور {country} برای کاربر {user_id} ثبت شد.")

@bot.message_handler(commands=['setassets'])
def set_assets(message):
    if not is_owner(message) or not message.reply_to_message:
        return
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "⛔ لطفا کشور را مشخص کنید. مثلا: /setassets Iran")
            return
        country = args[1]
        user_id = next((uid for uid, c in player_data.items() if c == country), None)
        if user_id is None:
            bot.reply_to(message, f"⛔ کشوری با نام {country} ثبت نشده است.")
            return
        text = message.reply_to_message.text
        pending_assets[user_id] = text
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ تایید", callback_data=f"confirm_assets:{user_id}"))
        markup.add(types.InlineKeyboardButton("❌ لغو", callback_data=f"cancel_assets:{user_id}"))
        bot.send_message(message.chat.id, f"متن دارایی:
{text}

مورد تایید هست؟", reply_markup=markup)
    except:
        bot.reply_to(message, "⛔ خطا در پردازش دستور /setassets")

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

# بیانیه
@bot.callback_query_handler(func=lambda call: call.data == "statement")
def handle_statement(call):
    msg = bot.send_message(call.message.chat.id, "متن بیانیه خود را ارسال کنید:")
    bot.register_next_step_handler(msg, process_statement)

def process_statement(message):
    pending_statements[message.from_user.id] = message.text
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ تایید", callback_data="confirm_statement"))
    markup.add(types.InlineKeyboardButton("❌ لغو", callback_data="cancel_statement"))
    bot.send_message(message.chat.id, f"{player_data[message.from_user.id]}
{message.text}

مورد تایید است؟", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["confirm_statement", "cancel_statement"])
def confirm_statement_handler(call):
    user_id = call.from_user.id
    if call.data == "confirm_statement":
        text = f"📢 بیانیه از کشور {player_data[user_id]}:
{pending_statements[user_id]}"
        bot.send_message(f"{CHANNEL_USERNAME}", text)
        bot.send_message(call.message.chat.id, "✅ بیانیه ارسال شد", reply_markup=main_menu())
    else:
        bot.send_message(call.message.chat.id, "❌ بیانیه لغو شد", reply_markup=main_menu())
    pending_statements.pop(user_id, None)

# دارایی
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
    bot.send_message(call.message.chat.id, f"📦 دارایی شما:
{text}", reply_markup=main_menu())

@bot.message_handler(commands=['up'])
def update_assets(message):
    user_id = message.from_user.id
    if user_id not in player_assets:
        bot.reply_to(message, "⛔ دارایی‌ای برای شما ثبت نشده")
        return
    lines = player_assets[user_id].split('\n')
    updated_lines = []
    for line in lines:
        if '[' in line and ']' in line and ':' in line:
            try:
                left, value = line.split(':', 1)
                name, boost = left.split('[')
                boost = int(boost.strip(']'))
                value = int(value.strip())
                value += boost
                updated_lines.append(f"{name}[{boost}]: {value}")
            except:
                updated_lines.append(line)
        else:
            updated_lines.append(line)
    player_assets[user_id] = '\n'.join(updated_lines)
    bot.reply_to(message, "✅ بازدهی اعمال شد")

# حمله
@bot.callback_query_handler(func=lambda call: call.data == "attack")
def handle_attack(call):
    msg = bot.send_message(call.message.chat.id, "⬇️ اطلاعات حمله را به ترتیب ارسال کنید:
کشور حمله‌کننده
کشور مورد حمله
شهر
مختصات
تعداد موشک
نوع موشک")
    bot.register_next_step_handler(msg, process_attack)

def process_attack(message):
    try:
        lines = message.text.split('\n')
        text = f"🚀 کشور {lines[0]} به {lines[1]} حمله کرد
شهر: {lines[2]}
مختصات: {lines[3]}
تعداد موشک‌ها: {lines[4]}
نوع موشک‌ها: {lines[5]}"
        bot.send_message(f"{CHANNEL_USERNAME}", text)
        bot.send_message(message.chat.id, "✅ حمله ثبت شد", reply_markup=main_menu())
    except:
        bot.send_message(message.chat.id, "❌ فرمت اشتباه است")

# خرابکاری (غیرفعال شده)
@bot.callback_query_handler(func=lambda call: call.data == "sabotage")
def handle_sabotage(call):
    bot.send_message(call.message.chat.id, "⛔ تحلیل هوش مصنوعی غیرفعال است", reply_markup=main_menu())

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

# بکاپ‌گیری هر 10 دقیقه
backup_file = "backup.json"
def backup_job():
    while True:
        data = {
            "player_data": player_data,
            "player_assets": player_assets
        }
        with open(backup_file, 'w') as f:
            json.dump(data, f)
        time.sleep(600)  # 10 دقیقه

threading.Thread(target=backup_job, daemon=True).start()

# تنظیم webhook
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

print("ربات با webhook راه‌اندازی شد...")

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
