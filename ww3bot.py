import os
import asyncio
import random
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import logging

# تنظیم لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# متغیرهای محیطی
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID', '0'))

class MathChallengeBot:
    def __init__(self):
        self.db_path = 'math_bot.db'
        self.init_database()
        self.current_challenges = {}
        
    def init_database(self):
        """ایجاد جداول دیتابیس"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # جدول کاربران
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                score INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                total_answers INTEGER DEFAULT 0,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول گروه‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY,
                group_name TEXT,
                is_active INTEGER DEFAULT 1,
                challenge_interval INTEGER DEFAULT 600,
                difficulty_level INTEGER DEFAULT 1,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول چالش‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                question TEXT,
                correct_answer INTEGER,
                difficulty INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                solved_by INTEGER DEFAULT NULL,
                solved_at TIMESTAMP DEFAULT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def register_user(self, user_id, username, first_name):
        """ثبت کاربر جدید"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, last_activity)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, username, first_name))
        
        conn.commit()
        conn.close()
    
    def register_group(self, group_id, group_name):
        """ثبت گروه جدید"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO groups 
            (group_id, group_name)
            VALUES (?, ?)
        ''', (group_id, group_name))
        
        conn.commit()
        conn.close()
    
    def generate_math_challenge(self, difficulty=1):
        """تولید چالش ریاضی"""
        if difficulty == 1:  # آسان
            a = random.randint(1, 20)
            b = random.randint(1, 20)
            operation = random.choice(['+', '-'])
            if operation == '+':
                question = f"{a} + {b} = ?"
                answer = a + b
            else:
                if a < b:
                    a, b = b, a
                question = f"{a} - {b} = ?"
                answer = a - b
                
        elif difficulty == 2:  # متوسط
            a = random.randint(10, 50)
            b = random.randint(2, 12)
            operation = random.choice(['+', '-', '*'])
            if operation == '+':
                question = f"{a} + {b} = ?"
                answer = a + b
            elif operation == '-':
                question = f"{a} - {b} = ?"
                answer = a - b
            else:
                question = f"{a} × {b} = ?"
                answer = a * b
                
        else:  # سخت
            a = random.randint(15, 99)
            b = random.randint(15, 99)
            c = random.randint(2, 9)
            operation = random.choice(['mixed1', 'mixed2', 'division'])
            if operation == 'mixed1':
                question = f"{a} + {b} - {c} = ?"
                answer = a + b - c
            elif operation == 'mixed2':
                question = f"{a} - {b} + {c} = ?"
                answer = a - b + c
            else:
                a = random.randint(20, 100)
                b = random.randint(2, 10)
                a = a - (a % b)  # اطمینان از تقسیم بدون باقی‌مانده
                question = f"{a} ÷ {b} = ?"
                answer = a // b
        
        return question, answer
    
    def update_user_score(self, user_id, is_correct):
        """به‌روزرسانی امتیاز کاربر"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if is_correct:
            cursor.execute('''
                UPDATE users 
                SET score = score + 10, 
                    correct_answers = correct_answers + 1,
                    total_answers = total_answers + 1,
                    last_activity = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (user_id,))
        else:
            cursor.execute('''
                UPDATE users 
                SET total_answers = total_answers + 1,
                    last_activity = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (user_id,))
        
        conn.commit()
        conn.close()
    
    def get_leaderboard(self, limit=10):
        """دریافت جدول رتبه‌بندی"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT first_name, username, score, correct_answers, total_answers
            FROM users 
            WHERE score > 0
            ORDER BY score DESC, correct_answers DESC
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        return results

# ایجاد نمونه از کلاس بات
bot_instance = MathChallengeBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور شروع"""
    user = update.effective_user
    chat = update.effective_chat
    
    # ثبت کاربر
    bot_instance.register_user(user.id, user.username, user.first_name)
    
    if chat.type == 'private':
        welcome_text = f"""
🤖 سلام {user.first_name}!

به بات چالش ریاضی خوش آمدید!

🎯 ویژگی‌های بات:
• ارسال چالش ریاضی هر ۱۰ دقیقه
• سیستم امتیازدهی
• جدول رتبه‌بندی
• سطوح مختلف سختی

📋 دستورات:
/leaderboard - نمایش رتبه‌بندی
/stats - آمار شخصی
/help - راهنما

برای استفاده، بات را به گروه اضافه کنید!
        """
        await update.message.reply_text(welcome_text)
    else:
        # ثبت گروه
        bot_instance.register_group(chat.id, chat.title)
        await update.message.reply_text(
            f"🎉 بات با موفقیت به گروه {chat.title} اضافه شد!\n"
            "چالش‌های ریاضی هر ۱۰ دقیقه ارسال خواهند شد."
        )
        
        # شروع ارسال چالش‌ها
        context.job_queue.run_repeating(
            send_challenge,
            interval=600,  # ۱۰ دقیقه
            first=10,
            chat_id=chat.id,
            name=f"challenge_{chat.id}"
        )

