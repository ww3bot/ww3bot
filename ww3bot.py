import os
import telebot
from telebot import types
import flask
import requests

# تنظیمات محیطی
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID_1 = int(os.environ.get("OWNER_ID"))
OWNER_ID_2 = int(os.environ.get("OWNER_ID_2"))
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
    return message.from_user.id in [OWNER_ID_1, OWNER_ID_2]

def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📃 ارسال بیانیه", callback_data="statement"))
    markup.add(types.InlineKeyboardButton("💼 دارایی", callback_data="assets"))
    markup.add(types.InlineKeyboardButton("🔥 حمله", callback_data="attack"))
    markup.add(types.InlineKeyboardButton("🌍 رول و خرابکاری", callback_data="sabotage"))
    return markup

# دستورات
@bot.message_handler(commands=['setcountry'])
def set_country(message):
    if not is_owner(message): return
    global allowed_chat_id
    try:
        _, user_id, country = message.text.split(None, 2)
        player_data[int(user_id)] = country
        allowed_chat_id = message.chat.id
        bot.reply_to(message, f"کشور {country} برای بازیکن تنظیم شد.")
    except:
        bot.reply_to(message, "فرمت صحیح: /setcountry [user_id] [country]")

@bot.message_handler(commands=['setassets'])
def set_assets(message):
    if not is_owner(message): return
    try:
        _, user_id, text = message.text.split(None, 2)
        user_id = int(user_id)
        pending_assets[user_id] = text
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ تایید", callback_data=f"confirm_assets:{user_id}"))
        markup.add(types.InlineKeyboardButton("❌ لغو", callback_data=f"cancel_assets:{user_id}"))
        bot.send_message(message.chat.id, f"متن دارایی:\n{text}\n\nمورد تایید هست؟", reply_markup=markup)
    except:
        bot.reply_to(message, "فرمت: /setassets [user_id] [text]")

@bot.message_handler(commands=['up'])
def upgrade_assets(message):
    user_id = message.from_user.id
    if user_id not in player_assets:
        bot.reply_to(message, "⛔ دارایی ثبت نشده")
        return

    updated = []
    lines = player_assets[user_id].split('\n')
    for line in lines:
        if '[' in line and ']' in line and ':' in line:
            try:
                label = line.split('[')[0].strip()
                boost = int(line.split('[')[1].split(']')[0])
                value = int(line.split(':')[1].strip())
                value += boost
                updated.append(f"{label}[{boost}]: {value}")
            except:
                updated.append(line)
        else:
            updated.append(line)

    player_assets[user_id] = '\n'.join(updated)
    bot.reply_to(message, "✅ بازدهی اعمال شد")

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
    bot.send_message(call.message.chat.id, f"📦 دارایی شما:\n{text}", reply_markup=main_menu())

# حمله
@bot.callback_query_handler(func=lambda call: call.data == "attack")
def handle_attack(call):
    msg = bot.send_message(call.message.chat.id, "⬇️ اطلاعات حمله را به ترتیب ارسال کنید:\nکشور حمله‌کننده\nکشور مورد حمله\nشهر\nمختصات\nتعداد موشک\nنوع موشک")
    bot.register_next_step_handler(msg, process_attack)

def process_attack(message):
    try:
        lines = message.text.split('\n')
        text = f"🚀 کشور {lines[0]} به {lines[1]} حمله کرد\nشهر: {lines[2]}\nمختصات: {lines[3]}\nتعداد موشک‌ها: {lines[4]}\nنوع موشک‌ها: {lines[5]}"
        bot.send_message(f"{CHANNEL_USERNAME}", text)
        bot.send_message(message.chat.id, "✅ حمله ثبت شد", reply_markup=main_menu())
    except:
        bot.send_message(message.chat.id, "❌ فرمت اشتباه است")

# خرابکاری با Hugging Face
@bot.callback_query_handler(func=lambda call: call.data == "sabotage")
def handle_sabotage(call):
    msg = bot.send_message(call.message.chat.id, "رول خود را وارد کنید تا تحلیل شود:")
    bot.register_next_step_handler(msg, analyze_sabotage)

def analyze_sabotage(message):
    try:
        hf_url = "https://api-inference.huggingface.co/models/HuggingFaceH4/zephyr-7b-alpha"
        headers = {"Authorization": f"Bearer {os.environ.get('HF_API_KEY')}"}
        payload = {
            "inputs": f"متن رول خرابکاری:\n{message.text}\nنتیجه این رول چیست؟ تحلیل نظامی بده.",
        }
        response = requests.post(hf_url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()[0]["generated_text"]
            bot.send_message(message.chat.id, f"🔍 تحلیل رول شما:\n{result}", reply_markup=main_menu())
        else:
            raise Exception("Not Found")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ خطا در تحلیل:\n{str(e)}", reply_markup=main_menu())

# Webhook
@app.route('/', methods=['POST'])
def webhook():
    if flask.request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(flask.request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return ''
    return flask.abort(403)

# راه‌اندازی
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)
print("ربات با webhook راه‌اندازی شد...")

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
