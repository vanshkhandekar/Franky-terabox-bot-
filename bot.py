# main.py
"""
Terabox_byfranky_bot - single-file bot
Features included:
- Normal users: single link at a time, daily limit (10)
- Premium users: bulk links (up to 10 bulk links), unlimited daily (daily_quota = -1)
- Invite system: share invite => referrer +1 daily quota
- Payment button: sends local QR image + UPI ID + professional message (English)
- Admin commands: /status, /approve <user_id>, /remove <user_id>
- Auto-delete user message & bot reply after 30 minutes
- Channel membership required to use bot (checks @franky_intro)
- Logging to DB + daily report to admin
- All DB stored in Neon PostgreSQL (asyncpg)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from io import BytesIO
import os

import asyncpg
import qrcode
from PIL import Image

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ---------------- CONFIG (prefilled) ----------------
# TOKEN, ADMIN_ID, DB string taken from your earlier messages
BOT_TOKEN = "8269947278:AAE4Jogxlstl0sEOpuY1pGnrPwy3TRrILT4"
ADMIN_ID = 5924901610
BOT_USERNAME = "Terabox_byfranky_bot"     # without @
CONTACT_USERNAME = "Thecyberfranky"      # without @
CHANNEL_USERNAME = "franky_intro"        # required channel (without @)

# Neon DB connection (prefilled)
DATABASE_URL = (
    "postgresql://neondb_owner:"
    "npg_SgH8G4BDbvui@ep-square-cloud-a1t2wxt9-pooler."
    "ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)

# Payment config (replace UPI_ID if you want)
UPI_ID = "yourupi@upi"
QR_IMAGE_FILE = "payment_qr.jpg"  # Put your QR here (replace anytime)

# Behaviour config
AUTO_DELETE_SECONDS = 1800  # 30 minutes
BULK_LIMIT_COUNT = 10  # premium can send up to 10 links in one message (we'll split by newline)
# ----------------------------------------------------

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("terabox")

# SQL schema
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    is_premium BOOLEAN DEFAULT FALSE,
    premium_until TIMESTAMP NULL,
    daily_quota INTEGER DEFAULT 10,
    daily_used INTEGER DEFAULT 0,
    referrals INTEGER DEFAULT 0,
    registered_on TIMESTAMP DEFAULT now()
);
CREATE TABLE IF NOT EXISTS links (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    link TEXT,
    uploaded_on TIMESTAMP DEFAULT now(),
    expiry_ts TIMESTAMP NULL
);
CREATE TABLE IF NOT EXISTS invites (
    id SERIAL PRIMARY KEY,
    referrer BIGINT,
    referee BIGINT,
    created_on TIMESTAMP DEFAULT now()
);
CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    level TEXT,
    message TEXT,
    created_on TIMESTAMP DEFAULT now()
);
"""

db_pool: asyncpg.pool.Pool = None

# ----------------- DB helpers -----------------
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with db_pool.acquire() as conn:
        await conn.execute(CREATE_SQL)
    logger.info("DB connected and tables ensured.")

async def db_log(level: str, message: str):
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO logs (level, message) VALUES ($1, $2)",
                level, message
            )
    except Exception as e:
        logger.exception("db_log failed: %s", e)

async def ensure_user(user_id: int, username: str = ""):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING",
            user_id, username or ""
        )

# ----------------- Utilities -----------------
def caption_text():
    return f"Thanks for using @{BOT_USERNAME} | Contact @{CONTACT_USERNAME}"

async def check_channel_membership(bot, user_id: int) -> bool:
    if not CHANNEL_USERNAME:
        return True
    try:
        chat = f"@{CHANNEL_USERNAME}"
        member = await bot.get_chat_member(chat_id=chat, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.info("Channel check failed: %s", e)
        return False

# ---------------- Handlers ----------------
async def start_with_payload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # handles /start and /start ref_x
    args = context.args
    user = update.effective_user
    await ensure_user(user.id, user.username or "")
    if args and args[0].startswith("ref_"):
        try:
            ref = int(args[0].split("ref_")[1])
        except Exception:
            await send_welcome(update, context)
            return
        # record invite and give +1 quota to referrer
        async with db_pool.acquire() as conn:
            await conn.execute("INSERT INTO invites (referrer, referee) VALUES ($1, $2)", ref, user.id)
            await conn.execute("UPDATE users SET referrals = referrals + 1, daily_quota = daily_quota + 1 WHERE user_id = $1", ref)
        await update.message.reply_text("Thanks — your invite is recorded. The referrer gets +1 daily quota.")
        try:
            await context.bot.send_message(ref, f"You got +1 quota because @{user.username} joined using your invite!")
        except Exception:
            pass
        await db_log("INFO", f"Invite recorded: ref={ref}, user={user.id}")
    else:
        await send_welcome(update, context)

async def send_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 Hello {user.first_name}!\n\n"
        "Welcome to *Terabox by Franky* — features (quick):\n"
        "1️⃣ Single upload / 10 links daily for normal users\n"
        "2️⃣ Premium: bulk uploads + streaming mirrors\n"
        "3️⃣ Invite friends → +1 daily quota each\n"
        "4️⃣ Auto-delete after 30 mins & payment support\n\n"
        "Type /help to see commands."
    )
    await update.message.reply_text(text, parse_mode="Markdown")
    await db_log("INFO", f"/start by {user.id}")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📋 *Commands*\n"
        "/start - Welcome\n"
        "/help - This menu\n"
        "/invite - Get your invite link\n"
        "/pay - Payment options\n"
        "/check - Check your premium status\n\n"
        "Admin only:\n"
        "/status - show totals\n"
        "/approve <user_id> - grant premium\n"
        "/remove <user_id> - remove premium\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def invite_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await ensure_user(user.id, user.username or "")
    payload = f"ref_{user.id}"
    bot_link = f"https://t.me/{BOT_USERNAME}?start={payload}"
    await update.message.reply_text(f"Share this invite link:\n{bot_link}\nYou get +1 daily quota per valid referral.")
    await db_log("INFO", f"Invite link sent to {user.id}")

