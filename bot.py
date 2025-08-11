import logging
import re
import asyncio
from datetime import datetime
from typing import Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatMemberUpdated,
    ChatMember,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)
from telegram.error import BadRequest

# ========================
#  CONFIGURATION
# ========================
BOT_TOKEN = "8269947278:AAE4Jogxlstl0sEOpuY1pGnrPwy3TRrILT4"
ADMIN_ID = 5924901610
ADMIN_USERNAME = "Thecyberfranky"
MANDATORY_CHANNEL = "franky_intro"  # without '@'
CHANNEL_JOIN_LINK = f"https://t.me/{MANDATORY_CHANNEL}"

# ========================
#  USER DATA STORAGE
# ========================
user_data = {}       # {user_id: {...}}
referral_map = {}    # {referred_user_id: referrer_user_id}

# ========================
#  LINK REGEX
# ========================
TERABOX_LINK_RE = re.compile(r"https?://(1024terabox\.com|1024tera\.com)/s/[A-Za-z0-9]+")

# ========================
#  LOGGING
# ========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_user_record(user_id: int) -> dict:
    """Get or initialize user record."""
    record = user_data.get(user_id)
    if not record:
        record = {
            "daily_count": 0,
            "referrals": 0,
            "premium": False,
            "last_reset": datetime.utcnow(),
            "extra_chances": 0,
        }
        user_data[user_id] = record
    else:
        if datetime.utcnow().date() != record["last_reset"].date():
            record["daily_count"] = 0
            record["extra_chances"] = 0
            record["last_reset"] = datetime.utcnow()
    return record


async def check_channel_membership(user_id: int, app: Application) -> bool:
    try:
        member = await app.bot.get_chat_member(f"@{MANDATORY_CHANNEL}", user_id)
        return member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except BadRequest:
        return False


def create_join_channel_markup():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Join Channel", url=CHANNEL_JOIN_LINK)]]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_channel_membership(user.id, context.application):
        await update.message.reply_text(
            f"❗ You must join @{MANDATORY_CHANNEL} to use this bot",
            reply_markup=create_join_channel_markup()
        )
        return

    await update.message.reply_text(
        f"Welcome to Terabox_byfranky_bot! For any help, contact @{ADMIN_USERNAME}."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text(
            f"❗ You must join @{MANDATORY_CHANNEL} to use this bot",
            reply_markup=create_join_channel_markup()
        )
        return

    await update.message.reply_text(
        "📜 Commands:\n"
        "/start - Start bot\n"
        "/help - Help\n"
        "/subscribe - Premium plans\n"
        "/status - Your usage status\n"
        "/refer <user_id> - Refer a user\n"
        "\n👑 Admin:\n"
        "/approve <user_id> - Make user premium\n"
        "/remove <user_id> - Remove premium"
    )


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text(
            f"❗ You must join @{MANDATORY_CHANNEL} to use this bot",
            reply_markup=create_join_channel_markup()
        )
        return

    await update.message.reply_text(
        "💎 Subscription Plans:\n"
        "Free: 10 Terabox links/day + referral bonus\n"
        "Premium: Unlimited + bulk processing\n\n"
        f"Contact @{ADMIN_USERNAME} to upgrade."
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text(
            f"❗ You must join @{MANDATORY_CHANNEL} to use this bot",
            reply_markup=create_join_channel_markup()
        )
        return

    record = get_user_record(update.effective_user.id)
    daily_limit = "Unlimited" if record["premium"] else 10 + record["extra_chances"]

    await update.message.reply_text(
        f"👤 User: @{update.effective_user.username or update.effective_user.first_name}\n"
        f"Premium: {'✅' if record['premium'] else '❌'}\n"
        f"Daily Usage: {record['daily_count']} / {daily_limit}\n"
        f"Referrals: {record['referrals']}"
    )


async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
    except:
        await update.message.reply_text("Usage: /approve <user_id>")
        return
    get_user_record(uid)["premium"] = True
    await update.message.reply_text(f"✅ User {uid} now Premium")


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
    except:
        await update.message.reply_text("Usage: /remove <user_id>")
        return
    get_user_record(uid)["premium"] = False
    await update.message.reply_text(f"❌ User {uid} Premium removed")


async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text(
            f"❗ You must join @{MANDATORY_CHANNEL} to use this bot",
            reply_markup=create_join_channel_markup()
        )
        return

    try:
        referred_id = int(context.args[0])
    except:
        await update.message.reply_text("Usage: /refer <user_id>")
        return

    if referred_id == update.effective_user.id:
        await update.message.reply_text("❌ You cannot refer yourself")
        return

    if referred_id in referral_map:
        await update.message.reply_text("❌ User already referred")
        return

    referral_map[referred_id] = update.effective_user.id
    rec = get_user_record(update.effective_user.id)
    rec["referrals"] += 1
    rec["extra_chances"] += 1
    await update.message.reply_text(
        f"✅ Referral added! +1 daily chance. Total referrals: {rec['referrals']}"
    )


async def parse_terabox_link(url: str) -> Optional[dict]:
    # Simulated result (replace with real Terabox API scraper)
    return {
        "title": "Sample Terabox Video",
        "thumbnail": "https://via.placeholder.com/320x180.png?text=Terabox",
        "direct_download": "https://cdn.1024terabox.com/video.mp4",
        "stream_links_normal": [
            "https://stream1.1024terabox.com/video.mp4",
            "https://stream2.1024terabox.com/video.mp4",
        ],
        "stream_links_premium": [
            "https://stream1.1024terabox.com/video.mp4",
            "https://stream2.1024terabox.com/video.mp4",
            "https://stream3.1024terabox.com/video.mp4",
            "https://stream4.1024terabox.com/video.mp4",
            "https://stream5.1024terabox.com/video.mp4",
        ],
    }


async def process_terabox_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text(
            f"❗ You must join @{MANDATORY_CHANNEL} to use this bot",
            reply_markup=create_join_channel_markup()
        )
        return

    matches = list(TERABOX_LINK_RE.finditer(update.message.text or ""))
    if not matches:
        return await update.message.reply_text("❌ No valid Terabox link found")

    rec = get_user_record(update.effective_user.id)
    if not rec["premium"]:
        limit = 10 + rec["extra_chances"]
        if rec["daily_count"] + len(matches) > limit:
            return await update.message.reply_text("❌ Daily limit reached")
        if len(matches) > 1:
            return await update.message.reply_text("❌ Free users can send 1 link at a time")

    for m in matches:
        data = await parse_terabox_link(m.group(0))
        if not data:
            continue

        links = data["stream_links_premium"] if rec["premium"] else data["stream_links_normal"]
        caption = f"🎬 {data['title']}\n📥 {data['direct_download']}\n\n▶️ Streaming Links:\n"
        for i, link in enumerate(links):
            caption += f"{i+1}. {link}\n"

        await update.message.reply_photo(data["thumbnail"], caption=caption)
        rec["daily_count"] += 1


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Error: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("⚠️ Error occurred")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("refer", refer))

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(TERABOX_LINK_RE), process_terabox_message))

    app.add_error_handler(on_error)

    app.run_polling()


if __name__ == "__main__":
    main()
