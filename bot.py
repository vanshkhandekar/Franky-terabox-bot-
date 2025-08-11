import logging
import re
import json
from datetime import datetime
from typing import Optional
import asyncio
from playwright.async_api import async_playwright

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
BOT_TOKEN = "8269947278:AAGX87RM56PTLHABH1gbniSG3ooAoe9tbUI"
ADMIN_ID = 5924901610
ADMIN_USERNAME = "Thecyberfranky"
MANDATORY_CHANNEL = "franky_intro"
CHANNEL_JOIN_LINK = f"https://t.me/{MANDATORY_CHANNEL}"

# ========================
# DATA
# ========================
user_data = {}
referral_map = {}

# All known Terabox domains
TERABOX_LINK_RE = re.compile(
    r"https?://("
    r"1024terabox\.com|terabox\.app|teraboxapp\.com|"
    r"teraboxlink\.com|terafileshare\.com|"
    r"teraboxdrive\.com|terashare\.link|tbox\.app|"
    r"teraboxfile\.com|tbxshare\.com"
    r")/s/[A-Za-z0-9_-]+"
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================
# HELPERS
# ========================
def get_user_record(uid: int):
    rec = user_data.get(uid)
    if not rec:
        rec = {"daily_count": 0, "referrals": 0, "premium": False, "last_reset": datetime.utcnow(), "extra_chances": 0}
        user_data[uid] = rec
    elif datetime.utcnow().date() != rec["last_reset"].date():
        rec["daily_count"] = 0
        rec["extra_chances"] = 0
        rec["last_reset"] = datetime.utcnow()
    return rec

async def check_channel_membership(uid: int, app):
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
# PLAYWRIGHT TERABOX FETCHER
# ========================
async def parse_terabox_link(url: str) -> Optional[dict]:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Try multiple variable names
            preload = await page.evaluate("""() => window.preloadList || window.__PRELOADED_STATE__ || null""")
            await browser.close()

        if not preload or "list" not in preload or not preload["list"]:
            return None

        file_info = preload["list"][0]
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
        logger.error(f"Playwright error: {e}")
        return None

# ========================
# COMMANDS
# ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_channel_membership(update.effective_user.id, context.application):
        await update.message.reply_text("❗ Please join our channel first.", reply_markup=join_contact_buttons())
        return
    await update.message.reply_text(
        f"👋 Hello {update.effective_user.first_name}!\n"
        "🎉 Welcome to Terabox Downloader Bot (Full Browser Mode) 🚀\n"
        "📌 Send any Terabox link & get real file details + direct links.\n"
        "💎 Premium = Unlimited use\n"
        f"📩 Contact @{ADMIN_USERNAME} for premium",
        parse_mode="HTML",
        reply_markup=join_contact_buttons()
    )

async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matches = TERABOX_LINK_RE.findall(update.message.text or "")
    if not matches:
        await update.message.reply_text("❌ No valid Terabox link found.")
        return

    rec = get_user_record(update.effective_user.id)
    for match in re.finditer(TERABOX_LINK_RE, update.message.text):
        link = match.group(0)
        await update.message.reply_text("⏳ Fetching link, please wait...")
        info = await parse_terabox_link(link)
        if not info:
            await update.message.reply_text("⚠️ Unable to fetch file details — may be private/password protected")
            continue

        streams = info['stream_links_premium'] if rec['premium'] else info['stream_links_normal']
        caption = f"🎬 <b>{info['title']}</b>\n📥 {info['direct_download']}\n\n▶ Streaming:\n"
        for i, s in enumerate(streams):
            caption += f"{i+1}. {s}\n"

        await update.message.reply_photo(info['thumbnail'], caption=caption, parse_mode="HTML", reply_markup=join_contact_buttons())
        rec['daily_count'] += 1

# ========================
# MAIN
# ========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(TERABOX_LINK_RE), process_link))
    app.run_polling()

if __name__ == "__main__":
    main()