async def send_challenge(context: ContextTypes.DEFAULT_TYPE):
    """ارسال چالش ریاضی"""
    chat_id = context.job.chat_id
    
    # دریافت سطح سختی گروه
    conn = sqlite3.connect(bot_instance.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT difficulty_level FROM groups WHERE group_id = ?', (chat_id,))
    result = cursor.fetchone()
    difficulty = result[0] if result else 1
    conn.close()
    
    # تولید چالش
    question, answer = bot_instance.generate_math_challenge(difficulty)
    
    # ذخیره چالش در دیتابیس
    conn = sqlite3.connect(bot_instance.db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO challenges (group_id, question, correct_answer, difficulty)
        VALUES (?, ?, ?, ?)
    ''', (chat_id, question, answer, difficulty))
    challenge_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # ذخیره چالش فعلی
    bot_instance.current_challenges[chat_id] = {
        'id': challenge_id,
        'answer': answer,
        'question': question
    }
    
    # ارسال چالش
    challenge_text = f"""
🧮 چالش ریاضی جدید!

❓ {question}

⏰ زمان: ۱۰ دقیقه
🏆 امتیاز: ۱۰ امتیاز
📊 سطح: {'آسان' if difficulty == 1 else 'متوسط' if difficulty == 2 else 'سخت'}

اولین نفری که جواب درست بدهد برنده است! 🎉
    """
    
    await context.bot.send_message(chat_id=chat_id, text=challenge_text)
    
    # تایمر برای نمایش جواب
    context.job_queue.run_once(
        show_answer,
        when=600,  # ۱۰ دقیقه
        chat_id=chat_id,
        data={'challenge_id': challenge_id, 'answer': answer, 'question': question}
    )

async def show_answer(context: ContextTypes.DEFAULT_TYPE):
    """نمایش جواب چالش"""
    chat_id = context.job.chat_id
    data = context.job.data
    
    # بررسی اینکه آیا چالش حل شده یا نه
    conn = sqlite3.connect(bot_instance.db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT solved_by FROM challenges WHERE id = ?', (data['challenge_id'],))
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0]:
        return  # چالش قبلاً حل شده
    
    answer_text = f"""
⏰ زمان تمام شد!

❓ سوال: {data['question']}
✅ جواب صحیح: {data['answer']}

متأسفانه هیچ کس نتوانست جواب درست بدهد.
چالش بعدی به زودی ارسال می‌شود! 🔄
    """
    
    await context.bot.send_message(chat_id=chat_id, text=answer_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش پیام‌ها برای بررسی جواب"""
    if update.effective_chat.type == 'private':
        return
    
    user = update.effective_user
    chat_id = update.effective_chat.id
    message_text = update.message.text
    
    # ثبت کاربر
    bot_instance.register_user(user.id, user.username, user.first_name)
    
    # بررسی وجود چالش فعال
    if chat_id not in bot_instance.current_challenges:
        return
    
    try:
        user_answer = int(message_text.strip())
        correct_answer = bot_instance.current_challenges[chat_id]['answer']
        challenge_id = bot_instance.current_challenges[chat_id]['id']
        
        if user_answer == correct_answer:
            # جواب درست
            bot_instance.update_user_score(user.id, True)
            
            # به‌روزرسانی چالش در دیتابیس
            conn = sqlite3.connect(bot_instance.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE challenges 
                SET solved_by = ?, solved_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (user.id, challenge_id))
            conn.commit()
            conn.close()
            
            # حذف چالش از حافظه
            del bot_instance.current_challenges[chat_id]
            
            # ارسال پیام تبریک
            congratulations = f"""
🎉 تبریک {user.first_name}!

✅ جواب شما درست بود: {correct_answer}
🏆 ۱۰ امتیاز دریافت کردید!

چالش بعدی به زودی ارسال می‌شود! 🔄
            """
            
            await update.message.reply_text(congratulations)
            
    except ValueError:
        # پیام عدد نیست
        pass

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش جدول رتبه‌بندی"""
    results = bot_instance.get_leaderboard()
    
    if not results:
        await update.message.reply_text("هنوز هیچ کس امتیازی کسب نکرده است! 🤔")
        return
    
    leaderboard_text = "🏆 جدول رتبه‌بندی:\n\n"
    
    for i, (first_name, username, score, correct, total) in enumerate(results, 1):
        accuracy = (correct / total * 100) if total > 0 else 0
        username_display = f"@{username}" if username else "بدون نام کاربری"
        
        leaderboard_text += f"{i}. {first_name} ({username_display})\n"
        leaderboard_text += f"   💯 امتیاز: {score}\n"
        leaderboard_text += f"   ✅ درست: {correct}/{total} ({accuracy:.1f}%)\n\n"
    
    await update.message.reply_text(leaderboard_text)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آمار شخصی"""
    user_id = update.effective_user.id
    
    conn = sqlite3.connect(bot_instance.db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT score, correct_answers, total_answers, join_date
        FROM users WHERE user_id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        await update.message.reply_text("شما هنوز ثبت نشده‌اید! از دستور /start استفاده کنید.")
        return
    
    score, correct, total, join_date = result
    accuracy = (correct / total * 100) if total > 0 else 0
    
    stats_text = f"""
📊 آمار شخصی شما:

🏆 امتیاز کل: {score}
✅ پاسخ‌های درست: {correct}
📝 کل پاسخ‌ها: {total}
🎯 درصد صحت: {accuracy:.1f}%
📅 تاریخ عضویت: {join_date[:10]}

برای مشاهده رتبه‌بندی از /leaderboard استفاده کنید!
    """
    
    await update.message.reply_text(stats_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """راهنمای استفاده"""
    help_text = """
🤖 راهنمای بات چالش ریاضی

📋 دستورات:
/start - شروع و ثبت نام
/leaderboard - جدول رتبه‌بندی
/stats - آمار شخصی
/help - این راهنما

🎮 نحوه بازی:
• بات هر ۱۰ دقیقه یک چالش ریاضی ارسال می‌کند
• اولین نفری که جواب درست بدهد ۱۰ امتیاز می‌گیرد
• امتیازات در جدول رتبه‌بندی ثبت می‌شود

🏆 سطوح سختی:
• آسان: جمع و تفریق اعداد کوچک
• متوسط: عملیات ترکیبی
• سخت: محاسبات پیچیده‌تر

برای مدیریت بات با سازنده تماس بگیرید.
    """
    
    await update.message.reply_text(help_text)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پنل مدیریت (فقط برای مالک)"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("شما دسترسی به این بخش ندارید! ❌")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 آمار کلی", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 لیست گروه‌ها", callback_data="admin_groups")],
        [InlineKeyboardButton("🏆 برترین کاربران", callback_data="admin_top_users")],
        [InlineKeyboardButton("⚙️ تنظیمات", callback_data="admin_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔧 پنل مدیریت بات\n\nگزینه مورد نظر را انتخاب کنید:",
        reply_markup=reply_markup
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش کال‌بک‌های پنل مدیریت"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != OWNER_ID:
        await query.edit_message_text("دسترسی غیرمجاز! ❌")
        return
    
    if query.data == "admin_stats":
        conn = sqlite3.connect(bot_instance.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM groups WHERE is_active = 1')
        active_groups = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM challenges')
        total_challenges = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM challenges WHERE solved_by IS NOT NULL')
        solved_challenges = cursor.fetchone()[0]
        
        conn.close()
        
        stats_text = f"""
📊 آمار کلی بات:

👥 کل کاربران: {total_users}
🏘️ گروه‌های فعال: {active_groups}
🧮 کل چالش‌ها: {total_challenges}
✅ چالش‌های حل شده: {solved_challenges}
📈 نرخ حل: {(solved_challenges/total_challenges*100):.1f}%
        """
        
        await query.edit_message_text(stats_text)

def main():
    """تابع اصلی"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN تنظیم نشده است!")
        return
    
    # ایجاد اپلیکیشن
    application = Application.builder().token(BOT_TOKEN).build()
    
    # اضافه کردن هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("leaderboard", leaderboard))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(admin_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # اجرای بات
    logger.info("بات شروع به کار کرد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
