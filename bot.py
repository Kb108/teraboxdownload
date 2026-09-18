```python
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
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Community TeraBox Gateway
GATEWAY_URL = "https://terabox-gateway.onrender.com/api"

# Maximum time to wait for downloading
DOWNLOAD_TIMEOUT = 60 * 60  # 1 hour

# Telegram file delete time
DELETE_AFTER = 60 * 60  # 1 hour

# TeraBox domains
TERABOX_PATTERN = re.compile(
    r"https?://(?:www\.)?"
    r"(?:"
    r"terabox\.com|"
    r"terabox\.app|"
    r"1024terabox\.com|"
    r"teraboxshare\.com|"
    r"teraboxlink\.com|"
    r"terasharefile\.com|"
    r"terafileshare\.com|"
    r"terasharelink\.com"
    r")"
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
        "👋 Welcome to TeraBox Downloader!\n\n"
        "🔗 আপনার TeraBox Share Link পাঠান।\n\n"
        "⚡ আমি File Information বের করে Download করার চেষ্টা করব।"
    )


# ============================================================
# FIND TERABOX LINK
# ============================================================

def get_terabox_link(text: str):

    match = TERABOX_PATTERN.search(text)

    if not match:
        return None

    return match.group(0).rstrip(
        ".,!?)]}>\"'"
    )


# ============================================================
# GET FILE INFORMATION
# ============================================================

async def get_file_information(share_url: str):

    timeout = aiohttp.ClientTimeout(
        total=60
    )

    params = {
        "url": share_url,
        "resolve": "true",
    }

    async with aiohttp.ClientSession(
        timeout=timeout,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/139.0 Safari/537.36"
            )
        },
    ) as session:

        async with session.get(
            GATEWAY_URL,
            params=params,
        ) as response:

            response_text = await response.text()

            if response.status != 200:

                raise Exception(
                    f"Processor HTTP {response.status}: "
                    f"{response_text[:500]}"
                )

            try:
                data = await response.json(
                    content_type=None
                )
            except Exception:

                raise Exception(
                    "Processor returned invalid JSON:\n"
                    + response_text[:500]
                )

            return data


# ============================================================
# EXTRACT FILE DATA
# ============================================================

def extract_files(data):

    # Expected format:
    # {
    #   "status": "success",
    #   "files": [...]
    # }

    if not isinstance(data, dict):

        raise Exception(
            "Invalid processor response."
        )

    status = data.get("status")

    if status not in (
        "success",
        True,
        None,
    ):

        error = (
            data.get("error")
            or data.get("message")
            or "Unknown processor error"
        )

        raise Exception(
            str(error)
        )

    files = data.get("files")

    if not files:

        # Some APIs may return one file
        if data.get("download_link"):

            files = [data]

        else:

            raise Exception(
                "No files found in TeraBox link."
            )

    return files


# ============================================================
# DOWNLOAD FILE
# ============================================================

async def download_file(
    download_url: str,
    output_path: Path,
    progress_message=None,
):

    timeout = aiohttp.ClientTimeout(
        total=DOWNLOAD_TIMEOUT
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/139.0 Safari/537.36"
        ),
        "Referer": "https://www.terabox.com/",
    }

    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=headers,
    ) as session:

        async with session.get(
            download_url,
            allow_redirects=True,
        ) as response:

            if response.status not in (
                200,
                206,
            ):

                raise Exception(
                    f"Download HTTP {response.status}"
                )

            total = response.content_length

            downloaded = 0

            last_update = 0

            with open(
                output_path,
                "wb",
            ) as file:

                async for chunk in response.content.iter_chunked(
                    1024 * 1024
                ):

                    file.write(chunk)

                    downloaded += len(chunk)

                    # Update progress approximately
                    if (
                        progress_message
                        and total
                        and downloaded - last_update
                        > 10 * 1024 * 1024
                    ):

                        percent = int(
                            downloaded
                            * 100
                            / total
                        )

                        try:

                            await progress_message.edit_text(
                                "⬇️ Downloading...\n\n"
                                f"📊 Progress: {percent}%\n"
                                f"📦 {downloaded / 1024 / 1024:.1f} MB"
                            )

                        except Exception:
                            pass

                        last_update = downloaded


# ============================================================
# DELETE AFTER 1 HOUR
# ============================================================

async def delete_later(
    bot,
    chat_id,
    message_id,
    file_path,
):

    await asyncio.sleep(
        DELETE_AFTER
    )

    # Delete Telegram message
    try:

        await bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
        )

        print(
            "Telegram file message deleted:",
            message_id,
        )

    except Exception as e:

        print(
            "Telegram delete error:",
            e,
        )

    # Delete temporary file
    try:

        if os.path.exists(file_path):

            os.remove(
                file_path
            )

            print(
                "Temporary file deleted:",
                file_path,
            )

    except Exception as e:

        print(
            "Temporary file delete error:",
            e,
        )


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
    # FIND LINK
    # --------------------------------------------------------

    share_url = get_terabox_link(
        text
    )

    if not share_url:

        await update.message.reply_text(
            "❌ TeraBox Link পাওয়া যায়নি।\n\n"
            "দয়া করে একটি valid TeraBox Share Link পাঠান।"
        )

        return

    # --------------------------------------------------------
    # PROCESSING MESSAGE
    # --------------------------------------------------------

    processing = await update.message.reply_text(
        "🔗 TeraBox Link Received!\n\n"
        "⏳ TeraBox থেকে file information নেওয়া হচ্ছে..."
    )

    try:

        # ----------------------------------------------------
        # GET FILE INFORMATION
        # ----------------------------------------------------

        data = await get_file_information(
            share_url
        )

        print(
            "Processor response:",
            data,
        )

        files = extract_files(
            data
        )

        # ----------------------------------------------------
        # FIRST FILE
        # ----------------------------------------------------

        file_data = files[0]

        file_name = (
            file_data.get("filename")
            or file_data.get("file_name")
            or file_data.get("name")
            or "terabox_file"
        )

        download_url = (
            file_data.get("download_link")
            or file_data.get("download_url")
            or file_data.get("dlink")
            or file_data.get("url")
        )

        file_size = (
            file_data.get("size")
            or "Unknown"
        )

        if not download_url:

            raise Exception(
                "Processor did not return a download URL."
            )

        # ----------------------------------------------------
        # UPDATE MESSAGE
        # ----------------------------------------------------

        await processing.edit_text(
            "✅ File Information Found!\n\n"
            f"📄 Name: {file_name}\n"
            f"📦 Size: {file_size}\n\n"
            "⬇️ Download শুরু হচ্ছে..."
        )

        # ----------------------------------------------------
        # TEMP FILE
        # ----------------------------------------------------

        suffix = Path(
            file_name
        ).suffix

        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix,
        )

        temp_file.close()

        temp_path = Path(
            temp_file.name
        )

        # ----------------------------------------------------
        # DOWNLOAD
        # ----------------------------------------------------

        try:

            await download_file(
                download_url,
                temp_path,
                processing,
            )

        except Exception:

            if temp_path.exists():

                temp_path.unlink()

            raise

        # ----------------------------------------------------
        # CHECK FILE
        # ----------------------------------------------------

        if not temp_path.exists():

            raise Exception(
                "Downloaded file not found."
            )

        actual_size = (
            temp_path.stat().st_size
        )

        if actual_size <= 0:

            temp_path.unlink()

            raise Exception(
                "Downloaded file is empty."
            )

        # ----------------------------------------------------
        # TELEGRAM UPLOAD
        # ----------------------------------------------------

        await processing.edit_text(
            "📤 Download complete!\n\n"
            "⏳ Telegram-এ file upload হচ্ছে..."
        )

        with open(
            temp_path,
            "rb",
        ) as document:

            sent_message = await update.message.reply_document(
                document=document,
                filename=file_name,
                caption=(
                    "🎬 TeraBox Download\n\n"
                    f"📄 {file_name}\n"
                    f"📦 {actual_size / 1024 / 1024:.2f} MB\n\n"
                    "⏰ এই file 1 ঘণ্টা পরে automatically "
                    "delete হবে।"
                ),
            )

        # ----------------------------------------------------
        # DELETE PROCESSING MESSAGE
        # ----------------------------------------------------

        try:

            await processing.delete()

        except Exception:
            pass

        # ----------------------------------------------------
        # DELETE AFTER 1 HOUR
        # ----------------------------------------------------

        asyncio.create_task(
            delete_later(
                context.bot,
                update.effective_chat.id,
                sent_message.message_id,
                str(temp_path),
            )
        )

        print(
            "File sent successfully:",
            file_name,
        )

    except Exception as e:

        print(
            "TeraBox ERROR:",
            repr(e),
        )

        try:

            await processing.edit_text(
                "❌ TeraBox file process করা যায়নি।\n\n"
                f"Error: {str(e)[:800]}\n\n"
                "🔗 অন্য একটি valid public TeraBox link দিয়ে "
                "আবার চেষ্টা করুন।"
            )

        except Exception:
            pass


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update,
    context,
):

    print(
        "BOT ERROR:",
        repr(context.error),
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN is missing.\n\n"
            "GitHub → Settings → Secrets and variables "
            "→ Actions → BOT_TOKEN check করুন."
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

    # Text messages
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
# RUN
# ============================================================

if __name__ == "__main__":
    main()
```
