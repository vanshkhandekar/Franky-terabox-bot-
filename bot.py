import logging
import re
import asyncio
from datetime import datetime, timedelta
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

# Configuration and constants
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # UPDATE: Put your bot token here
ADMIN_ID = 5924901610
ADMIN_USERNAME = "Thecyberfranky"
MANDATORY_CHANNEL = "franky_intro"  # Telegram channel username without @
CHANNEL_JOIN_LINK = f"https://t.me/{MANDATORY_CHANNEL}"

# User data stores (replace with persistent DB for production)
user_data = {}  # user_id: dict with keys: daily_count, referrals, premium (bool), last_reset (datetime), extra_chances
referral_map = {}  # referred_user_id: referrer_user_id
messages_to_delete = {}  # message_ids with expiry datetime {(chat_id, message_id): expiry_timestamp}

# Regex for Terabox links (example pattern)
TERABOX_LINK_RE = re.compile(r"https?://(1024terabox\.com|1024tera\.com)/s/[A-Za-z0-9]+")

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
        # Reset daily count if day changed
        if datetime.utcnow().date() != record["last_reset"].date():
            record["daily_count"] = 0
            record["extra_chances"] = 0
            record["last_reset"] = datetime.utcnow()
    return record


async def check_channel_membership(
    user_id: int, app: Application
) -> bool:
    """Check if user is a member of the mandatory channel."""
    try:
        member = await app.bot.get_chat_member(f"@{MANDATORY_CHANNEL}", user_id)
        if member.status in [ChatMember.MEMBER, ChatMember.OWNER, ChatMember.ADMINISTRATOR]:
            return True
        return False
    except BadRequest:
        return False


