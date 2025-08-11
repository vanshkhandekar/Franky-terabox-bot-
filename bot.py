import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from telegram.error import BadRequest
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
CHANNEL_USERNAME = "@franky_intro"
OWNER_USERNAME = "@Thecyberfranky"

# Messages
WELCOME_MESSAGE = (
    "Welcome to Terabox_byfranky_bot! For any help, contact @Thecyberfranky."
)
PREMIUM_INFO = (
    "To get premium membership, please contact @Thecyberfranky."
)
JOIN_CHANNEL_MSG = (
    f"Please join our channel {CHANNEL_USERNAME} to use this bot."
)
LIMIT_REACHED_MSG = (
    "You have reached your daily limit of 10 Terabox links. Refer friends to get extra usage."
)
REFERRAL_SUCCESS_MSG = (
    "Thanks for referring! You got 1 extra chance to use the bot today."
)
INVALID_LINK_MSG = (
    "Oops! The link you sent is invalid or expired. Please check and try again."
)
SUBSCRIPTION_PENDING_MSG = (
    "Your premium subscription request is pending approval. Please wait for confirmation."
)
PREMIUM_BULK_LIMIT_MSG = (
    "As a premium user, you can send up to 10 Terabox links at once."
)
AUTO_DELETE_NOTICE_MSG = (
    "Messages and files will be deleted automatically after 30 minutes to keep the bot clean."
)
CONTACT_OWNER_MSG = (
    "For any issues or help, contact the bot owner @Thecyberfranky."
)

# Dummy user database (In production use a real database)
users_db = {}

# To store user usage and subscription status
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
    try:
        member = await update.effective_chat.get_member(user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        else:
            return False
    except BadRequest:
        # Means user is not in channel or bot can't access member info
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    # Check if user joined the required channel
    if not await check_channel_membership(update, user_id):
        await update.message.reply_text(JOIN_CHANNEL_MSG)
        return

    if user_id not in users_db:
        users_db[user_id] = User(user_id)

    await update.message.reply_text(WELCOME_MESSAGE)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/time - Show current IST time\n"
        "/subscribe - Get premium subscription info\n"
        "/status - Check your subscription status\n"
    )
    await update.message.reply_text(help_text)

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.utcnow() + timedelta(hours=5, minutes=30)
    await update.message.reply_text(f"Current IST time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{PREMIUM_INFO}\n\nSubscribe plans:\n1 Month\nLifetime\n\nContact @Thecyberfranky to buy."
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = users_db.get(user_id)
    if not user:
        await update.message.reply_text("You are not registered. Send /start first.")
        return
    status = "Premium User" if user.is_premium else "Normal User"
    await update.message.reply_text(f"Your status: {status}\nDaily usage: {user.used_today}/{user.daily_limit}")

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
