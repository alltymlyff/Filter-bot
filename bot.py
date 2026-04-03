import os
import random
import re
import asyncio
import logging
import requests
from pymongo import MongoClient
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# ===== CONFIG =====
TOKEN = ""
MONGO_URI = ""
CHANNEL_ID = -1003635542803
FORCE_CHANNEL = -1001798846083   # must join

AUTO_DELETE_TIME = 300  # seconds

RANDOM_IMAGES = [
    "https://postimg.cc/dDTnngyd",
    "https://postimg.cc/3WD99zvX",
    "https://postimg.cc/14NMMbqr",
    "https://postimg.cc/14NMMbqr"
]

REACTIONS = ["🔥", "😍", "🎬", "💯", "👍"]

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)

# ===== DB =====
client = MongoClient(MONGO_URI)
db = client["telegram_bot"]
collection = db["files"]

# ===== FOLDER =====
if not os.path.exists("files"):
    os.makedirs("files")


# ===== FUNCTIONS =====
def clean_text(text):
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip().title()


def generate_short_link(url):
    try:
        return requests.get(f"http://tinyurl.com/api-create.php?url={url}").text
    except:
        return url


async def auto_delete(msg, delay):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except:
        pass


async def check_subscription(user_id, context):
    try:
        member = await context.bot.get_chat_member(FORCE_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False


# ===== CHANNEL HANDLER =====
async def handle_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.channel_post
        if not message:
            return

        file = None
        file_name = "unknown"

        if message.document:
            file = message.document
            file_name = file.file_name

        elif message.video:
            file = message.video
            file_name = f"{file.file_unique_id}.mp4"

        elif message.photo:
            file = message.photo[-1]
            file_name = f"{file.file_unique_id}.jpg"

        if not file:
            return

        # Download file
        file_obj = await context.bot.get_file(file.file_id)
        file_path = f"files/{file_name}"
        await file_obj.download_to_drive(file_path)

        caption = clean_text(message.caption or file_name)

        # Telegram post link
        post_link = f"https://t.me/c/{str(CHANNEL_ID)[4:]}/{message.message_id}"
        short_link = generate_short_link(post_link)

        # Save in MongoDB
        data = {
            "file_name": file_name,
            "file_path": file_path,
            "caption": caption,
            "short_link": short_link
        }
        collection.insert_one(data)

        print("✅ Saved to DB:", file_name)

        # Random image preview
        random_img = random.choice(RANDOM_IMAGES)

        sent_msg = await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=random_img,
            caption=f"🎬 {caption}\n🔗 {short_link}"
        )

        # Random reaction (reply message)
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=random.choice(REACTIONS),
            reply_to_message_id=sent_msg.message_id
        )

        # Auto delete preview
        asyncio.create_task(auto_delete(sent_msg, AUTO_DELETE_TIME))

    except Exception as e:
        print("❌ Error:", e)


# ===== USER HANDLER (FORCE SUB) =====
async def handle_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id

        if not await check_subscription(user_id, context):
            msg = await update.message.reply_text(
                f"❌ Join channel first: {FORCE_CHANNEL}"
            )
            asyncio.create_task(auto_delete(msg, AUTO_DELETE_TIME))
            return

        await update.message.reply_text("✅ Access granted!")

    except Exception as e:
        print("❌ User Error:", e)


# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Channel posts
    app.add_handler(MessageHandler(filters.Chat(CHANNEL_ID), handle_channel))

    # Private messages
    app.add_handler(MessageHandler(filters.PRIVATE, handle_user))

    print("🚀 BOT RUNNING 24/7...")
    app.run_polling()


if __name__ == "__main__":
    main()