# ------------ Payment: button + callback ------------
async def pay_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("💳 Payment", callback_data="payment_main")],
    ]
    await update.message.reply_text("Choose an option:", reply_markup=InlineKeyboardMarkup(kb))

async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    # Two choices: show profile link + show UPI / QR
    kb = [
        [InlineKeyboardButton("Open seller profile", url=f"https://t.me/{CONTACT_USERNAME}")],
        [InlineKeyboardButton("Show UPI & QR", callback_data="payment_show")]
    ]
    await q.message.reply_text("Choose a payment option:", reply_markup=InlineKeyboardMarkup(kb))

async def payment_show_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    # Prepare professional English message with UPI & instruction
    message = (
        "💳 *Payment Instructions*\n\n"
        f"UPI ID: `{UPI_ID}`\n\n"
        "Please make the payment and then send the payment screenshot to "
        f"@{CONTACT_USERNAME} for manual verification. Once verified, your premium will be activated.\n\n"
        "If you have any issues, contact the seller directly."
    )
    # Send QR image from local file if exists, else just send text
    if os.path.exists(QR_IMAGE_FILE):
        try:
            with open(QR_IMAGE_FILE, "rb") as f:
                await q.message.reply_photo(photo=f, caption=message, parse_mode="Markdown")
        except Exception as e:
            await q.message.reply_text(f"Could not send QR image: {e}\n\n{message}", parse_mode="Markdown")
    else:
        # generate QR on the fly from UPI ID as fallback
        try:
            qr_text = f"upi://pay?pa={UPI_ID}&pn={CONTACT_USERNAME}"
            img = qrcode.make(qr_text)
            bio = BytesIO()
            img.save(bio, format="PNG")
            bio.seek(0)
            await q.message.reply_photo(photo=bio, caption=message, parse_mode="Markdown")
        except Exception as e:
            await q.message.reply_text(f"{message}\n\n(Note: QR image not available: {e})", parse_mode="Markdown")
    await db_log("INFO", f"Payment info shown to {q.from_user.id}")

# -------------- Admin commands --------------
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized.")
        return
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users")
        premium = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_premium = TRUE")
        links24 = await conn.fetchval("SELECT COUNT(*) FROM links WHERE uploaded_on >= now() - interval '1 day'")
    await update.message.reply_text(f"Total users: {total}\nPremium: {premium}\nLinks last 24h: {links24}")
    await db_log("INFO", "/status used by admin")

async def approve_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /approve <user_id>")
        return
    try:
        uid = int(context.args[0])
    except:
        await update.message.reply_text("User id must be integer.")
        return
    until = datetime.utcnow() + timedelta(days=365)  # 1 year default
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_premium = TRUE, premium_until = $1, daily_quota = -1 WHERE user_id = $2", until, uid)
    await update.message.reply_text(f"User {uid} granted premium until {until.isoformat()}")
    await db_log("INFO", f"Admin approved {uid}")

async def remove_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Unauthorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /remove <user_id>")
        return
    try:
        uid = int(context.args[0])
    except:
        await update.message.reply_text("User id must be integer.")
        return
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_premium = FALSE, premium_until = NULL, daily_quota = 10 WHERE user_id = $1", uid)
    await update.message.reply_text(f"User {uid} removed from premium.")
    await db_log("INFO", f"Admin removed {uid}")

# -------------- Check status for user --------------
async def check_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT is_premium, premium_until, daily_quota, daily_used FROM users WHERE user_id = $1", user.id)
    if not row:
        await update.message.reply_text("No record found. Send /start to register.")
        return
    is_prem, until, quota, used = row["is_premium"], row["premium_until"], row["daily_quota"], row["daily_used"]
    text = (
        f"Premium: {is_prem}\n"
        f"Premium until: {until}\n"
        f"Daily quota: {'unlimited' if quota == -1 else quota}\n"
        f"Used today: {used}"
    )
    await update.message.reply_text(text)

