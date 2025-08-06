from flask import Flask, request
import telebot
import os

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

user_states = {}

# مراحل گفت‌وگو
STATE_WAIT_POST = 1
STATE_WAIT_EMOJI = 2
STATE_WAIT_COUNT = 3

@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return 'ok', 200

@app.route('/')
def index():
    return "Bot is running!"

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "لطفاً یک پست را فوروارد کنید.")
    user_states[message.from_user.id] = {'step': STATE_WAIT_POST}

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states)
def handle_steps(message):
    user = user_states[message.from_user.id]

    # مرحله اول: فوروارد کردن پست
    if user['step'] == STATE_WAIT_POST:
        if not message.forward_from and not message.forward_from_chat:
            bot.send_message(message.chat.id, "❌ لطفاً فقط پست فوروارد شده بفرستید.")
            return
        user['post'] = message
        user['step'] = STATE_WAIT_EMOJI
        bot.send_message(message.chat.id, "✅ حالا ایموجی مورد نظر برای ری‌اکشن را ارسال کنید.")

    # مرحله دوم: دریافت ایموجی
    elif user['step'] == STATE_WAIT_EMOJI:
        user['emoji'] = message.text.strip()
        user['step'] = STATE_WAIT_COUNT
        bot.send_message(message.chat.id, "🔢 تعداد ری‌اکشن را ارسال کنید (مثلاً 47):")

    # مرحله سوم: تعداد
    elif user['step'] == STATE_WAIT_COUNT:
        if not message.text.isdigit():
            bot.send_message(message.chat.id, "❌ فقط عدد وارد کنید.")
            return
        user['count'] = int(message.text.strip())

        emoji = user['emoji']
        count = user['count']
        post = user['post']

        # ساخت دکمه ریکشن فیک
        markup = telebot.types.InlineKeyboardMarkup()
        markup.row(
            telebot.types.InlineKeyboardButton(f"{emoji} {count}", callback_data="none")
        )

        bot.copy_message(chat_id=message.chat.id,
                         from_chat_id=post.chat.id,
                         message_id=post.message_id,
                         reply_markup=markup)

        bot.send_message(message.chat.id, "✅ ریکشن فیک ارسال شد.")
        user_states.pop(message.from_user.id)

# تنظیم webhook
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=os.environ.get("WEBHOOK_URL") + "/" + TOKEN)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
