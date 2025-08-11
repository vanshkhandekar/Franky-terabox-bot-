import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Set this in Render environment variables
ADMIN_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))  # Set this in Render env vars
CHANNEL_USERNAME = "@franky_intro"
OWNER_USERNAME = "@Thecyberfranky"

WELCOME_MESSAGE = (
    "Welcome to Terabox_byfranky_bot! For any help, contact @Thecyberfranky."
)
JOIN_CHANNEL_MSG = f"Please join our channel {CHANNEL_USERNAME} to use this bot."

# Dummy user database
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
    try:
        member = await update.effective_chat.get_member(user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except BadRequest:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not await check_channel_membership(update, user_id):
        await update.message.reply_text(JOIN_CHANNEL_MSG)
        return

    if user_id not in users_db:
        users_db[user_id] = User(user_id)

    await update.message.reply_text(WELCOME_MESSAGE)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sorry, I didn't understand that command.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    print("Bot started with polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
