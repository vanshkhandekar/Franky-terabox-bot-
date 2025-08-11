import asyncio
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)
from telegram.error import BadRequest

# ===== CONFIG =====
BOT_TOKEN = "8269947278:AAE4Jogxlstl0sEOpuY1pGnrPwy3TRrILT4"
ADMIN_ID = 5924901610
OWNER_USERNAME = "@Thecyberfranky"
CHANNELS = ["@franky_intro"]
CHANNEL_INVITE_LINK = "https://t.me/franky_intro"

WELCOME_MSG = (
    "Welcome to Terabox_byfranky_bot!\n\n"
    f"For any help, contact {OWNER_USERNAME}."
)

JOIN_CHANNEL_MSG = (
    "You must join our channel to use this bot."
)

SUBSCRIBE_MSG = (
    f"To get premium membership, please contact {OWNER_USERNAME}.\n\n"
    "Plans:\n- 1 Month\n- Lifetime"
)

# ===== USER STORAGE =====
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
        if (now - self.last_reset) > timedelta(days=1):
            self.used_today = 0
            self.last_reset = now

    def can_use(self):
        self.reset_daily()
        if self.is_premium:
            return True
        return self.used_today < self.daily_limit

    def add_use(self):
        self.used_today += 1

    def add_referral(self):
        self.referrals += 1
        if not self.is_premium:
            self.daily_limit += 1

# ===== HELPERS =====

async def check_channel_membership(update: Update, user_id: int) -> bool:
    for channel in CHANNELS:
        try:
            member = await update.bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except BadRequest:
            return False
    return True

