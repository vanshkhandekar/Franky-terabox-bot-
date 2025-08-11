import logging
import re
import json
from datetime import datetime
from typing import Optional
import httpx
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)
from telegram.error import BadRequest

# ========================
# CONFIG
# ========================
BOT_TOKEN = "8269947278:AAGX87RM56PTLHABH1gbniSG3ooAoe9tbUI"  # token
ADMIN_ID = 5924901610
ADMIN_USERNAME = "Thecyberfranky"
MANDATORY_CHANNEL = "franky_intro"
CHANNEL_JOIN_LINK = f"https://t.me/{MANDATORY_CHANNEL}"

# ========================
# DATA
# ========================
user_data = {}
referral_map = {}

# ==== ALL TERABOX LINK DOMAINS SUPPORTED ====
TERABOX_LINK_RE = re.compile(
    r"https?://("
    r"1024terabox\.com|terabox\.app|teraboxapp\.com|"
    r"teraboxlink\.com|terafileshare\.com|"
    r"teraboxdrive\.com|terashare\.link|tbox\.app|"
    r"teraboxfile\.com|tbxshare\.com"
    r")/s/[A-Za-z0-9_-]+"
)

# ========================
# LOGGING
# ========================
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================
# UTILS
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
# UNIVERSAL LINK PARSER
# ========================
async def parse_terabox_link(url: str) -> Optional[dict]:
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Referer": url}
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.error(f"HTTP error {resp.status_code}")
                return None
            html = resp.text

        # Regex to get window.preloadList even if it has spaces or newlines
        match = re.search(r'window\.preloadList\s*=\s*(\{.*?\});', html, re.S)
        if not match:
            logger.error("No preloadList found in HTML for this link")
            return None

        data = json.loads(match.group(1))
        if "list" not in data or not data["list"]:
            return None

        file_info = data["list"][0]
        direct_link = file_info.get("dlink")
        if not direct_link:
            return None

        return {
            "title": file_info.get("server_filename", "Terabox File"),
            "thumbnail": file_info.get("thumbs", {}).get("url3", "https://via.placeholder.com/320x180.png?text=Terabox"),
            "direct_download": direct_link,
            "stream_links_normal": [direct_link + "&stream=low", direct_link + "&stream=high"],
            "stream_links_premium": [
                direct_link + "&stream=low",
                direct_link + "&stream=med",
                direct_link + "&stream=high",
                direct_link + "&stream=ultra",
                direct_link + "&stream=original",
            ],
        }
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return None

# ========================
# COMMANDS
# ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text("❗ Please join channel first.", reply_markup=join_contact_buttons())
        return
    await update.message.reply_text(
        f"👋 Hello {update.effective_user.first_name}!\n\n"
        "🎉 Welcome to <b>Terabox Downloader Bot</b>\n"
        "📌 Send a Terabox link (any domain) & get direct + streaming links.\n"
        "💎 Premium = Unlimited\n\n"
        f"Contact @{ADMIN_USERNAME} for help/premium.",
        parse_mode="HTML",
        reply_markup=join_contact_buttons()
    )

async def help_command(update, context):
    await update.message.reply_text(
        "📜 Commands:\n/start - Start Bot\n/help - Show help\n"
        "/subscribe - Premium info\n/status - Check usage\n/refer <id> -Invite friends"
    )

async def subscribe(update, context):
    await update.message.reply_text(
        "💎 Premium Plans:\nFree: 10 links/day\nPremium: Unlimited\n📩 Contact Admin",
        reply_markup=join_contact_buttons()
    )

async def status(update, context):
    rec = get_user_record(update.effective_user.id)
    limit = "Unlimited" if rec["premium"] else 10 + rec["extra_chances"]
    await update.message.reply_text(
        f"👤 User: {update.effective_user.id}\n💎 Premium: {'✅' if rec['premium'] else '❌'}\n"
        f"📊 Daily: {rec['daily_count']}/{limit}\n🤝 Referrals: {rec['referrals']}"
    )

# ========================
# LINK HANDLER
# ========================
async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    links = list(TERABOX_LINK_RE.finditer(update.message.text or ""))
    if not links:
        await update.message.reply_text("❌ No valid Terabox link found.")
        return

    rec = get_user_record(update.effective_user.id)
    for m in links:
        info = await parse_terabox_link(m.group(0))
        if not info:
            await update.message.reply_text("⚠️ Unable to fetch file details.")
            continue
        stream = info['stream_links_premium'] if rec['premium'] else info['stream_links_normal']
        caption = f"🎬 <b>{info['title']}</b>\n📥 {info['direct_download']}\n\n▶ Streaming:\n"
        for i, l in enumerate(stream):
            caption += f"{i+1}. {l}\n"
        await update.message.reply_photo(info['thumbnail'], caption=caption, parse_mode="HTML", reply_markup=join_contact_buttons())
        rec["daily_count"] += 1

# ========================
# MAIN
# ========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(TERABOX_LINK_RE), process_link))
    app.run_polling()

if __name__ == "__main__":
    main()
