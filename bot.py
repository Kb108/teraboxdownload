import os
import re
import asyncio

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============================================================
# BOT TOKEN
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")


# ============================================================
# TERABOX LINK PATTERN
# ============================================================

TERABOX_PATTERN = re.compile(
    r"https?://(?:www\.)?"
    r"(?:terabox\.com|teraboxapp\.com|1024terabox\.com)"
    r"/\S+",
    re.IGNORECASE,
)


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "👋 Welcome to TeraBox Downloader Bot!\n\n"
        "🔗 আপনার TeraBox Share Link পাঠান।"
    )


# ============================================================
# TERABOX MESSAGE
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    text = update.message.text or ""

    # Find TeraBox link
    match = TERABOX_PATTERN.search(text)

    if not match:

        await update.message.reply_text(
            "❌ TeraBox Link পাওয়া যায়নি।\n\n"
            "দয়া করে একটি valid TeraBox Share Link পাঠান।"
        )

        return

    # Clean link
    link = match.group(0).rstrip(".,!?)]}")

    print("TeraBox link received:", link)

    # Processing message
    processing_message = await update.message.reply_text(
        "🔗 TeraBox Link Received!\n\n"
        "⏳ Processing হচ্ছে..."
    )

    # Temporary delay
    await asyncio.sleep(2)

    await processing_message.edit_text(
        "✅ TeraBox Link Detected!\n\n"
        "🔗 Link successfully received.\n\n"
        "⚙️ Downloader Processor এখনো যুক্ত করা হয়নি।\n\n"
        "📥 পরের ধাপে TeraBox Downloader যুক্ত করা হবে।"
    )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update,
    context,
):

    print("BOT ERROR:", context.error)


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN is missing.\n"
            "Please add BOT_TOKEN in GitHub Secrets."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # /start
    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    # Normal text messages
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    # Error handler
    application.add_error_handler(
        error_handler
    )

    print(
        "TeraBox Telegram Bot is running..."
    )

    application.run_polling()


# ============================================================
# RUN BOT
# ============================================================

if __name__ == "__main__":
    main()
