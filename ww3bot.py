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
pending_statements = {}
pending_assets = {}
player_assets = {}
pending_messages = {}  # user_id -> {'step': 1, 'target': None}
country_groups = {}  # country name -> group chat id
bot_enabled = True

# ابزار
def is_owner(message):
    return message.from_user.id in [OWNER_ID, OWNER_ID_2]

def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📃 ارسال بیانیه", callback_data="statement"))
    markup.add(types.InlineKeyboardButton("💼 دارایی", callback_data="assets"))
    markup.add(types.InlineKeyboardButton("🔥 حمله", callback_data="attack"))
    markup.add(types.InlineKeyboardButton("✉️ ارسال پیام", callback_data="sendmsg"))
    return markup

# دستورات مدیر
@bot.message_handler(commands=['setcountry'])
def set_country(message):
    if not is_owner(message): return
    if not message.reply_to_message:
        bot.reply_to(message, "باید روی پیام پلیر ریپلای کنی و نام کشور رو بنویسی مثل /setcountry ایران")
        return
    try:
        user_id = message.reply_to_message.from_user.id
        country = message.text.split(None, 1)[1]
        player_data[user_id] = country
        bot.reply_to(message, f"✅ کشور {country} برای کاربر {user_id} ثبت شد")
    except:
        bot.reply_to(message, "خطا در پردازش فرمان")

@bot.message_handler(commands=['setgroup'])
def set_group(message):
    if not is_owner(message): return
    try:
        parts = message.text.split(None, 1)
        if len(parts) != 2:
            bot.reply_to(message, "فرمت درست: /setgroup ایران")
            return
        country = parts[1]
        country_groups[country] = message.chat.id
        bot.reply_to(message, f"✅ گروه برای کشور {country} ثبت شد")
    except:
        bot.reply_to(message, "خطا در ثبت گروه")

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

# منو
@bot.message_handler(commands=['start', 'panel'])
def send_menu(message):
    if not bot_enabled:
        bot.reply_to(message, "⛔ ربات خاموش است")
        return
    if message.from_user.id in player_data:
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
    country = player_data.get(message.from_user.id, 'کشور ثبت نشده')
    bot.send_message(message.chat.id, f"{country}\n{message.text}\n\nمورد تایید است؟", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["confirm_statement", "cancel_statement"])
def confirm_statement_handler(call):
    user_id = call.from_user.id
    if call.data == "confirm_statement":
        country = player_data.get(user_id, 'نامشخص')
        text = f"📢 بیانیه از کشور {country}:\n{pending_statements[user_id]}"
        bot.send_message(CHANNEL_USERNAME, text)
        bot.send_message(call.message.chat.id, "✅ بیانیه ارسال شد", reply_markup=main_menu())
    else:
        bot.send_message(call.message.chat.id, "❌ بیانیه لغو شد", reply_markup=main_menu())
    pending_statements.pop(user_id, None)

# دارایی
@bot.callback_query_handler(func=lambda c: c.data == "assets")
def handle_assets(call):
    user_id = call.from_user.id
    text = player_assets.get(user_id, "⛔ دارایی ثبت نشده")
    bot.send_message(call.message.chat.id, f"📦 دارایی شما:\n{text}", reply_markup=main_menu())

@bot.message_handler(commands=['setassets'])
def set_assets(message):
    if not is_owner(message): return
    if not message.reply_to_message:
        bot.reply_to(message, "باید روی پیام دارایی ریپلای کنی و بنویسی /setassets ایران")
        return
    try:
        country = message.text.split(None, 1)[1]
        for uid, cname in player_data.items():
            if cname == country:
                pending_assets[uid] = message.reply_to_message.text
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("✅ تایید", callback_data=f"confirm_assets:{uid}"))
                markup.add(types.InlineKeyboardButton("❌ لغو", callback_data=f"cancel_assets:{uid}"))
                bot.send_message(message.chat.id, "متن دارایی:\n" + message.reply_to_message.text + "\n\nمورد تایید هست؟", reply_markup=markup)
                return
        bot.send_message(message.chat.id, "⛔ کشور یافت نشد")
    except:
        bot.send_message(message.chat.id, "خطا در پردازش فرمان")

@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_assets") or c.data.startswith("cancel_assets"))
def confirm_assets_handler(call):
    parts = call.data.split(":")
    uid = int(parts[1])
    if call.data.startswith("confirm_assets"):
        player_assets[uid] = pending_assets.get(uid, "ثبت نشده")
        bot.send_message(call.message.chat.id, "✅ دارایی ثبت شد", reply_markup=main_menu())
    else:
        bot.send_message(call.message.chat.id, "❌ دارایی لغو شد", reply_markup=main_menu())
    pending_assets.pop(uid, None)

# بازدهی
@bot.message_handler(commands=['up'])
def handle_up(message):
    uid = message.from_user.id
    if uid not in player_assets:
        bot.send_message(message.chat.id, "⛔ دارایی ثبت نشده")
        return
    original_text = player_assets[uid]
    updated = []
    for line in original_text.splitlines():
        if '[' in line and ']' in line and ':' in line:
            try:
                label, value = line.split(':', 1)
                name, yield_val = label.split('[', 1)
                yield_val = int(yield_val.split(']')[0])
                base = int(value.strip())
                total = base + yield_val
                updated.append(f"{name.strip()}[{yield_val}]: {total}")
            except:
                updated.append(line)
        else:
            updated.append(line)
    player_assets[uid] = '\n'.join(updated)
    bot.send_message(message.chat.id, f"📈 دارایی به‌روز شد:\n{player_assets[uid]}", reply_markup=main_menu())

# ارسال پیام
@bot.callback_query_handler(func=lambda c: c.data == "sendmsg")
def start_sendmsg(call):
    pending_messages[call.from_user.id] = {"step": 1}
    msg = bot.send_message(call.message.chat.id, "🌍 نام کشور مقصد را وارد کنید:")
    bot.register_next_step_handler(msg, continue_sendmsg)

def continue_sendmsg(message):
    uid = message.from_user.id
    if uid not in pending_messages: return
    step = pending_messages[uid]["step"]
    if step == 1:
        country = message.text.strip()
        if country not in country_groups:
            bot.send_message(message.chat.id, "⛔ کشور یافت نشد", reply_markup=main_menu())
            pending_messages.pop(uid, None)
            return
        pending_messages[uid]["target"] = country
        pending_messages[uid]["step"] = 2
        msg = bot.send_message(message.chat.id, "📝 متن پیام خود را بنویسید:")
        bot.register_next_step_handler(msg, continue_sendmsg)
    elif step == 2:
        text = message.text
        source_country = player_data.get(uid, 'نامشخص')
        target_country = pending_messages[uid]["target"]
        group_id = country_groups[target_country]
        bot.send_message(group_id, f"📨 پیام از طرف کشور {source_country}:\n{text}")
        bot.send_message(message.chat.id, "✅ پیام ارسال شد", reply_markup=main_menu())
        pending_messages.pop(uid, None)

# بکاپ
def backup_data():
    while True:
        try:
            with open("backup.json", 'w', encoding='utf-8') as f:
                json.dump({
                    "countries": player_data,
                    "assets": player_assets,
                    "groups": country_groups
                }, f, ensure_ascii=False)
        except Exception as e:
            print("⚠️ خطا در بکاپ:", e)
        time.sleep(600)

threading.Thread(target=backup_data, daemon=True).start()

# Webhook
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

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
