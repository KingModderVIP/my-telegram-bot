from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from flask import Flask
from threading import Thread
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)
import datetime
import time
import requests
from bs4 import BeautifulSoup

# === Config ===
BOT_TOKEN = "7536984651:AAFWR-wywUJc4EiSX_SCMgCwEP4P8sweVCg"
ADMIN_CHAT_ID = 6972189106
COOLDOWN_SECONDS = 86400

LOGIN_URL = "https://kingmodder.com/login/public/"
RESET_URL_TEMPLATE = "https://kingmodder.com/login/public/keys/reset?userkey={}&reset=1"
ADMIN_USERNAME = "rc24piyush"
ADMIN_PASSWORD = "admin123"

ASK_GAME, ASK_KEY = range(2)
user_request_map = {}
user_last_request_time = {}
key_submission_times = {}
submitted_keys = set()
banned_users = {}
all_users = set()  # ⬅️ Track all unique users

GAMES = [
    "Dream Cricket 25",
    "Real Cricket 24",
    "Real Cricket 20",
    "Cricket League",
    "WCC3",
    "WCC2",
    "Sachin Saga Pro Cricket",
    "Hitwicket Superstars",
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    all_users.add(user_id)  # Track user
    now = time.time()
    if user_id in banned_users and banned_users[user_id] > now:
        remaining = int(banned_users[user_id] - now)
        h, m, s = remaining // 3600, (remaining % 3600) // 60, remaining % 60
        await update.message.reply_text(
            f"🚫 You are banned.\n⏳ Try again in: *{h}h {m}m {s}s*",
            parse_mode="Markdown")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(f"🎮 {game}", callback_data=game)]
                for game in GAMES]
    await update.message.reply_text(
        "🎯 *Select the game you want to reset the key for:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown")
    return ASK_GAME


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)


async def game_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    game = query.data
    context.user_data["game_name"] = game
    await query.edit_message_text(
        text=f"✅ *Game Selected:* {game}\n\n🔐 Now enter your *mod key*.",
        parse_mode="Markdown")
    return ASK_KEY


async def get_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action("typing")
    key = update.message.text.strip().lower()
    user = update.message.from_user
    user_id = user.id
    all_users.add(user_id)  # Track user
    username = user.username or "N/A"
    full_name = user.full_name
    game = context.user_data.get("game_name")
    now = time.time()
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if user_id in banned_users and banned_users[user_id] > now:
        remaining = int(banned_users[user_id] - now)
        h, m, s = remaining // 3600, (remaining % 3600) // 60, remaining % 60
        await update.message.reply_text(
            f"🚫 You are banned.\n⏳ Try again in: *{h}h {m}m {s}s*",
            parse_mode="Markdown")
        return ConversationHandler.END

    if key in key_submission_times:
        remaining = int(COOLDOWN_SECONDS - (now - key_submission_times[key]))
        if remaining > 0:
            h, m, s = remaining // 3600, (remaining %
                                          3600) // 60, remaining % 60
            await update.message.reply_text(
                f"⏳ *This key has already been submitted.*\n🔁 Try again in: *{h}h {m}m {s}s*",
                parse_mode="Markdown")
            return ConversationHandler.END

    if user_id in user_last_request_time:
        remaining = int(COOLDOWN_SECONDS -
                        (now - user_last_request_time[user_id]))
        if remaining > 0:
            h, m, s = remaining // 3600, (remaining %
                                          3600) // 60, remaining % 60
            await update.message.reply_text(
                f"⏳ *You already submitted a request.*\n⏱ Wait: *{h}h {m}m {s}s*",
                parse_mode="Markdown")
            return ConversationHandler.END

    key_submission_times[key] = now
    user_last_request_time[user_id] = now
    submitted_keys.add(key)

    details_msg = (f"📥 *New Key Reset Request*\n━━━━━━━━━━━━━━━\n"
                   f"🎮 *Game:* `{game}`\n"
                   f"🔑 *Key:* `{key}`\n"
                   f"🙍‍♂️ *Name:* `{full_name}`\n"
                   f"📌 *Username:* @{username}\n"
                   f"🆔 *User ID:* `{user_id}`\n"
                   f"🕒 *Time:* `{timestamp}`\n━━━━━━━━━━━━━━━")

    details = await context.bot.send_message(ADMIN_CHAT_ID,
                                             details_msg,
                                             parse_mode="Markdown")

    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Done",
                             callback_data=f"done:{details.message_id}"),
        InlineKeyboardButton("❌ Fail",
                             callback_data=f"fail:{details.message_id}")
    ]])
    actions = await context.bot.send_message(ADMIN_CHAT_ID,
                                             "What do you want to do?",
                                             reply_markup=buttons)

    user_request_map[details.message_id] = {
        "user_id": user_id,
        "key": key,
        "game": game,
        "action_msg_id": actions.message_id
    }

    await update.message.reply_text(
        f"✅ *Request submitted!*\n\n📌 *Game:* {game}\n🔑 *Key:* `{key}`\n⏳ Please wait for admin approval.",
        parse_mode="Markdown")
    return ConversationHandler.END