# -------------- Link handler --------------
async def schedule_delete_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    try:
        await context.bot.delete_message(chat_id=data["chat_id"], message_id=data["message_id"])
    except Exception:
        pass

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    if not (text.startswith("http") or text.startswith("www") or text.startswith("magnet:")):
        return

    await ensure_user(user.id, user.username or "")

    # channel membership check
    ok = await check_channel_membership(context.bot, user.id)
    if not ok:
        await update.message.reply_text(f"Please join @{CHANNEL_USERNAME} to use this bot.")
        return

    # support bulk links for premium users (split by newline)
    # if user sends multiple links in one message, treat as bulk
    links = [line.strip() for line in text.splitlines() if line.strip()]
    is_bulk = len(links) > 1

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT daily_quota, daily_used, is_premium FROM users WHERE user_id = $1", user.id)
        if not row:
            await update.message.reply_text("Error retrieving user data.")
            return
        daily_quota, daily_used, is_premium = row["daily_quota"], row["daily_used"], row["is_premium"]

        # If bulk and not premium -> reject
        if is_bulk and not is_premium:
            await update.message.reply_text("Bulk uploads are for premium users only.")
            return

        # If bulk count > allowed -> reject
        if is_bulk and is_premium and len(links) > BULK_LIMIT_COUNT:
            await update.message.reply_text(f"Bulk limit is {BULK_LIMIT_COUNT} links per message.")
            return

        # Check daily quota (if not unlimited)
        if daily_quota != -1 and daily_used >= daily_quota:
            await update.message.reply_text("Daily limit reached. Invite friends or get premium.")
            return

        # For bulk, we increment by number of links; ensure not to exceed quota
        inc = len(links)
        if daily_quota != -1 and (daily_used + inc) > daily_quota:
            await update.message.reply_text("This will exceed your daily quota. Reduce links or get premium.")
            return

        # Store each link
        stored_ids = []
        for lnk in links:
            rec = await conn.fetchrow("INSERT INTO links (user_id, link) VALUES ($1, $2) RETURNING id", user.id, lnk)
            stored_ids.append(rec["id"])
        # update daily_used
        await conn.execute("UPDATE users SET daily_used = daily_used + $1 WHERE user_id = $2", inc, user.id)

    # Simulate terabox links and reply with filenames and size unknown (placeholder)
    responses = []
    for idx, lnk in enumerate(links):
        filename = lnk.split("/")[-1][:128] if "/" in lnk else lnk[:128]
        terabox_link = f"https://terabox.fake/d/{stored_ids[idx]}"
        responses.append(f"{filename}\n{terabox_link}\n")

    reply_text = "\n".join(responses) + f"\n{caption_text()}"
    sent = await update.message.reply_text(reply_text)

    # schedule delete for both user message and bot reply
    context.job_queue.run_once(schedule_delete_job, when=timedelta(seconds=AUTO_DELETE_SECONDS),
                               data={"chat_id": update.message.chat_id, "message_id": update.message.message_id})
    context.job_queue.run_once(schedule_delete_job, when=timedelta(seconds=AUTO_DELETE_SECONDS),
                               data={"chat_id": sent.chat_id, "message_id": sent.message_id})

    await db_log("INFO", f"User {user.id} added {len(links)} link(s)")

# -------------- Daily reset job --------------
async def daily_reset(context: ContextTypes.DEFAULT_TYPE):
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET daily_used = 0")
        total = await conn.fetchval("SELECT COUNT(*) FROM users")
        premium = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_premium = TRUE")
        links24 = await conn.fetchval("SELECT COUNT(*) FROM links WHERE uploaded_on >= now() - interval '1 day'")
    report = f"Daily report:\nUsers: {total}\nPremium: {premium}\nLinks last 24h: {links24}"
    try:
        await context.bot.send_message(ADMIN_ID, report)
    except Exception:
        pass
    await db_log("INFO", "Daily reset executed")

# -------------- Startup --------------
async def main():
    await init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    # Commands & handlers
    application.add_handler(CommandHandler("start", start_with_payload))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("invite", invite_handler))
    application.add_handler(CommandHandler("pay", pay_handler))
    application.add_handler(CallbackQueryHandler(payment_callback, pattern="^payment_main$"))
    application.add_handler(CallbackQueryHandler(payment_show_callback, pattern="^payment_show$"))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(CommandHandler("approve", approve_handler))
    application.add_handler(CommandHandler("remove", remove_handler))
    application.add_handler(CommandHandler("check", check_handler))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_message))

    # schedule daily reset at next UTC midnight
    now = datetime.utcnow()
    next_midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
    first = (next_midnight - now).total_seconds()
    application.job_queue.run_repeating(daily_reset, interval=24*3600, first=first)

    logger.info("Starting bot (polling)...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await application.updater.wait_until_finished()

if __name__ == "__main__":
    asyncio.run(main())
    app.run_polling()
