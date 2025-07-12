import os
import telebot
from telebot import types
import flask
import json
import threading
import time

TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
OWNER_ID_2 = int(os.environ.get("OWNER_ID_2"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = telebot.TeleBot(TOKEN)
app = flask.Flask(__name__)

player_data = {}  # user_id -> country
country_groups = {}  # country -> group chat id
player_assets = {}  # user_id -> asset text
pending_assets = {}  # user_id -> asset text
bot_enabled = True

def is_owner(message):
    return message.from_user.id in [OWNER_ID, OWNER_ID_2]

def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📃 ارسال بیانیه", callback_data="statement"))
    markup.add(types.InlineKeyboardButton("💼 دارایی", callback_data="assets"))
    markup.add(types.InlineKeyboardButton("🔥 حمله", callback_data="attack"))
    return markup

@bot.message_handler(commands=['setcountry'])
def set_country(message):
    if not is_owner(message):
        return
    if not message.reply_to_message:
        bot.reply_to(message, "باید روی پیام پلیر ریپلای کنی و نام کشور رو بنویسی مثل /setcountry ایران")
        return
    try:
        user_id = message.reply_to_message.from_user.id
        country = message.text.split(None, 1)[1]
        player_data[user_id] = country
        country_groups[country] = message.chat.id
        bot.reply_to(message, f"✅ کشور {country} برای کاربر {user_id} ثبت شد و این گروه برای کشور ذخیره شد")
    except:
        bot.reply_to(message, "❌ خطا در پردازش فرمان")

@bot.message_handler(commands=['setassets'])
def set_assets(message):
    if not is_owner(message):
        return
    if not message.reply_to_message:
        bot.reply_to(message, "باید روی پیام حاوی دارایی ریپلای کنی و نام کشور رو بزنی مثل /setassets ایران")
        return
    try:
        country = message.text.split(None, 1)[1]
        user_id = None
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
        bot.reply_to(message, "❌ خطا در پردازش فرمان")

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

@bot.message_handler(commands=['start', 'panel'])
def send_menu(message):
    if not bot_enabled:
        bot.reply_to(message, "⛔ ربات خاموش است")
        return
    user_id = message.from_user.id
    if user_id in player_data or is_owner(message):
        bot.send_message(message.chat.id, "🎮 پنل بازی متنی", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "assets")
def handle_assets(call):
    user_id = call.from_user.id
    target_user = None

    if user_id in player_data:
        target_user = user_id
    elif is_owner(call):
        for uid, country in player_data.items():
            if country_groups.get(country) == call.message.chat.id:
                target_user = uid
                break

    if not target_user or target_user not in player_assets:
        bot.send_message(call.message.chat.id, "⛔ دارایی ثبت نشده")
    else:
        asset_text = player_assets[target_user]
        bot.send_message(call.message.chat.id, f"📦 دارایی:\n{asset_text}", reply_markup=main_menu())

@bot.message_handler(commands=['up'])
def handle_up(message):
    if not is_owner(message):
        return
    updated_count = 0
    for user_id, asset in player_assets.items():
        updated_lines = []
        for line in asset.splitlines():
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
        country = player_data.get(user_id)
        group_id = country_groups.get(country)
        if group_id:
            bot.send_message(group_id, f"📈 دارایی به‌روزرسانی شد:\n{updated_text}")
            updated_count += 1
    bot.reply_to(message, f"✅ بازدهی {updated_count} کشور بروزرسانی شد")

# بکاپ گیری
BACKUP_FILE = "backup.json"
def backup_data():
    while True:
        try:
            with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "countries": player_data,
                    "groups": country_groups,
                    "assets": player_assets
                }, f, ensure_ascii=False)
        except Exception as e:
            print("خطا در بکاپ گیری:", e)
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
