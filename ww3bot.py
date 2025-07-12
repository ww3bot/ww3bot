import os
import telebot
from telebot import types
import flask
import requests
import json
import time

# محیط
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
OWNER_ID_2 = int(os.environ.get("OWNER_ID_2"))
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = telebot.TeleBot(TOKEN)
app = flask.Flask(__name__)

player_data = {}          # user_id -> country
player_assets = {}        # user_id -> text
pending_statements = {}   # user_id -> text
pending_assets = {}       # user_id -> text
bot_enabled = True
allowed_chat_id = None

BACKUP_FILE = "backup.json"
BACKUP_INTERVAL = 600  # 10 دقیقه
last_backup_time = 0

def is_owner(message):
    return message.from_user.id in [OWNER_ID, OWNER_ID_2]

def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📃 ارسال بیانیه", callback_data="statement"))
    markup.add(types.InlineKeyboardButton("💼 دارایی", callback_data="assets"))
    markup.add(types.InlineKeyboardButton("🔥 حمله", callback_data="attack"))
    markup.add(types.InlineKeyboardButton("🌍 رول و خرابکاری", callback_data="sabotage"))
    return markup

# ریپلای کردن برای کشور
@bot.message_handler(commands=['setcountry'])
def set_country(message):
    if not is_owner(message): return
    if not message.reply_to_message:
        bot.reply_to(message, "باید روی پیام بازیکن ریپلای کنید")
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "فرمت درست: /setcountry [نام کشور]")
        return
    user_id = message.reply_to_message.from_user.id
    country = args[1]
    player_data[user_id] = country
    global allowed_chat_id
    allowed_chat_id = message.chat.id
    bot.reply_to(message, f"کشور {country} برای بازیکن ست شد")

# ریپلای کردن روی متن دارایی
@bot.message_handler(commands=['setassets'])
def set_assets(message):
    if not is_owner(message): return
    if not message.reply_to_message:
        bot.reply_to(message, "باید روی متن دارایی ریپلای کنید")
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "فرمت: /setassets [کشور]")
        return
    country = args[1]
    found = False
    for uid, cname in player_data.items():
        if cname == country:
            pending_assets[uid] = message.reply_to_message.text
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ تایید", callback_data=f"confirm_assets:{uid}"))
            markup.add(types.InlineKeyboardButton("❌ لغو", callback_data=f"cancel_assets:{uid}"))
            bot.send_message(message.chat.id, f"متن دارایی:
{message.reply_to_message.text}

مورد تایید هست؟", reply_markup=markup)
            found = True
            break
    if not found:
        bot.reply_to(message, "کشور مورد نظر پیدا نشد")

@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_assets") or c.data.startswith("cancel_assets"))
def confirm_assets_handler(call):
    parts = call.data.split(":")
    user_id = int(parts[1])
    if call.data.startswith("confirm_assets"):
        player_assets[user_id] = pending_assets.get(user_id, "ثبت نشده")
        bot.send_message(call.message.chat.id, "✅ دارایی ثبت شد", reply_markup=main_menu())
    else:
        bot.send_message(call.message.chat.id, "❌ لغو شد", reply_markup=main_menu())
    pending_assets.pop(user_id, None)

@bot.message_handler(commands=['up'])
def update_assets(message):
    user_id = message.from_user.id
    if user_id not in player_assets:
        bot.reply_to(message, "دارایی ثبت نشده")
        return
    lines = player_assets[user_id].splitlines()
    new_lines = []
    for line in lines:
        if '[' in line and ']' in line and ':' in line:
            try:
                left, right = line.split(':', 1)
                base_text, efficiency = left.split('[')
                efficiency = efficiency.split(']')[0].strip()
                base_value = right.strip()
                new_value = int(base_value) + int(efficiency)
                new_line = f"{base_text.strip()}[{efficiency}]: {new_value}"
                new_lines.append(new_line)
            except:
                new_lines.append(line)
        else:
            new_lines.append(line)
    player_assets[user_id] = '\n'.join(new_lines)
    bot.reply_to(message, "✅ بازدهی اعمال شد")

@bot.callback_query_handler(func=lambda call: call.data == "assets")
def show_assets(call):
    user_id = call.from_user.id
    text = player_assets.get(user_id, "دارایی نیست")
    bot.send_message(call.message.chat.id, f"📦 دارایی شما:
{text}", reply_markup=main_menu())

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
def start_panel(message):
    if not bot_enabled:
        bot.reply_to(message, "⛔️ ربات غیرفعال است")
        return
    if message.from_user.id in player_data and message.chat.id == allowed_chat_id:
        bot.send_message(message.chat.id, "به پنل خوش آمدید", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "statement")
def handle_statement(call):
    msg = bot.send_message(call.message.chat.id, "متن بیانیه را بفرستید:")
    bot.register_next_step_handler(msg, process_statement)

def process_statement(message):
    pending_statements[message.from_user.id] = message.text
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ تایید", callback_data="confirm_statement"))
    markup.add(types.InlineKeyboardButton("❌ لغو", callback_data="cancel_statement"))
    bot.send_message(message.chat.id, f"{player_data[message.from_user.id]}\n{message.text}\n\nمورد تایید هست؟", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["confirm_statement", "cancel_statement"])
def confirm_statement_handler(call):
    user_id = call.from_user.id
    if call.data == "confirm_statement":
        text = f"📢 بیانیه از کشور {player_data[user_id]}:
{pending_statements[user_id]}"
        bot.send_message(f"{CHANNEL_USERNAME}", text)
        bot.send_message(call.message.chat.id, "✅ بیانیه ارسال شد", reply_markup=main_menu())
    else:
        bot.send_message(call.message.chat.id, "❌ لغو شد", reply_markup=main_menu())
    pending_statements.pop(user_id, None)

@bot.callback_query_handler(func=lambda c: c.data == "sabotage")
def sabotage_query(call):
    msg = bot.send_message(call.message.chat.id, "رول را بفرستید:")
    bot.register_next_step_handler(msg, analyze_sabotage)

def analyze_sabotage(message):
    prompt = f"{message.text}"
    try:
        response = requests.post("https://api.banterai.net/ask", json={"query": prompt})
        if response.status_code == 200:
            reply = response.json().get("response", "پاسخی دریافت نشد")
        else:
            reply = f"❌ خطا در ارتباط با سرور BanterAI: {response.status_code}"
    except Exception as e:
        reply = f"❌ خطای ارتباط: {e}"
    bot.send_message(message.chat.id, f"🧬 تحلیل:
{reply}", reply_markup=main_menu())

@app.route('/', methods=['POST'])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        json_string = flask.request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)

# بکاپ گیری
import threading

def save_backup():
    data = {
        "countries": player_data,
        "assets": player_assets
    }
    with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def backup_loop():
    global last_backup_time
    while True:
        if time.time() - last_backup_time >= BACKUP_INTERVAL:
            save_backup()
            last_backup_time = time.time()
        time.sleep(5)

threading.Thread(target=backup_loop, daemon=True).start()

# webhook
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

print("ربات با webhook راه‌اندازی شد...")

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
