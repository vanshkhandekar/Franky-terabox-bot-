from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import requests
import re

# Tumhara token direct yaha dala hai
BOT_TOKEN = "8269947278:AAGX87RM56PTLHABH1gbniSG3ooAoe9tbUI"

# Regex to match Terabox links
TERABOX_REGEX = re.compile(
    r"https?://(?:www\.)?(?:1024terabox|terabox|teraboxlink|terafileshare|tbox|teraboxdrive)\.com/\S+"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Bhejo Terabox link, main try karke info launga!\n\n" +
        "⚠ Private/password links par shayad kaam na kare."
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    match = TERABOX_REGEX.search(update.message.text)
    if not match:
        await update.message.reply_text("❌ Valid Terabox link bhejo bhai.")
        return

    url = match.group(0)
    await update.message.reply_text("⏳ Thoda ruk ja... data le raha hu!")

    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": url
        }
        res = session.get(url, headers=headers, timeout=20).text

        # Title extract
        title_match = re.search(r'"server_filename"\s*:\s*"([^"]+)"', res)
        # Direct link extract (hidden param)
        dlink_match = re.search(r'"dlink"\s*:\s*"([^"]+)"', res)

        if title_match:
            title = title_match.group(1)
            caption = f"🎬 Title: {title}\n🔗 Original: {url}"
            if dlink_match:
                direct = dlink_match.group(1).replace("\\u0026", "&")
                caption += f"\n📥 Direct: {direct}"
            await update.message.reply_text(caption)
        else:
            await update.message.reply_text("⚠ File info fetch nahi ho payi (link private ho sakta hai).")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_link))
    app.run_polling()

if __name__ == "__main__":
    main()
