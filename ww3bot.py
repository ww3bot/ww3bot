import os
import asyncio
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
import logging
import json

# تنظیم لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# متغیرهای محیطی
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID', '0'))
CHANNEL_ID = os.getenv('CHANNEL_ID', '')

class ChannelManagerBot:
    def __init__(self):
        self.db_path = 'channel_manager.db'
        self.init_database()
        self.managed_channels = {}
        
    def init_database(self):
        """ایجاد جداول دیتابیس"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # جدول کانال‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                channel_name TEXT,
                channel_username TEXT,
                member_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول پست‌ها
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                message_id INTEGER,
                content TEXT,
                post_type TEXT,
                views INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scheduled_time TIMESTAMP DEFAULT NULL
            )
        ''')
        
        # جدول آمار روزانه
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                date DATE,
                member_count INTEGER,
                new_members INTEGER DEFAULT 0,
                left_members INTEGER DEFAULT 0,
                posts_count INTEGER DEFAULT 0,
                total_views INTEGER DEFAULT 0
            )
        ''')
        
        # جدول تنظیمات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                channel_id INTEGER,
                setting_key TEXT,
                setting_value TEXT,
                PRIMARY KEY (channel_id, setting_key)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_channel(self, channel_id, channel_name, channel_username=None):
        """اضافه کردن کانال جدید"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO channels 
            (channel_id, channel_name, channel_username, last_update)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (channel_id, channel_name, channel_username))
        
        conn.commit()
        conn.close()
    
    def get_channel_stats(self, channel_id):
        """دریافت آمار کانال"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # آمار کلی کانال
        cursor.execute('''
            SELECT channel_name, member_count, added_date
            FROM channels WHERE channel_id = ?
        ''', (channel_id,))
        channel_info = cursor.fetchone()
        
        # تعداد پست‌ها
        cursor.execute('''
            SELECT COUNT(*) FROM posts WHERE channel_id = ?
        ''', (channel_id,))
        posts_count = cursor.fetchone()[0]
        
        # مجموع بازدیدها
        cursor.execute('''
            SELECT SUM(views) FROM posts WHERE channel_id = ?
        ''', (channel_id,))
        total_views = cursor.fetchone()[0] or 0
        
        # آمار هفته گذشته
        cursor.execute('''
            SELECT SUM(new_members), SUM(left_members), SUM(posts_count)
            FROM daily_stats 
            WHERE channel_id = ? AND date >= date('now', '-7 days')
        ''', (channel_id,))
        weekly_stats = cursor.fetchone()
        
        conn.close()
        
        return {
            'channel_info': channel_info,
            'posts_count': posts_count,
            'total_views': total_views,
            'weekly_stats': weekly_stats
        }
    
    def save_post(self, channel_id, message_id, content, post_type):
        """ذخیره اطلاعات پست"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO posts (channel_id, message_id, content, post_type)
            VALUES (?, ?, ?, ?)
        ''', (channel_id, message_id, content, post_type))
        
        conn.commit()
        conn.close()

# ایجاد نمونه از کلاس بات
bot_instance = ChannelManagerBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور شروع"""
    user_id = update.effective_user.id
    chat = update.effective_chat
    
    if user_id != OWNER_ID and chat.type == 'private':
        await update.message.reply_text("❌ شما دسترسی به این بات ندارید!")
        return
    
    if chat.type == 'private':
        welcome_text = f"""
🤖 سلام مالک عزیز!

به بات مدیریت کانال خوش آمدید!

🎯 قابلیت‌های بات:
• مدیریت کامل کانال‌ها
• آمار و گزارش‌گیری
• ارسال و مدیریت پست‌ها
• نظارت بر اعضا

📋 دستورات اصلی:
/panel - پنل مدیریت
/stats - آمار کانال‌ها
/channels - لیست کانال‌ها
/help - راهنما

برای شروع از دستور /panel استفاده کنید.
        """
        
        await update.message.reply_text(welcome_text)
    
    elif chat.type == 'channel':
        # بات به کانال اضافه شده
        try:
            member_count = await context.bot.get_chat_member_count(chat.id)
            bot_instance.add_channel(chat.id, chat.title, chat.username)
            
            # به‌روزرسانی تعداد اعضا
            conn = sqlite3.connect(bot_instance.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE channels SET member_count = ?, last_update = CURRENT_TIMESTAMP
                WHERE channel_id = ?
            ''', (member_count, chat.id))
            conn.commit()
            conn.close()
            
            # اطلاع به مالک
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"✅ کانال جدید شناسایی شد!\n\n"
                     f"📢 نام: {chat.title}\n"
                     f"🔗 آیدی: {chat.id}\n"
                     f"👥 اعضا: {member_count:,}\n"
                     f"📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
        except Exception as e:
            logger.error(f"خطا در شناسایی کانال: {e}")

