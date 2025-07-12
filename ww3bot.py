import os
import telebot
from telebot import types
import flask
import json
import threading
import time

# === Environment ===
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
OWNER_ID_2 = int(os.environ.get("OWNER_ID_2"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = telebot.TeleBot(TOKEN)
app = flask.Flask(__name__)

player_data = {}         # user_id -> country
player_groups = {}       # country -> group_id
pending_assets = {}
player_assets = {}
bot_enabled = True

# === Helpers ===
def is_owner(message):
    return message.from_user.id in [OWNER_ID, OWNER_ID_2]

def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("\ud83d\udcc3 ارسال بیانیه", callback_data="statement"))
    markup.add(types.InlineKeyboardButton("\ud83d\udcbc دارایی", callback_data="assets"))
    return markup

# === /setcountry ===
@bot.message_handler(commands=['setcountry'])
def set_country(message):
    if not is_owner(message): return
    if not message.reply_to_message or not hasattr(message.reply_to_message, 'from_user'):
        bot.reply_to(message, "باید روی پیام پلیر ریپلای کنی و نام کشور رو بنویسی مثل /setcountry ایران")
        return
    try:
        user_id = message.reply_to_message.from_user.id
        country = message.text.split(None, 1)[1].strip()
        player_data[user_id] = country
        player_groups[country] = message.chat.id
        bot.reply_to(message, f"✅ کشور {country} برای کاربر {user_id} ثبت شد و این گروه به عنوان گروه رسمی {country} ثبت شد")
    except Exception as e:
        bot.reply_to(message, f"خطا در ثبت کشور: {str(e)}")

# === /delcountry ===
@bot.message_handler(commands=['delcountry'])
def del_country(message):
    if not is_owner(message): return
    if not message.reply_to_message or not hasattr(message.reply_to_message, 'from_user'):
        bot.reply_to(message, "باید روی پیام پلیر ریپلای کنی تا کشورش حذف بشه")
        return
    user_id = message.reply_to_message.from_user.id
    country = player_data.pop(user_id, None)
    if country:
        player_groups.pop(country, None)
        bot.reply_to(message, f"✅ کشور {country} حذف شد")
    else:
        bot.reply_to(message, "⛔ کشور برای این پلیر ثبت نشده بود")

# === /setassets ===
@bot.message_handler(commands=['setassets'])
def set_assets(message):
    if not is_owner(message): return
    if not message.reply_to_message or not message.reply_to_message.text:
        bot.reply_to(message, "باید روی پیام حاوی دارایی ریپلای کنی و نام کشور رو بزنی مثل /setassets ایران")
        return
    try:
        country = message.text.split(None, 1)[1].strip()
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
    except Exception as e:
        bot.reply_to(message, f"خطا در پردازش فرمان: {str(e)}")

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

# === /up ===
@bot.message_handler(commands=['up'])
def handle_up(message):
    if not is_owner(message): return
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
        country = player_data.get(user_id, "نامشخص")
        group_id = player_groups.get(country)
        if group_id:
            bot.send_message(group_id, f"📈 دارایی جدید کشور {country}:\n{updated_text}")

# === پنل و دارایی ===
@bot.message_handler(commands=['start', 'panel'])
def send_menu(message):
    if not bot_enabled:
        bot.reply_to(message, "⛔ ربات خاموش است")
        return
    uid = message.from_user.id
    if uid in player_data or is_owner(message):
        bot.send_message(message.chat.id, "به پنل خوش آمدید", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "assets")
def handle_assets(call):
    requester_id = call.from_user.id
    requester_country = player_data.get(requester_id, None)
    target_id = None
    for uid, cname in player_data.items():
        if player_groups.get(cname) == call.message.chat.id:
            target_id = uid
            break
    if requester_id == target_id or is_owner(call):
        if target_id:
            asset = player_assets.get(target_id, "⛔ دارایی ثبت نشده")
            bot.send_message(call.message.chat.id, f"📦 دارایی:\n{asset}", reply_markup=main_menu())
        else:
            bot.send_message(call.message.chat.id, "⛔ دارایی‌ای برای این کشور ثبت نشده")
    else:
        bot.send_message(call.message.chat.id, "⛔ دسترسی ندارید")

# === Backup ===
BACKUP_FILE = "backup.json"
def backup_data():
    while True:
        try:
            with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
                json.dump({"countries": player_data, "groups": player_groups, "assets": player_assets}, f, ensure_ascii=False)
        except Exception as e:
            print("Backup error:", e)
        time.sleep(600)

threading.Thread(target=backup_data, daemon=True).start()

# === Webhook ===
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
print("ربات راه‌اندازی شد با webhook")

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
