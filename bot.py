import os
import re
import asyncio
import tempfile
from pathlib import Path

import aiohttp
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ============================================================
# SETTINGS
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

# TeraBox processor
PROCESSOR_URL = "https://terabox-gateway.onrender.com/api"

# 1 hour
DELETE_AFTER = 60 * 60

# TeraBox link detector
TERABOX_PATTERN = re.compile(
    r"https?://(?:www\.)?"
    r"(?:terabox\.com|teraboxapp\.com|1024terabox\.com)"
    r"/\S+",
    re.IGNORECASE,
)


# ============================================================
# /start
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "👋 Welcome to TeraBox Downloader Bot!\n\n"
        "🔗 আপনার TeraBox Share Link পাঠান।\n\n"
        "⚡ Public TeraBox link হলে আমি file process করার চেষ্টা করব।"
    )


# ============================================================
# FIND TERABOX LINK
# ============================================================

def find_terabox_link(text):

    match = TERABOX_PATTERN.search(text)

    if not match:
        return None

    return match.group(0).rstrip(
        ".,!?)]}>\"'"
    )


# ============================================================
# PROCESS TERABOX LINK
# ============================================================

async def process_terabox(link):

    timeout = aiohttp.ClientTimeout(
        total=120
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/139.0 Safari/537.36"
        )
    }

    params = {
        "url": link
    }

    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=headers
    ) as session:

        async with session.get(
            PROCESSOR_URL,
            params=params
        ) as response:

            result = await response.text()

            print(
                "PROCESSOR STATUS:",
                response.status
            )

            print(
                "PROCESSOR RESPONSE:",
                result[:3000]
            )

            if response.status != 200:

                raise Exception(
                    f"Processor HTTP {response.status}"
                )

            try:

                data = await response.json(
                    content_type=None
                )

            except Exception:

                raise Exception(
                    "Processor JSON response পাওয়া যায়নি."
                )

            return data


# ============================================================
# EXTRACT FILE
# ============================================================

def extract_file(data):

    if not isinstance(data, dict):

        raise Exception(
            "Invalid processor response."
        )

    # Different possible response names
    files = data.get("files")

    if isinstance(files, list) and len(files) > 0:

        file_info = files[0]

    else:

        file_info = data

    file_name = (
        file_info.get("filename")
        or file_info.get("file_name")
        or file_info.get("name")
        or "terabox_file"
    )

    download_url = (
        file_info.get("download_url")
        or file_info.get("download_link")
        or file_info.get("dlink")
        or file_info.get("direct_link")
        or file_info.get("url")
    )

    if not download_url:

        raise Exception(
            "Processor থেকে download link পাওয়া যায়নি."
        )

    return file_name, download_url


# ============================================================
# DOWNLOAD FILE
# ============================================================

async def download_file(
    download_url,
    output_file,
    status_message
):

    timeout = aiohttp.ClientTimeout(
        total=60 * 60
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/139.0 Safari/537.36"
        ),
        "Referer": "https://www.terabox.com/"
    }

    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=headers
    ) as session:

        async with session.get(
            download_url,
            allow_redirects=True
        ) as response:

            if response.status not in (
                200,
                206
            ):

                raise Exception(
                    f"Download HTTP {response.status}"
                )

            downloaded = 0

            with open(
                output_file,
                "wb"
            ) as file:

                async for chunk in response.content.iter_chunked(
                    1024 * 1024
                ):

                    file.write(chunk)

                    downloaded += len(chunk)

                    # Update every 20 MB
                    if downloaded % (
                        20 * 1024 * 1024
                    ) < 1024 * 1024:

                        try:

                            await status_message.edit_text(
                                "⬇️ File Download হচ্ছে...\n\n"
                                f"📦 Downloaded: "
                                f"{downloaded / 1024 / 1024:.1f} MB"
                            )

                        except Exception:
                            pass


# ============================================================
# DELETE FILE AFTER 1 HOUR
# ============================================================

async def delete_after_one_hour(
    bot,
    chat_id,
    message_id,
    file_path
):

    await asyncio.sleep(
        DELETE_AFTER
    )

    # Delete Telegram message
    try:

        await bot.delete_message(
            chat_id=chat_id,
            message_id=message_id
        )

        print(
            "Telegram message deleted."
        )

    except Exception as e:

        print(
            "Telegram delete error:",
            e
        )

    # Delete server file
    try:

        if os.path.exists(file_path):

            os.remove(
                file_path
            )

            print(
                "Temporary file deleted."
            )

    except Exception as e:

        print(
            "Temporary file delete error:",
            e
        )


