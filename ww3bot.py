import os
import telebot
from telebot import types

# گرفتن متغیرها از محیط
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME")

bot = telebot.TeleBot(TOKEN)

# متغیرهای حافظه موقت
active_group = None
bot_on = True
player_data = {}
player_assets = {}
pending_statements = {}
pending_attacks = {}

# منوی اصلی
def main_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📃 ارسال بیانیه", callback_data="statement"))
    markup.add(types.InlineKeyboardButton("💼 دارایی", callback_data="assets"))
    markup.add(types.InlineKeyboardButton("🔥 حمله", callback_data="attack"))
    return markup

def is_owner(message):
    return message.from_user.id == OWNER_ID

def is_registered(user_id):
    return user_id in player_data

def is_valid_group(message):
    return active_group is None or message.chat.id == active_group

# روشن یا خاموش کردن ربات
@bot.message_handler(commands=['on', 'off'])
def toggle_bot(message):
    global bot_on
    if not is_owner(message): return
    if message.text == '/off':
        bot_on = False
        bot.reply_to(message, "ربات خاموش شد")
    elif message.text == '/on':
        bot_on = True
        bot.reply_to(message, "ربات روشن شد")

# تنظیم گروه
@bot.message_handler(commands=['setgroup'])
def set_group(message):
    global active_group
    if not is_owner(message): return
    active_group = message.chat.id
    bot.reply_to(message, "گروه فعال تنظیم شد")

# تنظیم کشور پلیر
@bot.message_handler(commands=['setplayer'])
def set_player(message):
    if not is_owner(message): return
    try:
        args = message.text.split()
        user_id = int(args[1])
        country = ' '.join(args[2:])
        player_data[user_id] = country
        bot.reply_to(message, f"پلیر {user_id} برای کشور {country} تنظیم شد")
    except:
        bot.reply_to(message, "فرمت: /setplayer [user_id] [country]")

# تنظیم دارایی پلیر
@bot.message_handler(commands=['setassets'])
def set_assets(message):
    if not is_owner(message): return
    try:
        args = message.text.split()
        user_id = int(args[1])
        text = message.text.split(None, 2)[2]
        player_assets[user_id] = text
        bot.reply_to(message, "دارایی ثبت شد")
    except:
        bot.reply_to(message, "فرمت: /setassets [user_id] [text]")

# اجرای پنل
@bot.message_handler(commands=['panel'])
def panel(message):
    if not bot_on:
        bot.reply_to(message, "ربات خاموش است")
        return
    if not is_valid_group(message):
        bot.reply_to(message, "این گروه برای بازی فعال نیست")
        return
    if not is_registered(message.from_user.id):
        bot.reply_to(message, "شما ثبت نشده‌اید")
        return
    bot.send_message(message.chat.id, "خوش آمدید به پنل گیم متنی", reply_markup=main_menu())

# منوی دکمه‌ها
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    if not bot_on:
        bot.answer_callback_query(call.id, "ربات خاموش است")
        return
    if not is_registered(user_id):
        bot.answer_callback_query(call.id, "شما ثبت نشده‌اید")
        return

    if call.data == "statement":
        msg = bot.send_message(call.message.chat.id, "متن بیانیه خود را ارسال کنید")
        bot.register_next_step_handler(msg, handle_statement)

    elif call.data == "assets":
        text = player_assets.get(user_id, "دارایی‌ای برای شما ثبت نشده")
        bot.send_message(call.message.chat.id, text)

    elif call.data == "attack":
        msg = bot.send_message(call.message.chat.id, "به ترتیب:\n۱. کشور حمله‌کننده\n۲. کشور مورد حمله\n۳. شهر\n۴. مختصات\n۵. تعداد موشک\n۶. نوع موشک\nرا بنویسید (هر مورد در یک خط)")
        bot.register_next_step_handler(msg, handle_attack)

# مرحله ارسال بیانیه
def handle_statement(message):
    user_id = message.from_user.id
    country = player_data[user_id]
    pending_statements[user_id] = message.text
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ تایید", callback_data="confirm_statement"))
    markup.add(types.InlineKeyboardButton("❌ لغو", callback_data="cancel_statement"))
    bot.send_message(message.chat.id, f"{country}\n{message.text}\n\nمورد تایید شما هست؟", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data in ["confirm_statement", "cancel_statement"])
def confirm_statement_handler(call):
    user_id = call.from_user.id
    if call.data == "confirm_statement":
        text = f"{player_data[user_id]}\n{pending_statements[user_id]}"
        bot.send_message(CHANNEL_USERNAME, text)
        bot.send_message(call.message.chat.id, "✅ بیانیه با موفقیت ارسال شد", reply_markup=main_menu())
    else:
        bot.send_message(call.message.chat.id, "❌ بیانیه لغو شد", reply_markup=main_menu())
    pending_statements.pop(user_id, None)

# مرحله ارسال حمله
def handle_attack(message):
    user_id = message.from_user.id
    info = message.text.strip().split('\n')
    if len(info) < 6:
        bot.send_message(message.chat.id, "فرمت اشتباه است. تمام ۶ مورد را بنویسید (هرکدام در یک خط)")
        return
    attacker = info[0]
    target = info[1]
    city = info[2]
    coords = info[3]
    count = info[4]
    missile = info[5]
    text = (
        f"🚀 {attacker} به {target} حمله کرد\n"
        f"🎯 شهر: {city}\n"
        f"📍 مختصات: {coords}\n"
        f"🔥 تعداد موشک: {count}\n"
        f"💥 نوع موشک: {missile}"
    )
    bot.send_message(CHANNEL_USERNAME, text)
    bot.send_message(message.chat.id, "✅ حمله ارسال شد", reply_markup=main_menu())

# شروع
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "برای دسترسی به پنل از دستور /panel استفاده کنید")

# اجرای همیشگی
bot.polling()