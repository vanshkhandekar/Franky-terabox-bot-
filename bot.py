import logging
from threading import Timer
from telegram import (
    Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
)
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters, CallbackContext
)
from terabox_downloader import TeraboxDL  # Correct package for PyPI

# ===== CONFIGURATION =====
BOT_TOKEN = "8269947278:AAGX87RM56PTLHABH1gbniSG3ooAoe9tbUI"  # Your provided token
ADMIN_ID = 5924901610
ADMIN_USERNAME = "@Thecyberfranky"
MANDATORY_CHANNEL = "@franky_intro"
CHANNEL_LINK = "https://t.me/franky_intro"

# ===== USER DATA STORAGE =====
users = {}  # user_id: {"type": "normal/premium", "usage": int, "referrals": int}

# ===== HELPER FUNCTIONS =====
def check_subscription(bot: Bot, user_id):
    try:
        member = bot.get_chat_member(MANDATORY_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def delete_later(context: CallbackContext, chat_id: int, message_id: int):
    Timer(1800, lambda: context.bot.delete_message(chat_id, message_id)).start()

def process_terabox_link(link: str, user_type: str):
    try:
        tdl = TeraboxDL(link)
        info = tdl.get_info()
        direct = tdl.get_download_url()

        title = info.get('name', 'Untitled')
        thumb = info.get('thumbnail')
        size = info.get('size', 'N/A')

        if user_type == "premium":
            links = [direct] + [f"{link}?stream={i}" for i in range(1, 6)]
        else:
            links = [direct] + [f"{link}?stream={i}" for i in range(1, 3)]

        return title, thumb, size, links
    except Exception as e:
        logging.error(f"TeraboxDL error: {e}")
        return None, None, None, None

# ===== COMMAND HANDLERS =====
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in users:
        users[user_id] = {"type": "normal", "usage": 0, "referrals": 0}

    if not check_subscription(context.bot, user_id):
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url=CHANNEL_LINK)]])
        update.message.reply_text("⚠️ Please join our channel to use this bot.", reply_markup=btn)
        return

    update.message.reply_text(
        f"Welcome to Terabox_byfranky_bot! 🚀\nFor any help, contact {ADMIN_USERNAME}."
    )

def help_cmd(update: Update, context: CallbackContext):
    msg = (
        "/start — Start Bot\n"
        "/help — Show Commands\n"
        "/subscribe — Premium Info\n"
        "/status — Usage & Referrals\n"
        "/approve <id> — Admin Only\n"
        "/remove <id> — Admin Only\n"
        "/refer <id> — Referral System"
    )
    update.message.reply_text(msg)

def status_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    data = users.get(user_id, {})
    update.message.reply_text(
        f"👤 Type: {data.get('type')}\n"
        f"📊 Usage: {data.get('usage')}\n"
        f"🎯 Referrals: {data.get('referrals')}"
    )

def subscribe_cmd(update: Update, context: CallbackContext):
    update.message.reply_text(
        "💎 Premium Plan: Unlimited links + bulk (10 at once)\nContact admin: @Thecyberfranky"
    )

def approve_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        if uid in users:
            users[uid]["type"] = "premium"
            update.message.reply_text(f"✅ User {uid} is now PREMIUM.")
    except:
        update.message.reply_text("❌ Invalid user ID.")

def remove_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        if uid in users:
            users[uid]["type"] = "normal"
            update.message.reply_text(f"User {uid} reverted to NORMAL.")
    except:
        update.message.reply_text("❌ Invalid user ID.")

def refer_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        ref_id = int(context.args[0])
        if ref_id in users and ref_id != user_id:
            users[user_id]["referrals"] += 1
            update.message.reply_text("🤝 Referral added! +1 daily usage.")
        else:
            update.message.reply_text("❌ Invalid referral ID.")
    except:
        update.message.reply_text("Use: /refer <user_id>")

# ===== MESSAGE HANDLER =====
def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not text.startswith("http"):
        return

    if not check_subscription(context.bot, user_id):
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url=CHANNEL_LINK)]])
        update.message.reply_text("⚠️ Join our channel first.", reply_markup=btn)
        return

    user_info = users.get(user_id, {"type": "normal", "usage": 0, "referrals": 0})
    if user_info["type"] == "normal" and user_info["usage"] >= 10:
        update.message.reply_text("🚫 Daily limit reached.")
        return

    title, thumb, size, links = process_terabox_link(text, user_info["type"])
    if not title:
        update.message.reply_text("❌ Failed to process Terabox link.")
        return

    caption = f"*{title}*\nSize: {size}\n\n" + "\n".join(links)
    sent = update.message.reply_photo(photo=thumb, caption=caption, parse_mode=ParseMode.MARKDOWN)

    delete_later(context, sent.chat_id, sent.message_id)
    users[user_id]["usage"] += 1

# ===== MAIN =====
logging.basicConfig(level=logging.INFO)
updater = Updater(BOT_TOKEN, use_context=True)
dp = updater.dispatcher

dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("help", help_cmd))
dp.add_handler(CommandHandler("status", status_cmd))
dp.add_handler(CommandHandler("subscribe", subscribe_cmd))
dp.add_handler(CommandHandler("approve", approve_cmd))
dp.add_handler(CommandHandler("remove", remove_cmd))
dp.add_handler(CommandHandler("refer", refer_cmd))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

updater.start_polling()
updater.idle()
