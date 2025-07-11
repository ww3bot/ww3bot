import os
import telebot
from telebot import types
import flask

# متغیرهای محیطی
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_IDS = [
    int(os.environ.get("OWNER_ID")),
    int(os.environ.get("OWNER_ID2", 0))
]
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = telebot.TeleBot(TOKEN)
app = flask.Flask(__name__)

player_data = {}  # user_id -> country
player_assets = {}  # user_id -> assets
pending_assets = {}
pending_statements = {}

allowed_chat_id = None
bot_enabled = True

# ابزار

def is_owner(message):
    return message.from_user.id in OWNER_IDS

def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📃 ارسال بیانیه", callback_data="statement"))
    markup.add(types.InlineKeyboardButton("💼 دارایی", callback_data="assets"))
    markup.add(types.InlineKeyboardButton("🔥 حمله", callback_data="attack"))
    markup.add(types.InlineKeyboardButton("🌝 رول و خرابکاری", callback_data="sabotage"))
    markup.add(types.InlineKeyboardButton("🔄 ارتقاء بازدهی", callback_data="upgrade"))
    return markup

# دستورات
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
        markup.add(types.InlineKeyboardButton("✅ تایید", callback_data=f"confirm_assets:{user_id}"))
        markup.add(types.InlineKeyboardButton("❌ لغو", callback_data=f"cancel_assets:{user_id}"))
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
        bot.send_message(message.chat.id, "به پنل خوش آمدید", reply_markup=main_menu())

# منو
@bot.callback_query_handler(func=lambda call: call.data == "statement")
def handle_statement(call):
    msg = bot.send_message(call.message.chat.id, "متن بیانیه خود را ارسال کنید:")
    bot.register_next_step_handler(msg, process_statement)

def process_statement(message):
    pending_statements[message.from_user.id] = message.text
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ تایید", callback_data="confirm_statement"))
    markup.add(types.InlineKeyboardButton("❌ لغو", callback_data="cancel_statement"))
    bot.send_message(message.chat.id, f"{player_data[message.from_user.id]}\n{message.text}\n\nمورد تایید است؟", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["confirm_statement", "cancel_statement"])
def confirm_statement_handler(call):
    user_id = call.from_user.id
    if call.data == "confirm_statement":
        text = f"📢 بیانیه از کشور {player_data[user_id]}:\n{pending_statements[user_id]}"
        bot.send_message(f"{CHANNEL_USERNAME}", text)
        bot.send_message(call.message.chat.id, "✅ بیانیه ارسال شد", reply_markup=main_menu())
    else:
        bot.send_message(call.message.chat.id, "❌ بیانیه لغو شد", reply_markup=main_menu())
    pending_statements.pop(user_id, None)

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

@bot.callback_query_handler(func=lambda call: call.data == "upgrade")
def handle_upgrade(call):
    user_id = call.from_user.id
    text = player_assets.get(user_id, None)
    if not text:
        bot.send_message(call.message.chat.id, "⛔ دارایی ثبت نشده")
        return

    def apply_upgrade(line):
        import re
        pattern = r"(\[)(\d+)(\])\s*:\s*(\d+)"
        match = re.search(pattern, line)
        if match:
            boost = int(match.group(2))
            value = int(match.group(4))
            new_value = value + boost
            return re.sub(r":\s*\d+", f": {new_value}", line)
        return line

    upgraded_lines = [apply_upgrade(l) for l in text.splitlines()]
    new_text = "\n".join(upgraded_lines)
    player_assets[user_id] = new_text
    bot.send_message(call.message.chat.id, f"✅ دارایی شما با بازدهی جدید:\n{new_text}", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: call.data == "attack")
def handle_attack(call):
    msg = bot.send_message(call.message.chat.id, "⬇️ اطلاعات حمله را به ترتیب ارسال کنید:\nکشور حمله‌کننده\nکشور هدف\nشهر\nمختصات\nتعداد موشک\nنوع موشک")
    bot.register_next_step_handler(msg, process_attack)

def process_attack(message):
    try:
        lines = message.text.split('\n')
        text = f"🚀 کشور {lines[0]} به {lines[1]} حمله کرد\nشهر: {lines[2]}\nمختصات: {lines[3]}\nتعداد موشک‌ها: {lines[4]}\nنوع موشک‌ها: {lines[5]}"
        bot.send_message(CHANNEL_USERNAME, text)
        bot.send_message(message.chat.id, "✅ حمله ثبت شد", reply_markup=main_menu())
    except:
        bot.send_message(message.chat.id, "❌ فرمت اشتباه است")

@bot.callback_query_handler(func=lambda call: call.data == "sabotage")
def handle_sabotage(call):
    bot.send_message(call.message.chat.id, "💡 تحلیل رول غیرفعال شده است. برای فعال‌سازی هوش مصنوعی باید API داشته باشید.", reply_markup=main_menu())

@app.route('/', methods=['POST'])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)

bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

print("ربات با webhook راه‌اندازی شد...")
