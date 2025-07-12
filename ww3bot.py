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
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = telebot.TeleBot(TOKEN)
app = flask.Flask(__name__)

player_data = {}  # user_id -> country
pending_statements = {}
pending_assets = {}
player_assets = {}
bot_enabled = True

# ابزار
def is_owner(message):
    return message.from_user.id in [OWNER_ID, OWNER_ID_2]

def main_menu(user_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("\ud83d\udcc3 \u0627\u0631\u0633\u0627\u0644 \u0628\u06cc\u0627\u0646\u06cc\u0647", callback_data=f"statement:{user_id}"))
    markup.add(types.InlineKeyboardButton("\ud83d\udcbc \u062f\u0627\u0631\u0627\u06cc\u06cc", callback_data=f"assets:{user_id}"))
    return markup

# ست کشور
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

# ست دارایی
@bot.message_handler(commands=['setassets'])
def set_assets(message):
    if not is_owner(message): return
    if not message.reply_to_message:
        bot.reply_to(message, "باید روی پیام حاوی دارایی ریپلای کنی و نام کشور رو بزنی مثل /setassets ایران")
        return
    try:
        user_id = None
        country = message.text.split(None, 1)[1]
        for uid, cname in player_data.items():
            if cname == country:
                user_id = uid
                break
        if not user_id:
            bot.reply_to(message, "⛔ کشور مورد نظر یافت نشد")
            return
        pending_assets[user_id] = message.reply_to_message.text
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ تایید", callback_data=f"confirm_assets:{user_id}"))
        markup.add(types.InlineKeyboardButton("❌ لغو", callback_data=f"cancel_assets:{user_id}"))
        bot.send_message(message.chat.id, f"متن دارایی:\n{message.reply_to_message.text}\n\nمورد تایید هست؟", reply_markup=markup)
    except:
        bot.reply_to(message, "خطا در پردازش فرمان")

# روشن و خاموش
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
    uid = message.from_user.id
    if uid in player_data or is_owner(message):
        bot.send_message(message.chat.id, "به پنل گیم متنی خوش آمدید", reply_markup=main_menu(uid))

# بیانیه
@bot.callback_query_handler(func=lambda call: call.data.startswith("statement:"))
def handle_statement(call):
    target_id = int(call.data.split(":")[1])
    if call.from_user.id == target_id or call.from_user.id in [OWNER_ID, OWNER_ID_2]:
        msg = bot.send_message(call.message.chat.id, "متن بیانیه خود را ارسال کنید:")
        bot.register_next_step_handler(msg, lambda m: process_statement(m, target_id))

def process_statement(message, target_id):
    pending_statements[target_id] = message.text
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ تایید", callback_data=f"confirm_statement:{target_id}"))
    markup.add(types.InlineKeyboardButton("❌ لغو", callback_data=f"cancel_statement:{target_id}"))
    bot.send_message(message.chat.id, f"{player_data.get(target_id, 'کشور ثبت نشده')}\n{message.text}\n\nمورد تایید است؟", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_statement") or c.data.startswith("cancel_statement"))
def confirm_statement_handler(call):
    parts = call.data.split(":")
    target_id = int(parts[1])
    if call.data.startswith("confirm_statement"):
        text = f"📢 بیانیه از کشور {player_data.get(target_id, 'نامشخص')}:\n{pending_statements[target_id]}"
        bot.send_message(call.message.chat.id, "✅ بیانیه ارسال شد")
        bot.send_message(f"@{player_data.get(target_id, 'نامشخص')}", text)
    else:
        bot.send_message(call.message.chat.id, "❌ بیانیه لغو شد")
    pending_statements.pop(target_id, None)

# تایید دارایی
@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_assets") or c.data.startswith("cancel_assets"))
def confirm_assets_handler(call):
    parts = call.data.split(":")
    user_id = int(parts[1])
    if call.data.startswith("confirm_assets"):
        player_assets[user_id] = pending_assets.get(user_id, "ثبت نشده")
        bot.send_message(call.message.chat.id, "✅ دارایی ثبت شد")
    else:
        bot.send_message(call.message.chat.id, "❌ دارایی لغو شد")
    pending_assets.pop(user_id, None)

# نمایش دارایی
@bot.callback_query_handler(func=lambda c: c.data.startswith("assets:"))
def handle_assets(call):
    target_id = int(call.data.split(":")[1])
    if call.from_user.id == target_id or call.from_user.id in [OWNER_ID, OWNER_ID_2]:
        text = player_assets.get(target_id, "⛔ دارایی ثبت نشده")
        bot.send_message(call.message.chat.id, f"📦 دارایی:\n{text}")
    else:
        bot.send_message(call.message.chat.id, "⛔ دسترسی ندارید")

# ارتقاء بازدهی کلی توسط ادمین
@bot.message_handler(commands=['up'])
def handle_up_all(message):
    if not is_owner(message):
        bot.send_message(message.chat.id, "⛔ فقط ادمین می‌تواند بازدهی همه کشورها را به‌روز کند")
        return

    updated_count = 0
    for user_id, original_text in player_assets.items():
        updated_lines = []
        for line in original_text.splitlines():
            if '[' in line and ']' in line and ':' in line:
                try:
                    label, value_part = line.split(':', 1)
                    base = int(value_part.strip())
                    name, bracket = label.split('[', 1)
                    yield_value = int(bracket.split(']')[0])
                    total = base + yield_value
                    new_line = f"{name.strip()}[{yield_value}]: {total}"
                    updated_lines.append(new_line)
                except:
                    updated_lines.append(line)
            else:
                updated_lines.append(line)
        updated_text = '\n'.join(updated_lines)
        player_assets[user_id] = updated_text
        group = f"@{player_data.get(user_id, 'نامشخص')}"
        bot.send_message(group, f"📈 دارایی با بازدهی به‌روز شد:\n{updated_text}")
        updated_count += 1
    bot.send_message(message.chat.id, f"✅ بازدهی {updated_count} کشور به‌روزرسانی شد")

# بکاپ‌گیری
BACKUP_FILE = "backup.json"
def backup_data():
    while True:
        try:
            with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
                json.dump({"countries": player_data, "assets": player_assets}, f, ensure_ascii=False)
        except Exception as e:
            print("خطا در بکاپ گیری:", e)
        time.sleep(600)  # هر 10 دقیقه

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
