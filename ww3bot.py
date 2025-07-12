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

player_data = {}
country_groups = {}
player_assets = {}
pending_assets = {}
bot_enabled = True

def is_owner(msg): return msg.from_user.id in [OWNER_ID, OWNER_ID_2]

def main_menu():
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("📃 ارسال بیانیه", callback_data="statement"))
    m.add(types.InlineKeyboardButton("💼 دارایی", callback_data="assets"))
    m.add(types.InlineKeyboardButton("🔥 حمله", callback_data="attack"))
    return m

@bot.message_handler(commands=['setcountry'])
def set_country(message):
    if not is_owner(message): return
    reply = message.reply_to_message
    parts = message.text.split(None, 1)
    if not reply or not reply.from_user or len(parts) < 2:
        bot.reply_to(message, "باید روی پیام پلیر ریپلای کنی و نام کشور رو بنویسی مثل /setcountry ایران")
        return
    try:
        user_id = reply.from_user.id
        country = parts[1].strip()
        player_data[user_id] = country
        country_groups[country] = message.chat.id
        bot.reply_to(message, f"✅ کشور {country} برای کاربر {user_id} ثبت شد و این گروه به کشور نسبت داده شد")
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {e}")

@bot.message_handler(commands=['setassets'])
def set_assets(message):
    if not is_owner(message): return
    reply = message.reply_to_message
    parts = message.text.split(None, 1)
    if not reply or not reply.text or len(parts) < 2:
        bot.reply_to(message, "باید روی پیام حاوی دارایی ریپلای کنی و نام کشور رو بزنی مثل /setassets ایران")
        return
    try:
        country = parts[1].strip()
        user_id = None
        for uid, cname in player_data.items():
            if cname.lower() == country.lower():
                user_id = uid
                break
        if not user_id:
            bot.reply_to(message, "⛔ کشور مورد نظر یافت نشد")
            return
        pending_assets[user_id] = reply.text.strip()
        m = types.InlineKeyboardMarkup()
        m.add(types.InlineKeyboardButton("✅ تایید", callback_data=f"confirm_assets:{user_id}"))
        m.add(types.InlineKeyboardButton("❌ لغو", callback_data=f"cancel_assets:{user_id}"))
        bot.send_message(message.chat.id, f"متن دارایی:\n{reply.text.strip()}\n\nمورد تایید هست؟", reply_markup=m)
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {e}")

@bot.message_handler(commands=['delcountry'])
def del_country(message):
    if not is_owner(message): return
    if not message.reply_to_message:
        bot.reply_to(message, "⛔ باید روی پیام پلیر ریپلای بزنی")
        return
    try:
        user_id = message.reply_to_message.from_user.id
        country = player_data.pop(user_id, None)
        if country: country_groups.pop(country, None)
        bot.reply_to(message, f"✅ کشور {country or 'نامشخص'} برای {user_id} حذف شد")
    except: bot.reply_to(message, "❌ خطا در حذف کشور")

@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_assets") or c.data.startswith("cancel_assets"))
def confirm_assets_handler(call):
    uid = int(call.data.split(":")[1])
    if call.data.startswith("confirm_assets"):
        player_assets[uid] = pending_assets.get(uid, "ثبت نشده")
        bot.send_message(call.message.chat.id, "✅ دارایی ثبت شد", reply_markup=main_menu())
    else:
        bot.send_message(call.message.chat.id, "❌ دارایی لغو شد", reply_markup=main_menu())
    pending_assets.pop(uid, None)

@bot.message_handler(commands=['start', 'panel'])
def send_panel(message):
    if not bot_enabled: return bot.reply_to(message, "⛔ ربات خاموش است")
    if message.from_user.id in player_data or is_owner(message):
        bot.send_message(message.chat.id, "🎮 پنل بازی متنی", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "assets")
def handle_assets(call):
    uid = call.from_user.id
    target = uid if uid in player_data else None
    if not target and is_owner(call):
        for tid, cname in player_data.items():
            if country_groups.get(cname) == call.message.chat.id:
                target = tid
                break
    text = player_assets.get(target or -1, "⛔ دارایی ثبت نشده")
    bot.send_message(call.message.chat.id, f"📦 دارایی:\n{text}", reply_markup=main_menu())

@bot.message_handler(commands=['up'])
def up_all(message):
    if not is_owner(message): return
    count = 0
    for uid, assets in player_assets.items():
        lines, updated = [], False
        for line in assets.splitlines():
            if '[' in line and ']' in line and ':' in line:
                try:
                    label, val = line.split(':', 1)
                    name, br = label.split('[', 1)
                    y = int(br.split(']')[0])
                    base = int(val.strip())
                    total = base + y
                    lines.append(f"{name.strip()}[{y}]: {total}")
                    updated = True
                except: lines.append(line)
            else: lines.append(line)
        if updated:
            updated_text = '\n'.join(lines)
            player_assets[uid] = updated_text
            country = player_data.get(uid)
            gid = country_groups.get(country)
            if gid:
                bot.send_message(gid, f"📈 دارایی به‌روزرسانی شد:\n{updated_text}")
                count += 1
    bot.reply_to(message, f"✅ بازدهی {count} کشور آپدیت شد")

# بکاپ
def backup():
    while True:
        try:
            with open("backup.json", "w", encoding="utf-8") as f:
                json.dump({"countries": player_data, "groups": country_groups, "assets": player_assets}, f, ensure_ascii=False)
        except Exception as e:
            print("⛔ خطا در بکاپ:", e)
        time.sleep(600)

threading.Thread(target=backup, daemon=True).start()

@app.route('/', methods=['POST'])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(flask.request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return ''
    else:
        flask.abort(403)

bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

if __name__ == '__main__':
    print("ربات با Webhook راه‌اندازی شد")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
