import os
import sqlite3
import asyncio

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    CopyTextButton,
)
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# =========================================================
# PIN CYCLE CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = 8762217575
OWNER_USERNAME = "wabillah"

DB_FILE = "pincycle.db"


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(DB_FILE, check_same_thread=False)

db.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    active INTEGER DEFAULT 1
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS groups (
    chat_id INTEGER PRIMARY KEY,
    title TEXT,
    owner_id INTEGER
)
""")

db.commit()


# =========================================================
# ACCESS SYSTEM
# =========================================================

def has_access(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True

    row = db.execute(
        "SELECT active FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    return bool(row and row[0] == 1)


def grant_access(user_id: int):
    db.execute(
        """
        INSERT OR REPLACE INTO users(user_id, active)
        VALUES (?, 1)
        """,
        (user_id,)
    )
    db.commit()


def remove_access(user_id: int):
    db.execute(
        "UPDATE users SET active = 0 WHERE user_id = ?",
        (user_id,)
    )
    db.commit()


# =========================================================
# GROUP DATABASE
# =========================================================

def save_group(chat_id: int, title: str, owner_id: int):
    db.execute(
        """
        INSERT OR REPLACE INTO groups(chat_id, title, owner_id)
        VALUES (?, ?, ?)
        """,
        (chat_id, title, owner_id)
    )
    db.commit()


def get_group_owner(chat_id: int):
    row = db.execute(
        "SELECT owner_id FROM groups WHERE chat_id = ?",
        (chat_id,)
    ).fetchone()

    return row[0] if row else None


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    # -------------------------
    # NO ACCESS
    # -------------------------

    if not has_access(user.id):

        keyboard = [
            [
                InlineKeyboardButton(
                    "👤 Contact Owner",
                    url=f"https://t.me/{OWNER_USERNAME}"
                )
            ]
        ]

        await update.message.reply_text(
            "❌ You don't have access to use Pin Cycle.\n\n"
            "Please contact the owner to request access.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    # -------------------------
    # ACCESS GRANTED
    # -------------------------

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Add Group",
                callback_data="add_group"
            )
        ],
        [
            InlineKeyboardButton(
                "📋 Useful Commands",
                callback_data="useful_commands"
            )
        ],
        [
            InlineKeyboardButton(
                "👤 Contact Owner",
                url=f"https://t.me/{OWNER_USERNAME}"
            )
        ]
    ]

    await update.message.reply_text(
        "⚡ Pin Cycle\n\n"
        "Select an option below:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# INLINE BUTTONS
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if not has_access(user_id):

        await query.edit_message_text(
            "❌ You don't have access to use Pin Cycle."
        )

        return

    # =====================================================
    # ADD GROUP
    # =====================================================

    if query.data == "add_group":

        select_button = KeyboardButton(
            "➕ Select Group",
            request_chat={
                "request_id": 1,
                "chat_is_channel": False,
                "chat_is_forum": False,
                "bot_is_member": False,
            }
        )

        keyboard = ReplyKeyboardMarkup(
            [[select_button]],
            resize_keyboard=True,
            one_time_keyboard=True
        )

        await query.message.reply_text(
            "Select the group where you want to use Pin Cycle.",
            reply_markup=keyboard
        )

        return

    # =====================================================
    # USEFUL COMMANDS
    # =====================================================

    if query.data == "useful_commands":

        keyboard = [
            [
                InlineKeyboardButton(
                    text="📋 /pin 4h",
                    copy_text=CopyTextButton(
                        text="/pin 4h"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 /pin 8h",
                    copy_text=CopyTextButton(
                        text="/pin 8h"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 /pin 12h",
                    copy_text=CopyTextButton(
                        text="/pin 12h"
                    )
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 /pin 24h",
                    copy_text=CopyTextButton(
                        text="/pin 24h"
                    )
                )
            ],
        ]

        await query.edit_message_text(
            "📋 Useful Commands\n\n"
            "Tap any command to copy it:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return


# =========================================================
# GROUP SELECTED
# =========================================================

async def group_selected(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user
    shared = update.message.chat_shared

    if not shared:
        return

    if not has_access(user.id):
        return

    chat_id = shared.chat_id

    try:

        chat = await context.bot.get_chat(chat_id)

        if chat.type not in (
            ChatType.GROUP,
            ChatType.SUPERGROUP
        ):

            await update.message.reply_text(
                "❌ Please select a group.",
                reply_markup=ReplyKeyboardRemove()
            )

            return

        # Check bot membership/admin status
        bot_member = await context.bot.get_chat_member(
            chat_id,
            context.bot.id
        )

        if bot_member.status != "administrator":

            await update.message.reply_text(
                "❌ Pin Cycle must be an administrator "
                "in this group.\n\n"
                "Please add the bot as an admin and give it "
                "Pin Messages and Delete Messages permission.",
                reply_markup=ReplyKeyboardRemove()
            )

            return

        # Save group
        save_group(
            chat_id,
            chat.title or "Unnamed Group",
            user.id
        )

        await update.message.reply_text(
            f"✅ Group added successfully.\n\n"
            f"Group: {chat.title}\n\n"
            "You can now use:\n"
            "/pin 4h\n"
            "/pin 8h\n"
            "/pin 12h\n"
            "/pin 24h",
            reply_markup=ReplyKeyboardRemove()
        )

    except Exception as e:

        print("GROUP ERROR:", e)

        await update.message.reply_text(
            "❌ Couldn't add this group.\n\n"
            "Make sure Pin Cycle is added as an administrator.",
            reply_markup=ReplyKeyboardRemove()
        )


# =========================================================
# /PIN COMMAND
# =========================================================

async def pin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    # Only groups
    if chat.type not in (
        ChatType.GROUP,
        ChatType.SUPERGROUP
    ):
        return

    # User must have access
    if not has_access(user.id):
        return

    # Group must belong to this authorized user
    group_owner = get_group_owner(chat.id)

    if group_owner != user.id:
        return

    # Check command argument
    if not context.args:
        return

    value = context.args[0].lower().strip()

    durations = {
        "4h": 4 * 60 * 60,
        "8h": 8 * 60 * 60,
        "12h": 12 * 60 * 60,
        "24h": 24 * 60 * 60,
    }

    if value not in durations:
        return

    seconds = durations[value]

    # =====================================================
    # DELETE /PIN COMMAND IMMEDIATELY
    # =====================================================

    try:
        await message.delete()
    except Exception as e:
        print("COMMAND DELETE ERROR:", e)

    # =====================================================
    # CANCEL PREVIOUS WAITING CYCLE
    # =====================================================

    old_task = context.application.chat_data.get(chat.id, {}).get(
        "pin_task"
    )

    if old_task:
        old_task.cancel()

    # =====================================================
    # SAVE NEW CYCLE
    # =====================================================

    context.application.chat_data.setdefault(chat.id, {})

    context.application.chat_data[chat.id]["waiting"] = True
    context.application.chat_data[chat.id]["duration"] = seconds

    # =====================================================
    # ALERT
    # =====================================================

    await context.bot.send_message(
        chat_id=chat.id,
        text=(
            f"✅ Pin Cycle is ready. "
            f"The next post will be pinned for "
            f"{value[:-1]} hours, except admins."
        )
    )


# =========================================================
# MEMBER MESSAGE
# =========================================================

async def member_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    if chat.type not in (
        ChatType.GROUP,
        ChatType.SUPERGROUP
    ):
        return

    data = context.application.chat_data.get(chat.id)

    if not data:
        return

    # No active /pin command
    if not data.get("waiting"):
        return

    user = message.from_user

    if not user:
        return

    # Ignore bots
    if user.is_bot:
        return

    # =====================================================
    # CHECK ADMIN
    # =====================================================

    try:

        member = await context.bot.get_chat_member(
            chat.id,
            user.id
        )

        if member.status in (
            "administrator",
            "creator"
        ):
            return

    except Exception as e:

        print("MEMBER CHECK ERROR:", e)
        return

    duration = data.get("duration")

    if not duration:
        return

    # =====================================================
    # THIS IS THE NEXT MEMBER POST
    # =====================================================

    data["waiting"] = False

    try:

        await context.bot.pin_chat_message(
            chat_id=chat.id,
            message_id=message.message_id,
            disable_notification=True
        )

    except Exception as e:

        print("PIN ERROR:", e)

        data["waiting"] = True

        return

    # =====================================================
    # START TIMER
    # =====================================================

    task = asyncio.create_task(
        unpin_after(
            context,
            chat.id,
            message.message_id,
            duration
        )
    )

    data["pin_task"] = task


# =========================================================
# AUTO UNPIN
# =========================================================

async def unpin_after(
    context,
    chat_id,
    message_id,
    duration
):

    try:

        await asyncio.sleep(duration)

        try:

            await context.bot.unpin_chat_message(
                chat_id=chat_id,
                message_id=message_id
            )

        except Exception as e:

            print("UNPIN ERROR:", e)

        data = context.application.chat_data.get(chat_id)

        if data:

            data["waiting"] = False
            data.pop("pin_task", None)

    except asyncio.CancelledError:

        pass


# =========================================================
# OWNER ONLY: /ACCESS
# =========================================================

async def access_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    # ONLY OWNER
    if user.id != OWNER_ID:
        return

    if not context.args:

        await update.message.reply_text(
            "Usage:\n\n"
            "/access USER_ID"
        )

        return

    try:

        user_id = int(context.args[0])

    except ValueError:

        await update.message.reply_text(
            "❌ Invalid Telegram user ID."
        )

        return

    grant_access(user_id)

    await update.message.reply_text(
        f"✅ Access granted successfully.\n\n"
        f"User ID: {user_id}"
    )


# =========================================================
# OWNER ONLY: /REMOVE
# =========================================================

async def remove_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    # ONLY OWNER
    if user.id != OWNER_ID:
        return

    if not context.args:

        await update.message.reply_text(
            "Usage:\n\n"
            "/remove USER_ID"
        )

        return

    try:

        user_id = int(context.args[0])

    except ValueError:

        await update.message.reply_text(
            "❌ Invalid Telegram user ID."
        )

        return

    # Owner cannot remove himself
    if user_id == OWNER_ID:

        await update.message.reply_text(
            "❌ You cannot remove the owner."
        )

        return

    remove_access(user_id)

    await update.message.reply_text(
        f"✅ Access removed successfully.\n\n"
        f"User ID: {user_id}"
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update,
    context
):

    print("BOT ERROR:", context.error)


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN is missing. "
            "Add BOT_TOKEN in Railway Variables."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # -------------------------
    # Commands
    # -------------------------

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("pin", pin_command)
    )

    application.add_handler(
        CommandHandler("access", access_command)
    )

    application.add_handler(
        CommandHandler("remove", remove_command)
    )

    # -------------------------
    # Inline buttons
    # -------------------------

    application.add_handler(
        CallbackQueryHandler(button_handler)
    )

    # -------------------------
    # Group selector
    # -------------------------

    application.add_handler(
        MessageHandler(
            filters.StatusUpdate.CHAT_SHARED,
            group_selected
        )
    )

    # -------------------------
    # Group messages
    # -------------------------

    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & ~filters.COMMAND,
            member_message
        )
    )

    application.add_error_handler(error_handler)

    print("Pin Cycle is running...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
