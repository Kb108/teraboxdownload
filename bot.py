import os
import re
import asyncio
import tempfile
from pathlib import Path

import requests
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Current TeraBox API found from an active GitHub project
PROCESSOR_URL = "https://terabox-worker.robinkumarshakya103.workers.dev/api"

DELETE_AFTER = 60 * 60  # 1 hour


def is_terabox_url(text: str) -> bool:
    if not text:
        return False

    text = text.lower()

    domains = [
        "terabox.com",
        "1024terabox.com",
        "terabox.app",
        "teraboxshare.com",
        "teraboxlink.com",
        "terasharelink.com",
        "terafileshare.com",
        "terasharefile.com",
        "freeterabox.com",
        "teraboxapp.com",
    ]

    return any(domain in text for domain in domains)


def get_terabox_info(url: str):
    """
    Ask the TeraBox API for file information and direct download link.
    """

    response = requests.get(
        PROCESSOR_URL,
        params={"url": url},
        timeout=(15, 60),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120 Safari/537.36"
            )
        },
    )

    print("Processor HTTP status:", response.status_code)
    print("Processor response:", response.text[:3000])

    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise Exception(
            data.get("message")
            or data.get("error")
            or "Processor could not resolve the TeraBox link."
        )

    files = data.get("files") or data.get("data")

    if not files:
        raise Exception("No file information was returned by the processor.")

    if isinstance(files, dict):
        files = [files]

    file_info = files[0]

    filename = (
        file_info.get("filename")
        or file_info.get("file_name")
        or file_info.get("name")
        or "TeraBox_File"
    )

    download_url = (
        file_info.get("download_link")
        or file_info.get("direct_link")
        or file_info.get("dlink")
        or file_info.get("url")
    )

    if not download_url:
        raise Exception("Processor did not return a download URL.")

    return filename, download_url


def download_file(download_url: str, filename: str):
    """
    Download the file to temporary GitHub Actions storage.
    """

    safe_name = Path(filename).name

    temp_dir = tempfile.mkdtemp(prefix="terabox_")
    file_path = os.path.join(temp_dir, safe_name)

    print("Downloading:", safe_name)

    with requests.get(
        download_url,
        stream=True,
        timeout=(20, 120),
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120 Safari/537.36"
            )
        },
    ) as response:

        response.raise_for_status()

        total = 0

        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    total += len(chunk)

        print("Downloaded bytes:", total)

    return file_path


async def delete_later(
    bot,
    chat_id: int,
    message_id: int,
    file_path: str,
):
    """
    Delete Telegram message and temporary file after 1 hour.
    """

    await asyncio.sleep(DELETE_AFTER)

    try:
        await bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
        )
        print("Telegram file message deleted.")
    except Exception as e:
        print("Telegram delete error:", e)

    try:
        if os.path.exists(file_path):
            os.remove(file_path)

        parent = os.path.dirname(file_path)

        if os.path.isdir(parent):
            try:
                os.rmdir(parent)
            except OSError:
                pass

        print("Temporary file deleted.")

    except Exception as e:
        print("Temporary file delete error:", e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "Send me a public TeraBox share link.\n\n"
        "I will try to process the file and send it here."
    )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    if not is_terabox_url(text):
        await update.message.reply_text(
            "❌ Please send a valid public TeraBox share link."
        )
        return

    processing_message = await update.message.reply_text(
        "🔗 TeraBox Link Received!\n\n"
        "⏳ Getting file information..."
    )

    file_path = None

    try:

        # STEP 1
        await processing_message.edit_text(
            "🔗 TeraBox Link Received!\n\n"
            "⏳ Connecting to TeraBox processor..."
        )

        filename, download_url = await asyncio.to_thread(
            get_terabox_info,
            text,
        )

        print("Filename:", filename)
        print("Download URL received.")

        # STEP 2
        await processing_message.edit_text(
            "📁 File found!\n\n"
            f"📄 {filename}\n\n"
            "⬇️ Downloading file..."
        )

        file_path = await asyncio.to_thread(
            download_file,
            download_url,
            filename,
        )

        # STEP 3
        await processing_message.edit_text(
            "📤 Uploading file to Telegram..."
        )

        with open(file_path, "rb") as document:

            sent_message = await update.message.reply_document(
                document=document,
                caption=(
                    f"📁 {filename}\n\n"
                    "⏰ This file will be automatically deleted "
                    "after 1 hour."
                ),
            )

        # Remove processing message
        try:
            await processing_message.delete()
        except Exception:
            pass

        # STEP 4
        asyncio.create_task(
            delete_later(
                context.bot,
                update.effective_chat.id,
                sent_message.message_id,
                file_path,
            )
        )

    except requests.exceptions.Timeout:

        await processing_message.edit_text(
            "❌ Processor Timeout!\n\n"
            "TeraBox processor did not respond in time.\n\n"
            "Please try again with another public TeraBox link."
        )

        if file_path and os.path.exists(file_path):
            os.remove(file_path)

    except requests.exceptions.HTTPError as e:

        await processing_message.edit_text(
            "❌ Processor HTTP Error.\n\n"
            f"Status: {getattr(e.response, 'status_code', 'Unknown')}\n\n"
            "Please try again later."
        )

        if file_path and os.path.exists(file_path):
            os.remove(file_path)

    except Exception as e:

        print("BOT ERROR:", repr(e))

        await processing_message.edit_text(
            "❌ Download failed.\n\n"
            f"Reason: {str(e)[:800]}"
        )

        if file_path and os.path.exists(file_path):
            os.remove(file_path)


def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Add BOT_TOKEN in GitHub Secrets."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    print("====================================")
    print("TeraBox Telegram Bot Started")
    print("Force Join: DISABLED")
    print("Auto Delete: 1 hour")
    print("Processor:", PROCESSOR_URL)
    print("====================================")

    application.run_polling(
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
