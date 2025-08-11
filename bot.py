import logging
import re
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
BOT_TOKEN = "8269947278:AAGX87RM56PTLHABH1gbniSG3ooAoe9tbUI"  # NEW TOKEN
ADMIN_ID = 5924901610
ADMIN_USERNAME = "Thecyberfranky"
MANDATORY_CHANNEL = "franky_intro"
CHANNEL_JOIN_LINK = f"https://t.me/{MANDATORY_CHANNEL}"

# ========================
#  DATA STORAGE
# ========================
user_data = {}
referral_map = {}

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
def get_user_record(uid: int) -> dict:
    rec = user_data.get(uid)
    if not rec:
        rec = {"daily_count": 0, "referrals": 0, "premium": False, "last_reset": datetime.utcnow(), "extra_chances": 0}
        user_data[uid] = rec
    else:
        if datetime.utcnow().date() != rec["last_reset"].date():
            rec["daily_count"] = 0
            rec["extra_chances"] = 0
            rec["last_reset"] = datetime.utcnow()
    return rec

async def check_channel_membership(uid: int, app) -> bool:
    try:
        member = await app.bot.get_chat_member(f"@{MANDATORY_CHANNEL}", uid)
        return member.status in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except BadRequest:
        return False

def join_contact_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_JOIN_LINK)],
        [InlineKeyboardButton("📩 Contact Admin", url=f"https://t.me/{ADMIN_USERNAME}")]
    ])

# ========================
#  TERABOX LINK FETCHER
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
        return {
            "title": file_info.get("server_filename", "Terabox File"),
            "thumbnail": file_info.get("thumbs", {}).get("url3", "https://via.placeholder.com/320x180.png?text=Terabox"),
            "direct_download": file_info.get("dlink"),
            "stream_links_normal": [file_info["dlink"] + "&stream=low", file_info["dlink"] + "&stream=high"],
            "stream_links_premium": [
                file_info["dlink"] + "&stream=low",
                file_info["dlink"] + "&stream=med",
                file_info["dlink"] + "&stream=high",
                file_info["dlink"] + "&stream=ultra",
                file_info["dlink"] + "&stream=original",
            ]
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
        await update.message.reply_text("❗ Please join our channel first to use the bot.", reply_markup=join_contact_buttons())
        return
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        "🎉 Welcome to <b>Terabox_byfranky_bot</b> 🚀\n\n"
        "📌 I can fetch videos, files, and streaming links from Terabox for you.\n"
        "💎 Premium users enjoy unlimited access & bulk link processing.\n\n"
        f"For help or premium, contact @{ADMIN_USERNAME}.\n"
        f"Don't forget to join our updates channel 📢",
        parse_mode="HTML",
        reply_markup=join_contact_buttons()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text("❗ Join our channel to use the bot.", reply_markup=join_contact_buttons())
        return
    await update.message.reply_text(
        "📜 <b>Commands:</b>\n\n"
        "/start - Start bot 💡\n"
        "/help - Show help 📖\n"
        "/subscribe - Premium plans 💎\n"
        "/status - Check your usage 📊\n"
        "/refer <user_id> - Refer and earn extra chances 🤝\n\n"
        "👑 <b>Admin Only:</b>\n"
        "/approve <uid> - Make premium\n"
        "/remove <uid> - Remove premium",
        parse_mode="HTML"
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text("❗ Join our channel to use the bot.", reply_markup=join_contact_buttons())
        return
    await update.message.reply_text(
        "💎 <b>Subscription Plans:</b>\n\n"
        "Free: 10 Terabox links/day + referrals\n"
        "Premium: Unlimited use + bulk processing\n\n"
        f"📩 Contact @{ADMIN_USERNAME} for premium.",
        parse_mode="HTML",
        reply_markup=join_contact_buttons()
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text("❗ Join our channel to use the bot.", reply_markup=join_contact_buttons())
        return
    rec = get_user_record(update.effective_user.id)
    limit = "Unlimited" if rec["premium"] else 10 + rec["extra_chances"]
    await update.message.reply_text(
        f"👤 <b>User:</b> {update.effective_user.id}\n"
        f"💎 <b>Premium:</b> {'✅' if rec['premium'] else '❌'}\n"
        f"📊 <b>Daily:</b> {rec['daily_count']}/{limit}\n"
        f"🤝 <b>Referrals:</b> {rec['referrals']}",
        parse_mode="HTML"
    )

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        uid = int(context.args[0])
    except:
        await update.message.reply_text("Usage: /approve <user_id>"); return
    get_user_record(uid)["premium"] = True
    await update.message.reply_text(f"✅ User {uid} Premium Added.")

async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        uid = int(context.args[0])
    except:
        await update.message.reply_text("Usage: /remove <user_id>"); return
    get_user_record(uid)["premium"] = False
    await update.message.reply_text(f"❌ User {uid} Premium Removed.")

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text("❗ Join channel first.", reply_markup=join_contact_buttons())
        return
    try:
        rid = int(context.args[0])
    except:
        await update.message.reply_text("Usage: /refer <user_id>"); return
    if rid == update.effective_user.id:
        await update.message.reply_text("❌ Cannot refer yourself."); return
    if rid in referral_map:
        await update.message.reply_text("❌ Already referred."); return
    referral_map[rid] = update.effective_user.id
    rec = get_user_record(update.effective_user.id)
    rec["referrals"] += 1
    rec["extra_chances"] += 1
    await update.message.reply_text("✅ Referral Added. +1 Daily Chance.")

# ========================
#  TERABOX HANDLER
# ========================
async def process_terabox_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text("❗ Join channel first.", reply_markup=join_contact_buttons())
        return
    matches = list(TERABOX_LINK_RE.finditer(update.message.text or ""))
    if not matches:
        await update.message.reply_text("❌ No valid Terabox link found."); return

    rec = get_user_record(update.effective_user.id)
    for m in matches:
        info = await parse_terabox_link(m.group(0))
        if not info:
            await update.message.reply_text("⚠️ Unable to fetch file details."); continue

        links = info["stream_links_premium"] if rec["premium"] else info["stream_links_normal"]
        caption = f"🎬 <b>{info['title']}</b>\n📥 <b>Direct Download:</b> {info['direct_download']}\n\n▶️ <b>Streaming Links:</b>\n"
        for i, l in enumerate(links):
            caption += f"{i+1}. {l}\n"

        await update.message.reply_photo(info["thumbnail"], caption=caption, parse_mode="HTML", reply_markup=join_contact_buttons())
        rec["daily_count"] += 1

# ========================
#  ERROR HANDLER
# ========================
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Error: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("⚠️ Error occurred")

# ========================
#  MAIN FUNCTION
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