async def my_chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تشخیص تغییرات عضویت بات در کانال‌ها"""
    result = update.my_chat_member
    chat = result.chat
    new_member = result.new_chat_member
    old_member = result.old_chat_member
    
    # فقط برای کانال‌ها
    if chat.type != 'channel':
        return
    
    # اگر بات ادمین شد
    if (new_member.status in ['administrator'] and 
        old_member.status in ['left', 'kicked', 'member']):
        
        try:
            member_count = await context.bot.get_chat_member_count(chat.id)
            bot_instance.add_channel(chat.id, chat.title, chat.username)
            
            # به‌روزرسانی تعداد اعضا
            conn = sqlite3.connect(bot_instance.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE channels SET member_count = ?, last_update = CURRENT_TIMESTAMP
                WHERE channel_id = ?
            ''', (member_count, chat.id))
            conn.commit()
            conn.close()
            
            # اطلاع به مالک
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"🎉 بات به کانال جدید اضافه شد!\n\n"
                     f"📢 نام: {chat.title}\n"
                     f"🔗 آیدی: {chat.id}\n"
                     f"👥 اعضا: {member_count:,}\n"
                     f"📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                     f"✅ کانال در دیتابیس ثبت شد!"
            )
            
        except Exception as e:
            logger.error(f"خطا در ثبت کانال جدید: {e}")
    
    # اگر بات از کانال حذف شد
    elif (new_member.status in ['left', 'kicked'] and 
          old_member.status in ['administrator', 'member']):
        
        # غیرفعال کردن کانال در دیتابیس
        conn = sqlite3.connect(bot_instance.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE channels SET is_active = 0, last_update = CURRENT_TIMESTAMP
            WHERE channel_id = ?
        ''', (chat.id,))
        conn.commit()
        conn.close()
        
        # اطلاع به مالک
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"⚠️ بات از کانال حذف شد!\n\n"
                 f"📢 نام: {chat.title}\n"
                 f"🔗 آیدی: {chat.id}\n"
                 f"📅 تاریخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                 f"❌ کانال غیرفعال شد."
        )

async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پنل مدیریت اصلی"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ دسترسی غیرمجاز!")
        return
    
    keyboard = [
        [
            InlineKeyboardButton("📊 آمار کانال‌ها", callback_data="stats_channels"),
            InlineKeyboardButton("📝 مدیریت پست‌ها", callback_data="manage_posts")
        ],
        [
            InlineKeyboardButton("👥 مدیریت اعضا", callback_data="manage_members"),
            InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")
        ],
        [
            InlineKeyboardButton("📈 گزارش‌ها", callback_data="reports"),
            InlineKeyboardButton("🔄 به‌روزرسانی", callback_data="refresh_data")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🎛️ پنل مدیریت کانال\n\nگزینه مورد نظر را انتخاب کنید:",
        reply_markup=reply_markup
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آمار کانال‌ها"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ دسترسی غیرمجاز!")
        return
    
    conn = sqlite3.connect(bot_instance.db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM channels WHERE is_active = 1')
    channels = cursor.fetchall()
    
    if not channels:
        await update.message.reply_text("هیچ کانالی ثبت نشده است!")
        conn.close()
        return
    
    stats_text = "📊 آمار کانال‌های مدیریت شده:\n\n"
    
    for channel in channels:
        channel_id, name, username, member_count, _, added_date, _ = channel
        
        # آمار پست‌ها
        cursor.execute('SELECT COUNT(*) FROM posts WHERE channel_id = ?', (channel_id,))
        posts_count = cursor.fetchone()[0]
        
        # مجموع بازدیدها
        cursor.execute('SELECT SUM(views) FROM posts WHERE channel_id = ?', (channel_id,))
        total_views = cursor.fetchone()[0] or 0
        
        stats_text += f"📢 {name}\n"
        if username:
            stats_text += f"   🔗 @{username}\n"
        stats_text += f"   👥 اعضا: {member_count:,}\n"
        stats_text += f"   📝 پست‌ها: {posts_count}\n"
        stats_text += f"   👁️ بازدیدها: {total_views:,}\n"
        stats_text += f"   📅 تاریخ اضافه: {added_date[:10]}\n\n"
    
    conn.close()
    await update.message.reply_text(stats_text)

async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لیست کانال‌ها"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ دسترسی غیرمجاز!")
        return
    
    conn = sqlite3.connect(bot_instance.db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT channel_id, channel_name, channel_username FROM channels WHERE is_active = 1')
    channels = cursor.fetchall()
    conn.close()
    
    if not channels:
        await update.message.reply_text("هیچ کانالی ثبت نشده است!")
        return
    
    keyboard = []
    for channel_id, name, username in channels:
        display_name = f"{name} (@{username})" if username else name
        keyboard.append([InlineKeyboardButton(display_name, callback_data=f"channel_{channel_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📋 کانال‌های مدیریت شده:\n\nروی کانال مورد نظر کلیک کنید:",
        reply_markup=reply_markup
    )

async def send_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ارسال پیام به کانال"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ دسترسی غیرمجاز!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ لطفاً آیدی کانال و متن پیام را وارد کنید:\n"
            "/send -1001234567890 متن پیام شما"
        )
        return
    
    try:
        channel_id = int(context.args[0])
        message_text = ' '.join(context.args[1:])
        
        if not message_text:
            await update.message.reply_text("❌ متن پیام نمی‌تواند خالی باشد!")
            return
        
        # ارسال پیام به کانال
        sent_message = await context.bot.send_message(
            chat_id=channel_id,
            text=message_text,
            parse_mode=ParseMode.HTML
        )
        
        # ذخیره در دیتابیس
        bot_instance.save_post(channel_id, sent_message.message_id, message_text, 'text')
        
        await update.message.reply_text(
            f"✅ پیام با موفقیت به کانال ارسال شد!\n"
            f"🆔 شناسه پیام: {sent_message.message_id}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ آیدی کانال باید عدد باشد!")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ارسال پیام: {str(e)}")

async def get_channel_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت اطلاعات کانال"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ دسترسی غیرمجاز!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ لطفاً آیدی کانال را وارد کنید:\n"
            "/info -1001234567890"
        )
        return
    
    try:
        channel_id = int(context.args[0])
        
        # دریافت اطلاعات کانال
        chat = await context.bot.get_chat(channel_id)
        member_count = await context.bot.get_chat_member_count(channel_id)
        
        # ذخیره/به‌روزرسانی در دیتابیس
        bot_instance.add_channel(channel_id, chat.title, chat.username)
        
        # به‌روزرسانی تعداد اعضا
        conn = sqlite3.connect(bot_instance.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE channels SET member_count = ?, last_update = CURRENT_TIMESTAMP
            WHERE channel_id = ?
        ''', (member_count, channel_id))
        conn.commit()
        conn.close()
        
        info_text = f"""
