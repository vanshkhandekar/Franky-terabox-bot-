import os
import psycopg2
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Environment variables (already filled for you)
TOKEN = "8269947278:AAE4Jogxlstl0sEOpuY1pGnrPwy3TRrILT4"
DATABASE_URL = "postgresql://neondb_owner:npg_SgH8G4BDbvui@ep-square-cloud-a1t2wxt9-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# Connect to database
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is working ✅")

# Test database connection
async def testdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT NOW();")
        result = cur.fetchone()
        cur.close()
        conn.close()
        await update.message.reply_text(f"Database time: {result[0]}")
    except Exception as e:
        await update.message.reply_text(f"Database error: {e}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("testdb", testdb))
    print("Bot started polling...")
    app.run_polling()