def login_and_reset_key(key: str) -> bool:
    session = requests.Session()
    try:
        login_page = session.get(LOGIN_URL)
        soup = BeautifulSoup(login_page.text, "html.parser")
        csrf = soup.find("input", {"name": "csrf_test_name"})["value"]
        data = {
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
            "csrf_test_name": csrf,
            "stay_log": "yes"
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        response = session.post(LOGIN_URL, data=data, headers=headers)
        if "Logout" not in response.text:
            print("❌ Login failed!")
            return False
        reset_url = RESET_URL_TEMPLATE.format(key)
        r = session.get(reset_url)
        return r.json().get("reset", False)
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return False


async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("done:") or data.startswith("fail:"):
        msg_id = int(data.split(":")[1])
        info = user_request_map.get(msg_id)
        if not info:
            await query.edit_message_text("⚠️ Request not found.")
            return

        user_id = info["user_id"]
        key = info["key"]
        game = info["game"]

        if data.startswith("done:"):
            success = login_and_reset_key(key)
            if success:
                await context.bot.send_message(
                    user_id,
                    f"✅ Your key for *{game}* has been reset!",
                    parse_mode="Markdown")
                await query.edit_message_text("✅ Reset completed.")
            else:
                await query.edit_message_text(
                    "❌ Reset failed. Login or key error.")
        elif data.startswith("fail:"):
            banned_users[user_id] = time.time() + COOLDOWN_SECONDS
            await context.bot.send_message(
                user_id,
                "❌ Your key is invalid or rejected.\n⛔ You are blocked for 24 hours.",
                parse_mode="Markdown")
            await query.edit_message_text("🚫 User banned for 24 hours.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 *Help*\n/start – Start\n/reset – Restart\n/cancel – Cancel\n/help – Help\n/broadcast <message> – Admin only",
        parse_mode="Markdown")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != ADMIN_CHAT_ID:
        await update.message.reply_text("🚫 You are not authorized to use this command.")
        return

    msg = ' '.join(context.args)
    if not msg:
        await update.message.reply_text("⚠️ Please provide a message to broadcast.\nExample:\n`/broadcast Hello users!`", parse_mode="Markdown")
        return

    success = 0
    failed = 0
    for user_id in list(all_users):
        try:
            await context.bot.send_message(user_id, f"📢 *Broadcast:*\n{msg}", parse_mode="Markdown")
            success += 1
        except:
            failed += 1

    await update.message.reply_text(f"✅ Broadcast sent to {success} users.\n❌ Failed: {failed}")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_GAME: [CallbackQueryHandler(game_selected)],
            ASK_KEY:
            [MessageHandler(filters.TEXT & ~filters.COMMAND, get_key)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("reset", reset)
        ],
    )
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("broadcast", broadcast))  # ⬅️ Register broadcast
    app.add_handler(
        CallbackQueryHandler(admin_buttons, pattern="^(done|fail):"))
    app.run_polling()


app2 = Flask('')


@app2.route('/')
def home():
    return "Bot running."


def run_web():
    app2.run(host="0.0.0.0", port=8080)


Thread(target=run_web).start()

if __name__ == "__main__":
    main()