📢 اطلاعات کانال:

🏷️ نام: {chat.title}
🔗 نام کاربری: @{chat.username if chat.username else 'ندارد'}
🆔 آیدی: {channel_id}
👥 تعداد اعضا: {member_count:,}
📝 توضیحات: {chat.description if chat.description else 'ندارد'}

✅ اطلاعات در دیتابیس به‌روزرسانی شد.
        """
        
        await update.message.reply_text(info_text)
        
    except ValueError:
        await update.message.reply_text("❌ آیدی کانال باید عدد باشد!")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در دریافت اطلاعات: {str(e)}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش کال‌بک‌ها"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != OWNER_ID:
        await query.edit_message_text("❌ دسترسی غیرمجاز!")
        return
    
    data = query.data
    
    if data == "stats_channels":
        conn = sqlite3.connect(bot_instance.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM channels WHERE is_active = 1')
        total_channels = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(member_count) FROM channels WHERE is_active = 1')
        total_members = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT COUNT(*) FROM posts')
        total_posts = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(views) FROM posts')
        total_views = cursor.fetchone()[0] or 0
        
        conn.close()
        
        stats_text = f"""
📊 آمار کلی:

📢 کانال‌های فعال: {total_channels}
👥 مجموع اعضا: {total_members:,}
📝 کل پست‌ها: {total_posts}
👁️ مجموع بازدیدها: {total_views:,}

