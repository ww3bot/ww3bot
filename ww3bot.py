import telebot
from telebot import types
import os

TOKEN = os.getenv("TOKEN_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OWNER_ID = int(os.getenv("OWNER_ID"))

bot = telebot.TeleBot(TOKEN)

countries = {}
statement_step = {}

# /panel command
@bot.message_handler(commands=["panel"])
def send_panel(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("بیانیه", callback_data="statement"))
    bot.send_message(message.chat.id, "خوش آمدید به پنل", reply_markup=markup)

# /setcountry via reply
@bot.message_handler(commands=["setcountry"])
def set_country(message):
    if message.from_user.id != OWNER_ID:
        return
    if not message.reply_to_message:
        bot.reply_to(message, "باید روی پیام بازیکن ریپلای کنی")
        return
    user_id = message.reply_to_message.from_user.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "باید اسم کشور رو هم بنویسی")
        return
    country_name = parts[1]
    countries[user_id] = country_name
    bot.reply_to(message, f"کشور {country_name} برای کاربر ست شد")

# /delcountry via reply
@bot.message_handler(commands=["delcountry"])
def delete_country(message):
    if message.from_user.id != OWNER_ID:
        return
    if not message.reply_to_message:
        bot.reply_to(message, "باید روی پیام بازیکن ریپلای کنی")
        return
    user_id = message.reply_to_message.from_user.id
    if user_id in countries:
        del countries[user_id]
        bot.reply_to(message, "کشور کاربر حذف شد")
    else:
        bot.reply_to(message, "برای این کاربر کشوری ثبت نشده")

# handle inline button: "بیانیه"
@bot.callback_query_handler(func=lambda call: call.data == "statement")
def statement_start(call):
    statement_step[call.from_user.id] = True
    bot.send_message(call.message.chat.id, "متن بیانیه خود را وارد کنید")

# handle user input for statement
@bot.message_handler(func=lambda m: m.from_user.id in statement_step)
def receive_statement(message):
    user_id = message.from_user.id
    country = countries.get(user_id, "کشور ناشناس")
    text = f"📢 بیانیه از {country}:\n\n{message.text}"
    bot.send_message(CHANNEL_ID, text)
    bot.send_message(message.chat.id, "بیانیه شما ارسال شد")
    del statement_step[user_id]

# Start the bot
bot.infinity_polling()
