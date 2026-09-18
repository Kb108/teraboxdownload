import os
import re
import asyncio

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

CHANNEL_USERNAME = "@loot_dells"
CHANNEL_URL = "https://t.me/loot_dells"

TERABOX_PATTERN = re.compile(
    r"https?://(?:www\.)?"
    r"(?:terabox\.com|teraboxapp\.com|1024terabox\.com)"
    r"/\S+",
    re.IGNORECASE,
)


# ============================================================
# CHECK CHANNEL MEMBERSHIP
# ============================================================

async def check_joined(user_id, context):

    try:
        member = await context.bot.get_chat_member(
            chat_id=CHANNEL_USERNAME,
            user_id=user_id,
        )

        return member.status in (
            "member",
            "administrator",
            "creator",
        )

    except Exception as e:
        print("Membership check error:", e)
        return False


# ============================================================
# JOIN BUTTONS
# ============================================================

def join_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🛍️ Join Shopping Channel",
                url=CHANNEL_URL,
            )
        ],
        [
            InlineKeyboardButton(
                "✅ I've Joined",
                callback_data="check_join",
            )
        ],
    ])


# ============================================================
# START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user_id = update.effective_user.id

    joined = await check_joined(
        user_id,
        context,
    )

    if not joined:

        await update.message.reply_text(
            "🔒 Access Locked\n\n"
            "TeraBox ভিডিও পেতে আগে আমাদের "
            "Shopping Channel-এ Join করুন।\n\n"
            "👇 প্রথমে Channel-এ Join করুন।\n"
            "তারপর নিচের \"I've Joined\" বাটনে চাপুন।",
            reply_markup=join_keyboard(),
        )

        return

    await update.message.reply_text(
        "👋 Welcome!\n\n"
        "🔗 আপনার TeraBox Share Link পাঠান।"
    )


# ============================================================
# I'VE JOINED BUTTON
# ============================================================

async def check_join_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    joined = await check_joined(
        user_id,
        context,
    )

    if not joined:

        await query.edit_message_text(
            "❌ আপনি এখনও Shopping Channel-এ Join করেননি।\n\n"
            "আগে Channel-এ Join করুন এবং তারপর "
            "\"I've Joined\" চাপুন।",
            reply_markup=join_keyboard(),
        )

        return

    await query.edit_message_text(
        "✅ Membership Verified!\n\n"
        "🎉 এখন আপনি TeraBox Link পাঠাতে পারবেন।\n\n"
        "🔗 আপনার TeraBox Share Link পাঠান।"
    )


# ============================================================
# MESSAGE HANDLER
# ============================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user_id = update.effective_user.id

    # --------------------------------------------------------
    # FORCE JOIN CHECK
    # --------------------------------------------------------

    joined = await check_joined(
        user_id,
        context,
    )

    if not joined:

        await update.message.reply_text(
            "🔒 Access Locked\n\n"
            "ভিডিও পেতে আগে আমাদের Shopping Channel-এ Join করুন।",
            reply_markup=join_keyboard(),
        )

        return

    # --------------------------------------------------------
    # GET MESSAGE TEXT
    # --------------------------------------------------------

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

    link = match.group(0)

    # --------------------------------------------------------
    # PROCESSING MESSAGE
    # --------------------------------------------------------

    processing_message = await update.message.reply_text(
        "🔗 TeraBox Link Received!\n\n"
        "⏳ Processing হচ্ছে...\n\n"
        "📎 Link successfully detected."
    )

    print(
        "TeraBox link received:",
        link,
    )

    # --------------------------------------------------------
    # CURRENT STATUS
    # --------------------------------------------------------

    await asyncio.sleep(2)

    await processing_message.edit_text(
        "✅ TeraBox Link Received!\n\n"
        "⚙️ Downloader module এখনো যুক্ত করা হয়নি।\n\n"
        "পরবর্তী ধাপে TeraBox processor "
        "যোগ করা হবে।"
    )


# ============================================================
# ERROR HANDLER
# ============================================================

async def error_handler(
    update,
    context,
):

    print(
        "BOT ERROR:",
        context.error,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN is missing. "
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

    # I've Joined button
    application.add_handler(
        CallbackQueryHandler(
            check_join_callback,
            pattern="^check_join$",
        )
    )

    # Normal messages
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
        "TeraBox Telegram Bot is running..."
    )

    application.run_polling()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
