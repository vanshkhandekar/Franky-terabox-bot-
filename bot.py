import os
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from datetime import datetime, timedelta

# ====== CONFIG ======
BOT_TOKEN = "YOUR_BOT_TOKEN"
ADMIN_ID = 123456789  # Change to your Telegram ID
CHANNEL_USERNAME = "@YourChannel"  # Must join channel
PAYMENT_DATA = {"upi_id": None, "qr_file_id": None}  # Store payment info in memory

# ====== START COMMAND ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"👋 Hello {user.first_name}!\n\n"
        "📌 *Features:*\n"
        "1️⃣ Normal Users: 1 link at a time, daily limit 10\n"
        "2️⃣ Premium Users: Bulk links (10 at once)\n"
        "3️⃣ Auto-delete msgs after 30 min\n"
        "4️⃣ Must join channel to use bot\n"
    )

    keyboard = [
        [InlineKeyboardButton("💳 Payment", callback_data="payment")],
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.strip('@')}")]
    ]

    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ====== ADMIN: SET PAYMENT ======
async def setpayment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ You are not authorized.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /setpayment <UPI_ID>")
        return

    PAYMENT_DATA["upi_id"] = context.args[0]
    await update.message.reply_text(f"✅ UPI ID set to: `{PAYMENT_DATA['upi_id']}`", parse_mode="Markdown")
    await update.message.reply_text("Now send the QR code image...")

    context.user_data["awaiting_qr"] = True

# ====== ADMIN: RECEIVE QR IMAGE ======
async def receive_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if context.user_data.get("awaiting_qr"):
        file_id = update.message.photo[-1].file_id
        PAYMENT_DATA["qr_file_id"] = file_id
        context.user_data["awaiting_qr"] = False
        await update.message.reply_text("✅ Payment QR saved successfully.")

# ====== PAYMENT BUTTON ACTION ======
async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not PAYMENT_DATA["upi_id"] or not PAYMENT_DATA["qr_file_id"]:
        await query.message.reply_text("⚠️ Payment info not set yet. Please contact admin.")
        return

    caption = (
        f"💳 *Payment Details:*\n\n"
        f"📍 UPI ID: `{PAYMENT_DATA['upi_id']}`\n\n"
        "After payment, send screenshot to @thecyberfranky ✅"
    )

    await query.message.reply_photo(
        photo=PAYMENT_DATA["qr_file_id"],
        caption=caption,
        parse_mode="Markdown"
    )

# ====== MAIN ======
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setpayment", setpayment))
app.add_handler(MessageHandler(filters.PHOTO, receive_qr))
app.add_handler(CallbackQueryHandler(payment_info, pattern="^payment$"))

print("🤖 Bot started...")
app.run_polling()
