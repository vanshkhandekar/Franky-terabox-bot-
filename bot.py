import logging
import re
import asyncio
from datetime import datetime
from typing import Optional
import httpx

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatMember,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
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
MANDATORY_CHANNEL = "franky_intro"
CHANNEL_JOIN_LINK = f"https://t.me/{MANDATORY_CHANNEL}"

# ========================
#  USER DATA STORAGE
# ========================
user_data = {}       # {user_id: {...}}
referral_map = {}    # {referred_user_id: referrer_user_id}

# ========================
#  LINK REGEX
# ========================
TERABOX_LINK_RE = re.compile(r"https?://(1024terabox\.com|terabox\.app|teraboxapp\.com)/s/[A-Za-z0-9]+")

# ========================
#  LOGGING
# ========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========================
#  USER HANDLING
# ========================
def get_user_record(user_id: int) -> dict:
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

async def check_channel_membership(user_id: int, app) -> bool:
    try:
        member = await app.bot.get_chat_member(f"@{MANDATORY_CHANNEL}", user_id)
        return member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except BadRequest:
        return False

def create_join_channel_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel", url=CHANNEL_JOIN_LINK)]])

# ========================
#  TERABOX LINK FETCHER (REAL)
# ========================
async def parse_terabox_link(url: str) -> Optional[dict]:
    try:
        m = re.search(r"/s/([A-Za-z0-9]+)", url)
        if not m:
            return None
        share_code = m.group(1)

        api_url = f"https://www.1024terabox.com/share/list?app_id=250528&shorturl={share_code}&root=1"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": url}

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(api_url, headers=headers)
            if r.status_code != 200:
                return None
            data = r.json()

        if "list" not in data or not data["list"]:
            return None

        file_info = data["list"][0]
        file_name = file_info.get("server_filename", "Terabox File")
        thumbnail = file_info.get("thumbs", {}).get("url3", "https://via.placeholder.com/320x180.png?text=Terabox")
        direct_link = file_info.get("dlink")

        if not direct_link:
            return None

        stream_links_normal = [direct_link + "&stream=low", direct_link + "&stream=high"]
        stream_links_premium = [
            direct_link + "&stream=low",
            direct_link + "&stream=med",
            direct_link + "&stream=high",
            direct_link + "&stream=ultra",
            direct_link + "&stream=original",
        ]

        return {
            "title": file_name,
            "thumbnail": thumbnail,
            "direct_download": direct_link,
            "stream_links_normal": stream_links_normal,
            "stream_links_premium": stream_links_premium
        }
    except Exception as e:
        logger.error(f"Terabox parse error: {e}")
        return None

# ========================
#  COMMANDS
# ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await check_channel_membership(user.id, context.application):
        await update.message.reply_text(f"❗ Join @{MANDATORY_CHANNEL} first.", reply_markup=create_join_channel_markup())
        return
    await update.message.reply_text(f"Welcome to Terabox_byfranky_bot! For help, contact @{ADMIN_USERNAME}.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text(f"❗ Join @{MANDATORY_CHANNEL} first.", reply_markup=create_join_channel_markup())
        return
    await update.message.reply_text(
        "/start - Start bot\n"
        "/help - Show help\n"
        "/subscribe - Premium plans\n"
        "/status - Check usage\n"
        "/refer <user_id> - Refer friends\n"
        "/approve <uid> - Make premium (Admin)\n"
        "/remove <uid> - Remove premium (Admin)"
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text(f"❗ Join @{MANDATORY_CHANNEL} first.", reply_markup=create_join_channel_markup())
        return
    await update.message.reply_text(f"Free: 10 links/day\nPremium: Unlimited + bulk\nContact @{ADMIN_USERNAME}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text(f"❗ Join @{MANDATORY_CHANNEL} first.", reply_markup=create_join_channel_markup())
        return
    rec = get_user_record(update.effective_user.id)
    limit = "Unlimited" if rec["premium"] else 10 + rec["extra_chances"]
    await update.message.reply_text(
        f"User: {update.effective_user.id}\nPremium: {rec['premium']}\nDaily: {rec['daily_count']}/{limit}\nReferrals: {rec['referrals']}"
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
    await update.message.reply_text(f"User {uid} is now Premium ✅")

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
    except:
        await update.message.reply_text("Usage: /remove <user_id>")
        return
    get_user_record(uid)["premium"] = False
    await update.message.reply_text(f"User {uid} Premium Removed ❌")

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text(f"❗ Join @{MANDATORY_CHANNEL} first.", reply_markup=create_join_channel_markup())
        return
    try:
        referred_id = int(context.args[0])
    except:
        await update.message.reply_text("Usage: /refer <user_id>")
        return
    if referred_id == update.effective_user.id:
        await update.message.reply_text("❌ Cannot refer yourself")
        return
    if referred_id in referral_map:
        await update.message.reply_text("❌ Already referred")
        return
    referral_map[referred_id] = update.effective_user.id
    rec = get_user_record(update.effective_user.id)
    rec["referrals"] += 1
    rec["extra_chances"] += 1
    await update.message.reply_text(f"✅ Referral added. +1 daily chance.")

# ========================
#  TERABOX LINK HANDLER
# ========================
async def process_terabox_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text(f"❗ Join @{MANDATORY_CHANNEL} first.", reply_markup=create_join_channel_markup())
        return
    matches = list(TERABOX_LINK_RE.finditer(update.message.text or ""))
    if not matches:
        await update.message.reply_text("❌ No valid Terabox link found.")
        return

    rec = get_user_record(update.effective_user.id)
    for m in matches:
        info = await parse_terabox_link(m.group(0))
        if not info:
            await update.message.reply_text("⚠️ Failed to fetch link data.")
            continue

        links = info["stream_links_premium"] if rec["premium"] else info["stream_links_normal"]
        caption = f"🎬 {info['title']}\n📥 Direct Download: {info['direct_download']}\n\n▶️ Streaming Links:\n"
        for i, l in enumerate(links):
            caption += f"{i+1}. {l}\n"

        await update.message.reply_photo(info["thumbnail"], caption=caption)
        rec["daily_count"] += 1

# ========================
#  ERROR HANDLER
# ========================
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Error: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("⚠️ Error occurred")

# ========================
#  MAIN
# ========================
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