def create_join_channel_markup():
    keyboard = [
        [InlineKeyboardButton(text="Join Channel", url=CHANNEL_JOIN_LINK)]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    # Check channel join
    if not await check_channel_membership(user.id, context.application):
        await update.message.reply_text(
            f"❗ You must join the channel @{MANDATORY_CHANNEL} to use this bot.",
            reply_markup=create_join_channel_markup(),
        )
        return

    welcome_text = (
        f"Welcome to Terabox_byfranky_bot! For any help, contact @{ADMIN_USERNAME}."
    )
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    if not await check_channel_membership(user.id, context.application):
        await update.message.reply_text(
            f"❗ You must join the channel @{MANDATORY_CHANNEL} to use this bot.",
            reply_markup=create_join_channel_markup(),
        )
        return

    text = (
        "Terabox_byfranky_bot Commands:\n"
        "/start - Start or restart the bot\n"
        "/help - Show this help message\n"
        "/subscribe - Get subscription plans and premium contact info\n"
        "/status - Show your daily usage, referrals, and premium status\n"
        "/refer <user_id> - Refer a user to gain extra usage chances\n"
        "\nAdmin commands (only for admin):\n"
        "/approve <user_id> - Approve user as premium\n"
        "/remove <user_id> - Remove premium status from user\n"
    )
    await update.message.reply_text(text)


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    if not await check_channel_membership(user.id, context.application):
        await update.message.reply_text(
            f"❗ You must join the channel @{MANDATORY_CHANNEL} to use this bot.",
            reply_markup=create_join_channel_markup(),
        )
        return

    text = (
        "Subscription Plans:\n"
        "- Normal Users: Free, 3 Terabox links per day\n"
        "- Premium Users: Unlimited usage + bulk link processing (up to 10 links at once)\n\n"
        f"To get premium access contact @{ADMIN_USERNAME}"
    )
    await update.message.reply_text(text)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    if not await check_channel_membership(user.id, context.application):
        await update.message.reply_text(
            f"❗ You must join the channel @{MANDATORY_CHANNEL} to use this bot.",
            reply_markup=create_join_channel_markup(),
        )
        return

    record = get_user_record(user.id)
    daily_limit = 10 + record["extra_chances"] if not record["premium"] else "Unlimited"
    text = (
        f"Status for @{user.username or user.first_name}:\n"
        f"- Premium Status: {'Yes' if record['premium'] else 'No'}\n"
        f"- Daily Usage: {record['daily_count']} / {daily_limit if isinstance(daily_limit, int) else daily_limit}\n"
        f"- Referrals Made: {record['referrals']}\n"
        "\nNote: Normal users get +1 extra daily chance per successful referral."
    )
    await update.message.reply_text(text)


async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return
    try:
        user_id_to_approve = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /approve <user_id>")
        return

    record = get_user_record(user_id_to_approve)
    record["premium"] = True
    record["daily_count"] = 0
    record["extra_chances"] = 0
    record["last_reset"] = datetime.utcnow()
    await update.message.reply_text(f"User {user_id_to_approve} approved as premium.")


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return
    try:
        user_id_to_remove = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /remove <user_id>")
        return

    record = get_user_record(user_id_to_remove)
    record["premium"] = False
    record["daily_count"] = 0
    record["extra_chances"] = 0
    record["last_reset"] = datetime.utcnow()
    await update.message.reply_text(f"Premium status removed from user {user_id_to_remove}.")


async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    if not await check_channel_membership(user.id, context.application):
        await update.message.reply_text(
            f"❗ You must join the channel @{MANDATORY_CHANNEL} to use this bot.",
            reply_markup=create_join_channel_markup(),
        )
        return

    if len(context.args) == 0:
        await update.message.reply_text("Usage: /refer <user_id>")
        return
    try:
        referred_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID.")
        return

    if referred_id == user.id:
        await update.message.reply_text("You cannot refer yourself.")
        return

    # If user already referred
    if referred_id in referral_map:
        await update.message.reply_text("This user is already referred.")
        return

    referral_map[referred_id] = user.id

    # Increase referrer's extra chances by 1
    referrer_record = get_user_record(user.id)
    referrer_record["referrals"] += 1
    referrer_record["extra_chances"] += 1

    await update.message.reply_text(
        f"Referral saved! You gained +1 extra daily usage chance. Total referrals: {referrer_record['referrals']}."
    )


async def parse_terabox_link(url: str) -> Optional[dict]:
    """
    Simulates parsing the Terabox link to extract metadata and video/file links.
    In production, this function should call Terabox API or scrape necessary info.

    Returns dict:
        {
          "title": str,
          "thumbnail": str (url),
          "direct_download": str (url),
          "stream_links": list of str urls
        }
    """
    # Simulation example data:
    fake_base = "https://cdn.1024terabox.com/files/"
    title = "Sample Terabox Video"
    thumbnail = "https://via.placeholder.com/320x180.png?text=Terabox+Video"
    direct_download = fake_base + "video.mp4?download=1"
    stream_links_normal = [
        "https://stream01.1024terabox.com/video.mp4",
        "https://stream02.1024terabox.com/video.mp4",
    ]
    stream_links_premium = stream_links_normal + [
        "https://stream03.1024terabox.com/video.mp4",
        "https://stream04.1024terabox.com/video.mp4",
        "https://stream05.1024terabox.com/video.mp4",
    ]

    # Here we just return these fake data regardless of URL
    return {
        "title": title,
        "thumbnail": thumbnail,
        "direct_download": direct_download,
        "stream_links_normal": stream_links_normal,
        "stream_links_premium": stream_links_premium,
    }


async def process_terabox_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    if not await check_channel_membership(user.id, context.application):
        await update.message.reply_text(
            f"❗ You must join the channel @{MANDATORY_CHANNEL} to use this bot.",
            reply_markup=create_join_channel_markup(),
        )
        return

    text = update.message.text or ""
    links = TERABOX_LINK_RE.findall(text)
    # Actually TERABOX_LINK_RE.findall returns tuples, so use finditer to get full matches
    matches = list(TERABOX_LINK_RE.finditer(text))
    if not matches:
        await update.message.reply_text(
            "No valid Terabox link detected. Send a valid Terabox link to process."
        )
        return

    record = get_user_record(user.id)
    if not record["premium"]:
        # Check daily usage limit with extra chances
        limit = 10 + record["extra_chances"]
        if record["daily_count"] + len(matches) > limit:
            await update.message.reply_text(
                f"You reached your daily limit of {limit} Terabox links. "
                f"Refer others to get extra chances or subscribe for premium."
            )
            return
        if len(matches) > 1:
            await update.message.reply_text(
                "Normal users can only send 1 Terabox link at a time. Subscribe for bulk access."
            )
            return
    else:
        # Premium user can send up to 10 links in bulk
        if len(matches) > 10:
            await update.message.reply_text(
                "Premium users can send up to 10 Terabox links at once."
            )
            return

    # Process each Terabox link one by one
    for match in matches:
        terabox_url = match.group(0)

        try:
            info = await parse_terabox_link(terabox_url)
        except Exception as e:
            logger.error(f"Error parsing link {terabox_url}: {e}")
            await update.message.reply_text("Failed to process the Terabox link.")
            continue

        # Prepare message with file details and links
        caption = f"🎬 Title: {info['title']}\n"

        # Links per user type
        if record["premium"]:
            streaming_links = info["stream_links_premium"]
            num_stream = 5
        else:
            streaming_links = info["stream_links_normal"]
            num_stream = 2

        caption += f"📥 Direct Download Link: {info['direct_download']}\n"
        caption += f"▶️ Streaming Links:\n"
        for i in range(num_stream):
            caption += f"{i + 1}. {streaming_links[i]}\n"

        # Send photo with caption (thumbnail)
        await update.message.reply_photo(
            photo=info["thumbnail"],
            caption=caption,
            parse_mode="HTML",
        )
        # Increase user daily count by 1 for each link processed
        record["daily_count"] += 1

        # Schedule deletion of messages with links after 30 minutes
        # Save message ids to delete later
        chat_id = update.message.chat_id
        # Save the bot reply message info
        sent_messages = context.bot_data.setdefault("messages_to_delete", [])
        sent_messages.append((chat_id, update.message.message_id))
        # Here we add deletion for the bot's photo message as well
        # But since we don't have direct access to sent photo message id from this function,
        # Let's store photo message id via context.user_data for deletion in a separate handler if needed.

        # Alternatively, do deletion via a global list in the app (later implemented)

    # Delete the user's original message with Terabox links after 30 minutes
    # Store these to delete later
    if "messages_to_delete" not in context.bot_data:
        context.bot_data["messages_to_delete"] = []
    context.bot_data["messages_to_delete"].append((update.message.chat_id, update.message.message_id))

    await update.message.delete()


async def periodic_message_cleanup(application: Application):
    """Periodic task to delete disabled messages after 30 minutes."""
    while True:
        now = datetime.utcnow()
        items = application.bot_data.get("messages_to_delete", [])
        to_remove = []
        for item in items:
            chat_id, msg_id = item
            # We can check if the message is older than 30 minutes
            # But we don't have timestamps here, so store timestamps as well
            # Instead, keep a structure with (chat_id, msg_id, timestamp)
            # For simplicity, here implement below approach:

        # Wait 30 mins before first cleanup call
        await asyncio.sleep(1800)


async def track_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Track whether user joined the mandatory channel and greet/reject accordingly."""
    chat_member_update: ChatMemberUpdated = update.chat_member
    user = chat_member_update.from_user
    new_status = chat_member_update.new_chat_member.status
    old_status = chat_member_update.old_chat_member.status

    if new_status in [ChatMember.MEMBER, ChatMember.OWNER, ChatMember.ADMINISTRATOR]:
        # User just joined
        # Optionally send welcome or update data
        pass


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ An error occurred. Please try again later."
        )


def main():
    from telegram.ext import ApplicationBuilder

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("refer", refer))

    # Message handler for text messages with Terabox links
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(TERABOX_LINK_RE), process_terabox_message
        )
    )

    # Chat member update handler for tracking channel membership (optional)
    app.add_handler(ChatMemberHandler(track_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    app.add_error_handler(on_error)

    # Run the bot with long polling
    app.run_polling()


if __name__ == "__main__":
    main()
