import os
import re
import requests

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

TERABOX_API = (
    "https://terabox-worker.robinkumarshakya103.workers.dev/api"
)

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
# TERABOX PROCESSOR
# ============================================================

def process_terabox(link):

    try:

        response = requests.get(
            TERABOX_API,
            params={"url": link},
            timeout=30,
        )

        print("Processor status:", response.status_code)
        print("Processor response:", response.text[:1000])

        if response.status_code != 200:
            return None, "Processor HTTP Error"

        data = response.json()

        if not data.get("success"):
            return None, data.get(
                "message",
                "TeraBox link process failed."
            )

        files = data.get("files", [])

        if not files:
            return None, "No file found."

        return files, None

    except requests.exceptions.Timeout:

        return None, "Processor timeout."

    except requests.exceptions.RequestException as e:

        print("Request error:", e)
        return None, "Processor connection failed."

    except ValueError:

        print("Invalid JSON response")
        return None, "Processor returned invalid response."

    except Exception as e:

        print("Processor error:", e)
        return None, "Unknown processor error."


# ============================================================
# MESSAGE HANDLER
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    text = update.message.text or ""

    # --------------------------------------------------------
    # FIND TERABOX LINK
    # --------------------------------------------------------

    match = TERABOX_PATTERN.search(text)

    if not match:

        await update.message.reply_text(
            "❌ TeraBox Link পাওয়া যায়নি।\n\n"
            "দয়া করে একটি valid TeraBox Share Link পাঠান।"
        )

        return

    link = match.group(0).rstrip(".,!?)]}")

    # --------------------------------------------------------
    # PROCESSING
    # --------------------------------------------------------

    processing = await update.message.reply_text(
        "🔗 TeraBox Link Received!\n\n"
        "⏳ TeraBox থেকে file information নেওয়া হচ্ছে..."
    )

    print("TeraBox link:", link)

    # --------------------------------------------------------
    # RUN PROCESSOR
    # --------------------------------------------------------

    files, error = await context.application.run_in_executor(
        None,
        process_terabox,
        link,
    )

    if error:

        await processing.edit_text(
            "❌ TeraBox Processing Failed\n\n"
            f"Reason: {error}\n\n"
            "আবার চেষ্টা করুন।"
        )

        return

    # --------------------------------------------------------
    # SHOW FILE INFORMATION
    # --------------------------------------------------------

    message = "✅ TeraBox File Found!\n\n"

    for index, file in enumerate(files[:10], start=1):

        filename = (
            file.get("file_name")
            or file.get("filename")
            or "Unknown File"
        )

        size = file.get(
            "size",
            "Unknown"
        )

        download_url = (
            file.get("download_url")
            or file.get("download_link")
            or file.get("original_download_url")
        )

        message += (
            f"📁 File {index}\n"
            f"🎬 Name: {filename}\n"
            f"📦 Size: {size}\n\n"
        )

        if download_url:
            message += "🔗 Direct link found ✅\n\n"
        else:
            message += "⚠️ Download link পাওয়া যায়নি।\n\n"

    await processing.edit_text(message)


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

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    application.add_error_handler(
        error_handler
    )

    print(
        "TeraBox Downloader Bot is running..."
    )

    application.run_polling()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
