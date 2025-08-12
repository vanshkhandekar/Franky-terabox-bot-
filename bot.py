import logging
import time
from threading import Timer
from telegram import (
    Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
)
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters, CallbackContext
)
from TeraboxDL import TeraboxDL

BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"
ADMIN_ID = 5924901610
ADMIN_USERNAME = "@Thecyberfranky"
MANDATORY_CHANNEL = "@franky_intro"
CHANNEL_LINK = "https://t.me/franky_intro"

users = {}  # user_id: {"type": "normal/premium", "usage": int, "referrals": int}

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
        title = info['name']
        thumb = info['thumbnail']
        size = info.get('size', 'N/A')
        # Links logic
        if user_type == "premium":
            links = [direct] + [f"{link}?stream={i}" for i in range(1, 6)]
        else:
            links = [direct] + [f"{link}?stream={i}" for i in range(1, 3)]
        return title, thumb, size, links
    except Exception as e:
        return None, None, None, None

def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in users:
        users[user_id] = {"type": "normal", "usage": 0, "referrals": 0}
    if not check_subscription(context.bot, user_id):
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url=CHANNEL_LINK)]])
        update.message.reply_text("Please join our channel to use this bot.", reply_markup=btn)
        return
    update.message.reply_text(
        "Welcome to Terabox_byfranky_bot! For any help, contact @Thecyberfranky."
    )

def help_cmd(update: Update, context: CallbackContext):
    help_text = (
        "/start — Start the bot\n"
        "/help — Command list\n"
        "/subscribe — Premium info\n"
        "/status — Usage & referral\n"
        "/approve <id> — Admin only\n"
        "/remove <id> — Admin only\n"
        "/refer <id> — Referral system"
    )
    update.message.reply_text(help_text)

def status_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    data = users.get(user_id, {})
    update.message.reply_text(
        f"Type: {data.get('type')}\nUsage: {data.get('usage')}\nReferrals: {data.get('referrals')}"
    )

def subscribe_cmd(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Premium plan details:\nUnlimited links, bulk 10 links at once.\nContact admin: @Thecyberfranky"
    )

def approve_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        if uid in users:
            users[uid]["type"] = "premium"
            update.message.reply_text(f"User {uid} upgraded to premium.")
    except:
        update.message.reply_text("Invalid user ID.")

def remove_cmd(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        if uid in users:
            users[uid]["type"] = "normal"
            update.message.reply_text(f"Premium removed for {uid}.")
    except:
        update.message.reply_text("Invalid user ID.")

def refer_cmd(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        ref_id = int(context.args[0])
        if ref_id in users:
            users[user_id]["referrals"] += 1
            # give +1 usage/day for referral
            users[user_id]["usage"] -= 1
            update.message.reply_text("Referral successful! +1 usage/day.")
        else:
            update.message.reply_text("Invalid referral user ID.")
    except:
        update.message.reply_text("Please use: /refer <user_id>")

def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text
    if not text.startswith("http"):
        return
    if not check_subscription(context.bot, user_id):
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("Join Channel", url=CHANNEL_LINK)]])
        update.message.reply_text("Join channel to use this bot.", reply_markup=btn)
        return

    user_info = users.get(user_id, {"type": "normal", "usage": 0, "referrals": 0})
    if user_info["type"] == "normal" and user_info["usage"] >= 10:
        update.message.reply_text("Daily limit reached.")
        return

    title, thumb, size, links = process_terabox_link(text, user_info["type"])
    if not title:
        update.message.reply_text("Invalid Terabox link or TeraboxDL error.")
        return

    msg = f"*{title}*\nSize: {size}\n\n" + "\n".join(links)
    sent = update.message.reply_photo(photo=thumb, caption=msg, parse_mode=ParseMode.MARKDOWN)
    delete_later(context, sent.chat_id, sent.message_id)
    users[user_id]["usage"] += 1

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