# ============================================================
# MESSAGE HANDLER
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = update.message.text or ""

    link = find_terabox_link(
        text
    )

    if not link:

        await update.message.reply_text(
            "❌ Valid TeraBox link পাওয়া যায়নি.\n\n"
            "একটি public TeraBox Share Link পাঠান।"
        )

        return

    # --------------------------------------------------------
    # PROCESSING
    # --------------------------------------------------------

    status_message = await update.message.reply_text(
        "🔗 TeraBox Link Received!\n\n"
        "⏳ TeraBox থেকে file information নেওয়া হচ্ছে..."
    )

    temp_path = None

    try:

        # ----------------------------------------------------
        # PROCESS
        # ----------------------------------------------------

        data = await process_terabox(
            link
        )

        file_name, download_url = extract_file(
            data
        )

        print(
            "FILE NAME:",
            file_name
        )

        print(
            "DOWNLOAD URL FOUND"
        )

        await status_message.edit_text(
            "✅ File Information পাওয়া গেছে!\n\n"
            f"📄 File: {file_name}\n\n"
            "⬇️ এখন Download হচ্ছে..."
        )

        # ----------------------------------------------------
        # TEMP FILE
        # ----------------------------------------------------

        extension = Path(
            file_name
        ).suffix

        temp = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension
        )

        temp.close()

        temp_path = temp.name

        # ----------------------------------------------------
        # DOWNLOAD
        # ----------------------------------------------------

        await download_file(
            download_url,
            temp_path,
            status_message
        )

        # ----------------------------------------------------
        # CHECK FILE
        # ----------------------------------------------------

        if not os.path.exists(
            temp_path
        ):

            raise Exception(
                "Downloaded file পাওয়া যায়নি."
            )

        file_size = os.path.getsize(
            temp_path
        )

        if file_size <= 0:

            raise Exception(
                "Downloaded file empty."
            )

        # ----------------------------------------------------
        # TELEGRAM UPLOAD
        # ----------------------------------------------------

        await status_message.edit_text(
            "📤 Download complete!\n\n"
            "⏳ এখন Telegram-এ file পাঠানো হচ্ছে..."
        )

        with open(
            temp_path,
            "rb"
        ) as document:

            sent_message = await update.message.reply_document(
                document=document,
                filename=file_name,
                caption=(
                    "🎬 TeraBox Downloader\n\n"
                    f"📄 {file_name}\n"
                    f"📦 {file_size / 1024 / 1024:.2f} MB\n\n"
                    "⏰ এই file 1 ঘণ্টা পরে automatically "
                    "delete হবে।"
                )
            )

        # ----------------------------------------------------
        # DELETE PROCESSING MESSAGE
        # ----------------------------------------------------

        try:

            await status_message.delete()

        except Exception:
            pass

        # ----------------------------------------------------
        # SCHEDULE DELETE
        # ----------------------------------------------------

        asyncio.create_task(
            delete_after_one_hour(
                context.bot,
                update.effective_chat.id,
                sent_message.message_id,
                temp_path
            )
        )

        print(
            "SUCCESS:",
            file_name
        )

    except Exception as e:

        print(
            "TERABOX ERROR:",
            repr(e)
        )

        # Delete temporary file if error
        if temp_path:

            try:

                if os.path.exists(
                    temp_path
                ):

                    os.remove(
                        temp_path
                    )

            except Exception:
                pass

        try:

            await status_message.edit_text(
                "❌ TeraBox file process করা যায়নি.\n\n"
                f"Error:\n{str(e)[:1000]}\n\n"
                "🔗 অন্য একটি public TeraBox link দিয়ে চেষ্টা করুন।"
            )

        except Exception:
            pass


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update,
    context
):

    print(
        "BOT ERROR:",
        repr(context.error)
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN পাওয়া যায়নি.\n"
            "GitHub Secrets-এ BOT_TOKEN check করুন."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
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
# START BOT
# ============================================================

if __name__ == "__main__":
    main()