async def send_join_channel_message(update: Update):
    keyboard = [
        [InlineKeyboardButton("Join Our Channel", url=CHANNEL_INVITE_LINK)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(JOIN_CHANNEL_MSG, reply_markup=reply_markup)

def require_channel_join(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not await check_channel_membership(update, user_id):
            await send_join_channel_message(update)
            return
        await func(update, context)
    return wrapper

async def auto_delete_message(message, delay_seconds=1800):
    await asyncio.sleep(delay_seconds)
    try:
        await message.delete()
    except:
        pass

# ===== COMMANDS =====

@require_channel_join
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in users_db:
        users_db[user_id] = User(user_id)
    sent = await update.message.reply_text(WELCOME_MSG)
    asyncio.create_task(auto_delete_message(update.message))
    asyncio.create_task(auto_delete_message(sent))

@require_channel_join
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - This message\n"
        "/subscribe - How to get premium\n"
        "/status - Your subscription status\n"
        "/approve <user_id> - [Admin] Approve premium\n"
        "/remove <user_id> - [Admin] Remove premium\n"
        "/announce <message> - [Admin] Broadcast message\n"
        "/refer <user_id> - Refer user, get extra chance\n"
        "\nSend terabox link to get file/video links."
    )
    sent = await update.message.reply_text(help_text)
    asyncio.create_task(auto_delete_message(update.message))
    asyncio.create_task(auto_delete_message(sent))

@require_channel_join
async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Get Subscription", url=CHANNEL_INVITE_LINK)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    sent = await update.message.reply_text(SUBSCRIBE_MSG, reply_markup=reply_markup)
    asyncio.create_task(auto_delete_message(update.message))
    asyncio.create_task(auto_delete_message(sent))

@require_channel_join
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = users_db.get(user_id)
    if not user:
        await update.message.reply_text("You are not registered. Send /start first.")
        return
    status = "Premium" if user.is_premium else "Normal"
    text = (
        f"Status: {status}\n"
        f"Daily Usage: {user.used_today}/{user.daily_limit}\n"
        f"Referrals: {user.referrals}"
    )
    sent = await update.message.reply_text(text)
    asyncio.create_task(auto_delete_message(update.message))
    asyncio.create_task(auto_delete_message(sent))

@require_channel_join
async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /approve <user_id>")
        return
    target_id = int(context.args[0])
    user = users_db.get(target_id)
    if not user:
        user = User(target_id)
        users_db[target_id] = user
    user.is_premium = True
    user.daily_limit = 99999
    await update.message.reply_text(f"✅ User {target_id} approved as Premium.")

@require_channel_join
async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /remove <user_id>")
        return
    target_id = int(context.args[0])
    user = users_db.get(target_id)
    if not user:
        await update.message.reply_text("User not found.")
        return
    user.is_premium = False
    user.daily_limit = 10
    await update.message.reply_text(f"✅ User {target_id} premium removed.")

@require_channel_join
async def announce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Usage: /announce <message>")
        return
    sent_count = 0
    for u_id in users_db:
        try:
            await context.bot.send_message(chat_id=u_id, text=f"📢 Announcement:\n\n{message}")
            sent_count += 1
        except:
            pass
    await update.message.reply_text(f"✅ Announcement sent to {sent_count} users.")

@require_channel_join
async def refer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /refer <user_id>")
        return
    referrer_id = update.effective_user.id
    referred_id = int(context.args[0])
    if referred_id == referrer_id:
        await update.message.reply_text("You cannot refer yourself.")
        return
    referred_user = users_db.get(referred_id)
    if not referred_user:
        await update.message.reply_text("Referred user not found or not started the bot.")
        return
    referrer = users_db.get(referrer_id)
    if not referrer:
        await update.message.reply_text("You are not registered. Send /start first.")
        return
    referrer.add_referral()
    await update.message.reply_text(f"Thanks for referral! +1 extra chance. Total referrals: {referrer.referrals}")

@require_channel_join
async def handle_terabox_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = users_db.get(user_id)
    if not user:
        user = User(user_id)
        users_db[user_id] = user

    if not user.can_use():
        await update.message.reply_text("Daily limit reached! Upgrade to premium or refer someone to get more chances.")
        return
    user.add_use()

    links = [word for word in update.message.text.split() if "terabox.com" in word]
    if not links:
        await update.message.reply_text("No valid terabox link found.")
        return

    if not user.is_premium and len(links) > 1:
        await update.message.reply_text("Normal users can send only one link at a time.")
        return

    for link in links:
        # Placeholder thumbnail image
        thumbnail = "https://telegra.ph/file/8f7e1b9a6d2a61867c9f0.jpg"

        direct_link = link + "/direct"
        streaming_links = []
        if user.is_premium:
            streaming_links = [f"{link}/stream{i}" for i in range(1, 6)]
        else:
            streaming_links = [f"{link}/stream1", f"{link}/stream2"]

        text = f"🎥 Terabox File\nLink: {link}\n\nDownload or stream from below:\n"
        text += f"• Direct Download: {direct_link}\n"
        for i, s_link in enumerate(streaming_links, 1):
            text += f"• Stream {i}: {s_link}\n"

        buttons = [[InlineKeyboardButton("Download", url=direct_link)]]
        for i, s_link in enumerate(streaming_links, 1):
            buttons.append([InlineKeyboardButton(f"Stream {i}", url=s_link)])
        keyboard = InlineKeyboardMarkup(buttons)

        sent = await update.message.reply_photo(
            photo=thumbnail,
            caption=text,
            reply_markup=keyboard,
        )
        asyncio.create_task(auto_delete_message(update.message))
        asyncio.create_task(auto_delete_message(sent))

@require_channel_join
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sent = await update.message.reply_text("Sorry, I didn't understand that command.")
    asyncio.create_task(auto_delete_message(update.message))
    asyncio.create_task(auto_delete_message(sent))

# ===== RUN BOT =====

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("subscribe", subscribe_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(CommandHandler("remove", remove_command))
    app.add_handler(CommandHandler("announce", announce_command))
    app.add_handler(CommandHandler("refer", refer_command))
    app.add_handler(MessageHandler(filters.Regex(r".*(terabox\.com).*"), handle_terabox_link))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
