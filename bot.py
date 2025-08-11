import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)
from telegram.error import BadRequest
from datetime import datetime, timedelta

BOT_TOKEN = "8269947278:AAE4Jogxlstl0sEOpuY1pGnrPwy3TRrILT4"
ADMIN_ID = 5924901610

REQUIRED_CHANNELS = ["@franky_intro"]
CHANNEL_INVITE_LINK = "https://t.me/franky_intro"

OWNER_USERNAME = "@Thecyberfranky"

WELCOME_MESSAGE = (
    "Welcome to Terabox_byfranky_bot! For any help, contact @Thecyberfranky."
)
JOIN_CHANNEL_MSG = (
    "You must join our channel(s) to use this bot before using commands."
)

users_db = {}

class User:
    def __init__(self, user_id):
        self.user_id = user_id
        self.is_premium = False
        self.daily_limit = 10
        self.used_today = 0
        self.referrals = 0
        self.last_reset = datetime.utcnow()

    def reset_daily(self):
        now = datetime.utcnow()
        if now - self.last_reset > timedelta(days=1):
            self.used_today = 0
            self.last_reset = now

async def check_channel_membership(update: Update, user_id: int) -> bool:
    for channel in REQUIRED_CHANNELS:
        try:
            member = await update.bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except BadRequest:
            return False
    return True

async def send_join_channel_message(update: Update):
    keyboard = [
        [InlineKeyboardButton(text="Join Our Channel", url=CHANNEL_INVITE_LINK)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        JOIN_CHANNEL_MSG,
        reply_markup=reply_markup,
    )

def require_channel_join(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_channel_membership(update, user_id):
            await send_join_channel_message(update)
            return
        await func(update, context)
    return wrapper

@require_channel_join
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in users_db:
        users_db[user_id] = User(user_id)
    await update.message.reply_text(WELCOME_MESSAGE)

@require_channel_join
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/time - Show current IST time\n"
        "/subscribe - Get premium subscription info\n"
        "/status - Check your subscription status\n"
    )
    await update.message.reply_text(help_text)

@require_channel_join
async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    await update.message.reply_text(f"Current IST time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

@require_channel_join
async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"To get premium membership, please contact {OWNER_USERNAME}.\n\nSubscribe plans:\n1 Month\nLifetime"
    )

@require_channel_join
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = users_db.get(user_id)
    if not user:
        await update.message.reply_text("You are not registered. Send /start first.")
        return
    status = "Premium User" if user.is_premium else "Normal User"
    await update.message.reply_text(f"Your status: {status}\nDaily usage: {user.used_today}/{user.daily_limit}")

@require_channel_join
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sorry, I didn't understand that command.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(CommandHandler("subscribe", subscribe_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