📈 میانگین اعضا در هر کانال: {total_members//total_channels if total_channels > 0 else 0:,}
📊 میانگین بازدید هر پست: {total_views//total_posts if total_posts > 0 else 0}
        """
        
        await query.edit_message_text(stats_text)
    
    elif data == "manage_posts":
        keyboard = [
            [InlineKeyboardButton("📝 ارسال پست جدید", callback_data="new_post")],
            [InlineKeyboardButton("📋 لیست پست‌ها", callback_data="list_posts")],
            [InlineKeyboardButton("⏰ پست‌های زمان‌بندی شده", callback_data="scheduled_posts")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📝 مدیریت پست‌ها\n\nگزینه مورد نظر را انتخاب کنید:",
            reply_markup=reply_markup
        )
    
    elif data == "manage_members":
        keyboard = [
            [InlineKeyboardButton("👥 آمار اعضا", callback_data="member_stats")],
            [InlineKeyboardButton("📈 نمودار رشد", callback_data="growth_chart")],
            [InlineKeyboardButton("🔍 جستجوی کاربر", callback_data="search_user")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "👥 مدیریت اعضا\n\nگزینه مورد نظر را انتخاب کنید:",
            reply_markup=reply_markup
        )
    
    elif data == "settings":
        keyboard = [
            [InlineKeyboardButton("🔧 تنظیمات کانال", callback_data="channel_settings")],
            [InlineKeyboardButton("📊 تنظیمات گزارش", callback_data="report_settings")],
            [InlineKeyboardButton("💾 بک‌آپ دیتابیس", callback_data="backup_db")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚙️ تنظیمات\n\nگزینه مورد نظر را انتخاب کنید:",
            reply_markup=reply_markup
        )
    
    elif data == "refresh_data":
        await query.edit_message_text("🔄 در حال به‌روزرسانی اطلاعات...")
        
        # به‌روزرسانی اطلاعات کانال‌ها
        conn = sqlite3.connect(bot_instance.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT channel_id FROM channels WHERE is_active = 1')
        channels = cursor.fetchall()
        
        updated_count = 0
        for (channel_id,) in channels:
            try:
                member_count = await context.bot.get_chat_member_count(channel_id)
                cursor.execute('''
                    UPDATE channels SET member_count = ?, last_update = CURRENT_TIMESTAMP
                    WHERE channel_id = ?
                ''', (member_count, channel_id))
                updated_count += 1
            except:
                continue
        
        conn.commit()
        conn.close()
        
        await query.edit_message_text(
            f"✅ اطلاعات به‌روزرسانی شد!\n"
            f"📊 {updated_count} کانال به‌روزرسانی شد."
        )
    
    elif data.startswith("channel_"):
        channel_id = int(data.split("_")[1])
        stats = bot_instance.get_channel_stats(channel_id)
        
        if stats['channel_info']:
            name, member_count, added_date = stats['channel_info']
            
            channel_text = f"""
📢 {name}

👥 اعضا: {member_count:,}
📝 پست‌ها: {stats['posts_count']}
👁️ بازدیدها: {stats['total_views']:,}
📅 تاریخ اضافه: {added_date[:10]}

📊 آمار هفته گذشته:
➕ عضو جدید: {stats['weekly_stats'][0] or 0}
➖ خروج: {stats['weekly_stats'][1] or 0}
📝 پست جدید: {stats['weekly_stats'][2] or 0}
            """
            
            keyboard = [
                [InlineKeyboardButton("📝 ارسال پست", callback_data=f"send_post_{channel_id}")],
                [InlineKeyboardButton("📊 آمار کامل", callback_data=f"full_stats_{channel_id}")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back_channels")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(channel_text, reply_markup=reply_markup)

async def scan_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اسکن و شناسایی کانال‌های موجود"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ دسترسی غیرمجاز!")
        return
    
    await update.message.reply_text("🔍 در حال اسکن کانال‌ها...")
    
    try:
        # دریافت لیست چت‌های بات (محدود به تلگرام)
        # این روش کار نمی‌کند، پس از کاربر می‌خواهیم آیدی کانال‌ها را بدهد
        
        scan_text = """
🔍 برای شناسایی کانال‌ها:

1️⃣ روش خودکار:
• بات را به کانال اضافه کنید
• ادمین کنید (با دسترسی پیام)
• خودکار شناسایی می‌شود

2️⃣ روش دستی:
• از دستور /info [channel_id] استفاده کنید
• مثال: /info -1001234567890

3️⃣ دریافت آیدی کانال:
• به کانال برید
• @userinfobot را فوروارد کنید
• آیدی را کپی کنید

💡 نکته: بات باید ادمین کانال باشد تا بتواند آمار دریافت کند.
        """
        
        await update.message.reply_text(scan_text)
        
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در اسکن: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """راهنمای استفاده"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ دسترسی غیرمجاز!")
        return
    
    help_text = """
🤖 راهنمای بات مدیریت کانال

📋 دستورات اصلی:
/start - شروع بات
/panel - پنل مدیریت
/stats - آمار کانال‌ها
/channels - لیست کانال‌ها
/scan - اسکن کانال‌ها
/help - این راهنما

📝 دستورات پست:
/send [channel_id] [text] - ارسال پست
/info [channel_id] - اطلاعات کانال

🎯 نکات مهم:
• بات را به کانال اضافه کرده و ادمین کنید
• برای دریافت آیدی کانال از @userinfobot استفاده کنید
• آیدی کانال‌های عمومی با -100 شروع می‌شود
• بات خودکار کانال‌ها را شناسایی می‌کند

📞 پشتیبانی:
در صورت بروز مشکل با سازنده تماس بگیرید.
    """
    
    await update.message.reply_text(help_text)

def main():
    """تابع اصلی"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN تنظیم نشده است!")
        return
    
    if OWNER_ID == 0:
        logger.error("OWNER_ID تنظیم نشده است!")
        return
    
    # ایجاد اپلیکیشن
    application = Application.builder().token(BOT_TOKEN).build()
    
    # اضافه کردن هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("panel", panel))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("channels", channels_command))
    application.add_handler(CommandHandler("send", send_to_channel))
    application.add_handler(CommandHandler("info", get_channel_info))
    application.add_handler(CommandHandler("scan", scan_channels))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(callback_handler))
    
    # هندلر برای تشخیص تغییرات عضویت بات
    from telegram.ext import ChatMemberHandler
    application.add_handler(ChatMemberHandler(my_chat_member_handler, ChatMemberHandler.MY_CHAT_MEMBER))
    
    # اجرای بات
    logger.info("بات مدیریت کانال شروع به کار کرد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
