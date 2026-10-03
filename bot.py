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
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ChatMemberHandler,
    filters,
)


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

OWNER_ID = 8762217575
OWNER_USERNAME = "wabillah"
CONTACT_URL = "https://t.me/wabillah"

DB_FILE = "pin_cycle.db"


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect(DB_FILE, check_same_thread=False)
db.row_factory = sqlite3.Row

db.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    access INTEGER DEFAULT 0
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS groups (
    group_id INTEGER PRIMARY KEY,
    group_name TEXT NOT NULL,
    owner_id INTEGER NOT NULL
)
""")

db.commit()


# =========================================================
# ACTIVE CYCLES
# =========================================================

# group_id -> duration in seconds
active_cycles = {}

# group_id -> asyncio.Task
cycle_tasks = {}


# =========================================================
# DATABASE FUNCTIONS
# =========================================================

def has_access(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True

    row = db.execute(
        "SELECT access FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    return bool(row and row["access"] == 1)


def grant_access(user_id: int):
    db.execute(
        """
        INSERT INTO users (user_id, access)
        VALUES (?, 1)
        ON CONFLICT(user_id)
        DO UPDATE SET access = 1
        """,
        (user_id,)
    )
    db.commit()


def revoke_access(user_id: int):
    db.execute(
        "UPDATE users SET access = 0 WHERE user_id = ?",
        (user_id,)
    )
    db.commit()


def save_group(group_id: int, group_name: str, owner_id: int):
    db.execute(
        """
        INSERT INTO groups (group_id, group_name, owner_id)
        VALUES (?, ?, ?)
        ON CONFLICT(group_id)
        DO UPDATE SET
            group_name = excluded.group_name,
            owner_id = excluded.owner_id
        """,
        (group_id, group_name, owner_id)
    )
    db.commit()


def remove_group(group_id: int, owner_id: int):
    db.execute(
        """
        DELETE FROM groups
        WHERE group_id = ? AND owner_id = ?
        """,
        (group_id, owner_id)
    )
    db.commit()


def get_user_groups(user_id: int):
    return db.execute(
        """
        SELECT group_id, group_name
        FROM groups
        WHERE owner_id = ?
        ORDER BY group_name
        """,
        (user_id,)
    ).fetchall()


def user_owns_group(user_id: int, group_id: int) -> bool:
    row = db.execute(
        """
        SELECT 1 FROM groups
        WHERE group_id = ? AND owner_id = ?
        """,
        (group_id, user_id)
    ).fetchone()

    return row is not None


# =========================================================
# KEYBOARDS
# =========================================================

def contact_button():
    return InlineKeyboardButton(
        "👤 Contact Owner",
        url=CONTACT_URL
    )


def main_keyboard():
    return InlineKeyboardMarkup([
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
            contact_button()
        ]
    ])


def back_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="back_main"
            )
        ]
    ])


def add_group_reply_keyboard():
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    "➕ Select Group",
                    request_chat={
                        "request_id": 1001,
                        "chat_is_channel": False,
                        "bot_is_member": True,
                        "bot_administrator_rights": {
                            "can_delete_messages": True,
                            "can_pin_messages": True,
                        },
                    },
                )
            ],
            [
                KeyboardButton("⬅️ Back")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# =========================================================
# /START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    if not user:
        return

    if not has_access(user.id):

        keyboard = InlineKeyboardMarkup([
            [contact_button()]
        ])

        await update.message.reply_text(
            "❌ You don't have access to Pin Cycle.\n\n"
            "Please contact the owner to get access.",
            reply_markup=keyboard
        )
        return

    await update.message.reply_text(
        "✅ Pin Cycle",
        reply_markup=main_keyboard()
    )


# =========================================================
# MAIN MENU CALLBACKS
# =========================================================

async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "✅ Pin Cycle",
        reply_markup=main_keyboard()
    )


# =========================================================
# ADD GROUP
# =========================================================

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if not has_access(user_id):
        return

    await query.edit_message_text(
        "➕ Add Group\n\n"
        "Tap the button below and select your group.\n\n"
        "The bot must be an administrator with "
        "Delete Messages and Pin Messages permissions."
    )

    await context.bot.send_message(
        chat_id=user_id,
        text="Select your group:",
        reply_markup=add_group_reply_keyboard()
    )


# =========================================================
# BACK FROM REPLY KEYBOARD
# =========================================================

async def add_group_back(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if not has_access(user_id):
        return

    await update.message.reply_text(
        "✅ Pin Cycle",
        reply_markup=ReplyKeyboardRemove()
    )

    await context.bot.send_message(
        chat_id=user_id,
        text="Choose an option:",
        reply_markup=main_keyboard()
    )


# =========================================================
# GROUP SELECTION
# =========================================================

async def group_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if not has_access(user_id):
        return

    shared = update.message.chat_shared

    if not shared:
        return

    if shared.request_id != 1001:
        return

    group_id = shared.chat_id

    try:
        chat = await context.bot.get_chat(group_id)

        member = await context.bot.get_chat_member(
            group_id,
            context.bot.id
        )

        # Check bot admin status
        if member.status not in ("administrator", "creator"):

            await update.message.reply_text(
                "❌ The bot is not an administrator in this group."
            )
            return

        # If administrator, check permissions
        if member.status == "administrator":

            if not member.can_delete_messages:

                await update.message.reply_text(
                    "❌ Bot needs permission to Delete Messages."
                )
                return

            if not member.can_pin_messages:

                await update.message.reply_text(
                    "❌ Bot needs permission to Pin Messages."
                )
                return

        # Check if another user already owns this group
        existing = db.execute(
            """
            SELECT owner_id
            FROM groups
            WHERE group_id = ?
            """,
            (group_id,)
        ).fetchone()

        if existing and existing["owner_id"] != user_id:

            await update.message.reply_text(
                "❌ This group is already connected to another user."
            )
            return

        save_group(
            group_id,
            chat.title or "Unnamed Group",
            user_id
        )

        await update.message.reply_text(
            f"✅ Group added successfully.\n\n"
            f"Group: {chat.title}\n\n"
            f"You can now use /pin 4h, /pin 8h, "
            f"/pin 12h or /pin 24h in the group.",
            reply_markup=ReplyKeyboardRemove()
        )

        await context.bot.send_message(
            chat_id=user_id,
            text="✅ Pin Cycle",
            reply_markup=main_keyboard()
        )

    except Exception as e:

        print("GROUP SELECTION ERROR:", e)

        await update.message.reply_text(
            "❌ I couldn't connect this group.\n"
            "Please make sure the bot is an administrator."
        )


# =========================================================
# USEFUL COMMANDS
# =========================================================

async def useful_commands(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "📌 /pin 4h",
                copy_text=CopyTextButton(
                    text="/pin 4h"
                )
            )
        ],

        [
            InlineKeyboardButton(
                "📌 /pin 8h",
                copy_text=CopyTextButton(
                    text="/pin 8h"
                )
            )
        ],

        [
            InlineKeyboardButton(
                "📌 /pin 12h",
                copy_text=CopyTextButton(
                    text="/pin 12h"
                )
            )
        ],

        [
            InlineKeyboardButton(
                "📌 /pin 24h",
                copy_text=CopyTextButton(
                    text="/pin 24h"
                )
            )
        ],

        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="back_main"
            )
        ]
    ])

    await query.edit_message_text(
        "📋 Useful Commands\n\n"
        "Use these commands in your group.\n"
        "Tap any command to copy it and use it in your group.",
        reply_markup=keyboard
    )


# =========================================================
# CANCEL OLD CYCLE
# =========================================================

async def cancel_old_cycle(group_id: int):

    active_cycles.pop(group_id, None)

    task = cycle_tasks.pop(group_id, None)

    if task and not task.done():

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass


# =========================================================
# /PIN COMMAND
# =========================================================

async def pin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.message

    if not message:
        return

    user = update.effective_user

    if not user:
        return

    # Only group / supergroup
    if message.chat.type not in ("group", "supergroup"):
        return

    # User must have access
    if not has_access(user.id):
        return

    group_id = message.chat.id

    # User must own this group
    if not user_owns_group(user.id, group_id):

        try:
            await message.delete()
        except Exception:
            pass

        return

    # Check command
    text = message.text.lower().strip()

    duration_map = {
        "/pin 4h": 4 * 60 * 60,
        "/pin 8h": 8 * 60 * 60,
        "/pin 12h": 12 * 60 * 60,
        "/pin 24h": 24 * 60 * 60,
    }

    if text not in duration_map:
        return

    duration = duration_map[text]

    # Delete command immediately
    try:
        await message.delete()
    except Exception as e:
        print("COMMAND DELETE ERROR:", e)

    # Cancel any previous cycle
    await cancel_old_cycle(group_id)

    # Start new waiting cycle
    active_cycles[group_id] = duration

    hours = duration // 3600

    await context.bot.send_message(
        chat_id=group_id,
        text=(
            f"✅ Pin Cycle is ready. "
            f"The next post will be pinned for {hours} hours, "
            f"except admins."
        )
    )


# =========================================================
# MEMBER MESSAGE HANDLER
# =========================================================

async def handle_group_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = update.message

    if not message:
        return

    group_id = message.chat.id

    # No active cycle
    if group_id not in active_cycles:
        return

    user = message.from_user

    if not user:
        return

    # Ignore bot messages
    if user.is_bot:
        return

    # Ignore admins / creator
    try:

        member = await context.bot.get_chat_member(
            group_id,
            user.id
        )

        if member.status in ("administrator", "creator"):
            return

    except Exception as e:

        print("MEMBER CHECK ERROR:", e)
        return

    # Get duration
    duration = active_cycles.pop(group_id)

    # Pin message
    try:

        await message.pin(
            disable_notification=True
        )

    except Exception as e:

        print("PIN ERROR:", e)

        await context.bot.send_message(
            chat_id=group_id,
            text=(
                "❌ I couldn't pin the message.\n"
                "Please check my Pin Messages permission."
            )
        )

        return

    # Start unpin timer
    task = asyncio.create_task(
        unpin_after(
            context,
            group_id,
            message.message_id,
            duration
        )
    )

    cycle_tasks[group_id] = task


# =========================================================
# UNPIN AFTER DURATION
# =========================================================

async def unpin_after(
    context: ContextTypes.DEFAULT_TYPE,
    group_id: int,
    message_id: int,
    duration: int
):

    try:

        await asyncio.sleep(duration)

        await context.bot.unpin_chat_message(
            chat_id=group_id,
            message_id=message_id
        )

        print(
            f"Unpinned message {message_id} "
            f"from group {group_id}"
        )

    except asyncio.CancelledError:

        print(
            f"Cycle cancelled for group {group_id}"
        )

        raise

    except Exception as e:

        print("UNPIN ERROR:", e)

    finally:

        cycle_tasks.pop(group_id, None)


# =========================================================
# /ACCESS
# =========================================================

async def access_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user or user.id != OWNER_ID:
        return

    if not context.args:

        await update.message.reply_text(
            "Usage:\n/access USER_ID"
        )
        return

    try:

        target_id = int(context.args[0])

    except ValueError:

        await update.message.reply_text(
            "❌ Invalid USER ID."
        )
        return

    grant_access(target_id)

    await update.message.reply_text(
        f"✅ Access granted to {target_id}"
    )


# =========================================================
# /REMOVE
# =========================================================

async def remove_access(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user or user.id != OWNER_ID:
        return

    if not context.args:

        await update.message.reply_text(
            "Usage:\n/remove USER_ID"
        )
        return

    try:

        target_id = int(context.args[0])

    except ValueError:

        await update.message.reply_text(
            "❌ Invalid USER ID."
        )
        return

    revoke_access(target_id)

    await update.message.reply_text(
        f"✅ Access removed from {target_id}"
    )


# =========================================================
# BOT ADDED / REMOVED FROM GROUP
# =========================================================

async def bot_status_update(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    chat_member = update.my_chat_member

    if not chat_member:
        return

    new_status = chat_member.new_chat_member.status

    if new_status in ("left", "kicked"):

        group_id = chat_member.chat.id

        # Cancel cycle
        await cancel_old_cycle(group_id)

        # Remove database record
        db.execute(
            "DELETE FROM groups WHERE group_id = ?",
            (group_id,)
        )

        db.commit()


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "BOT ERROR:",
        context.error
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Private chat
    application.add_handler(
        CommandHandler(
            "start",
            start,
            filters=filters.ChatType.PRIVATE
        )
    )

    # Owner access management
    application.add_handler(
        CommandHandler(
            "access",
            access_command,
            filters=filters.ChatType.PRIVATE
        )
    )

    application.add_handler(
        CommandHandler(
            "remove",
            remove_access,
            filters=filters.ChatType.PRIVATE
        )
    )

    # Inline buttons
    application.add_handler(
        CallbackQueryHandler(
            back_main,
            pattern="^back_main$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            add_group,
            pattern="^add_group$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            useful_commands,
            pattern="^useful_commands$"
        )
    )

    # Group /pin command
    application.add_handler(
        CommandHandler(
            "pin",
            pin_command,
            filters=filters.ChatType.GROUPS
        )
    )

    # Reply keyboard Back
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & filters.Regex("^⬅️ Back$"),
            add_group_back
        )
    )

    # Telegram group selector
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & filters.StatusU
