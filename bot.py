import os
import re
import logging
from datetime import date, datetime
from pathlib import Path

import config
from database import get_user_profile, init_db, upsert_user_profile, save_together_report
from services.astrology import AstrologyError, calculate_natal_chart
from services.pdf_report import PDFGenerationError, generate_report
from services.pdf_year_report import generate_year_report
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

LOG_PATH = Path(__file__).resolve().parent / "bot.log"

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)

LOGGER = logging.getLogger(__name__)

TOKEN = config.TELEGRAM_BOT_TOKEN

NAME, BIRTH_DATE, BIRTH_TIME, BIRTH_CITY, CONFIRMATION = range(5)


# ─────────────────────────────────────────────────────────────────────────────
# Together flow
# ─────────────────────────────────────────────────────────────────────────────

def get_time_known_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Tak, znaiu", callback_data="together_time_yes")],
        [InlineKeyboardButton("Ne znaiu", callback_data="together_time_no")],
    ])


def get_together_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Vse pravylno", callback_data="together_confirm_yes")],
        [InlineKeyboardButton("Vvesty zanovo", callback_data="together_confirm_restart")],
    ])


async def start_together_flow(message, user, context: ContextTypes.DEFAULT_TYPE):
    """Begin the Together data collection flow."""
    try:
        saved_profile = get_user_profile(user.id)
    except Exception:
        LOGGER.exception("Failed to load profile for Together for user %s", user.id)
        await message.reply_text("Ne vdalosia zavantazhyty vash profil.")
        return

    if not saved_profile:
        await message.reply_text(
            "Spochatku potribno zapovnyty svii profil. Vykorystaithe /start."
        )
        return

    context.user_data["together_person_a"] = {
        "name": saved_profile["name"],
        "birth_date": saved_profile["birth_date"],
        "birth_time": saved_profile["birth_time"],
        "birthplace": saved_profile["birthplace"],
    }

    await message.reply_text(
        "Karta stosunkiv porivniuie dvi natalni karty.\n\n"
        f"Persona A -- tse vy ({saved_profile['name']}).\n\n"
        "Teper vvedit dani Persony B.\n\n"
        "Yak zvaty tsiu liudynu?"
    )
    return TOGETHER_PERSON_B_NAME


async def together_get_person_b_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = normalize_spaces(update.message.text)
    if not is_valid_name(name):
        await update.message.reply_text("Vvedit imia (ne menshe 2 symvoliv).")
        return TOGETHER_PERSON_B_NAME

    context.user_data["together_b_name"] = name
    await update.message.reply_text(
        f"Data narodzhennia {name}?\n\nFormat: DD.MM.RRRR"
    )
    return TOGETHER_PERSON_B_DATE


async def together_get_person_b_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    birth_date = normalize_spaces(update.message.text)
    if not parse_birth_date(birth_date):
        await update.message.reply_text("Vvedit korektnu datu u formati DD.MM.RRRR.")
        return TOGETHER_PERSON_B_DATE

    context.user_data["together_b_date"] = birth_date
    name = context.user_data.get("together_b_name", "")
    await update.message.reply_text(
        f"Chy vidomyi tochnyi chas narodzhennia {name}?",
        reply_markup=get_time_known_keyboard(),
    )
    return TOGETHER_PERSON_B_TIME_KNOWN


async def together_handle_time_known(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    if query.data == "together_time_yes":
        context.user_data["together_b_time_known"] = True
        name = context.user_data.get("together_b_name", "")
        await query.message.reply_text(
            f"Chas narodzhennia {name}? Format: HH:MM"
        )
        return TOGETHER_PERSON_B_TIME
    else:
        context.user_data["together_b_time_known"] = False
        context.user_data["together_b_time"] = "Ne znaiu"
        name = context.user_data.get("together_b_name", "")
        await query.message.reply_text(
            f"Misto narodzhennia {name}?\n\nNapryklad: Lviv, Ukraine"
        )
        return TOGETHER_PERSON_B_PLACE


async def together_get_person_b_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    birth_time = normalize_birth_time(update.message.text)
    if not birth_time:
        await update.message.reply_text(
            "Vvedit chas u formati HH:MM abo napishit: ne znaiu."
        )
        return TOGETHER_PERSON_B_TIME

    context.user_data["together_b_time"] = birth_time
    name = context.user_data.get("together_b_name", "")
    await update.message.reply_text(
        f"Misto narodzhennia {name}?\n\nNapryklad: Lviv, Ukraine"
    )
    return TOGETHER_PERSON_B_PLACE


async def together_get_person_b_place(update: Update, context: ContextTypes.DEFAULT_TYPE):
    birthplace = normalize_spaces(update.message.text)

    if "," not in birthplace:
        await update.message.reply_text(
            "Vkazhit takozh krainu.\nNapryklad: Lviv, Ukraine"
        )
        return TOGETHER_PERSON_B_PLACE

    if not is_valid_birth_place(birthplace):
        await update.message.reply_text("Vvedit korektne misto (ne menshe 2 symvoliv).")
        return TOGETHER_PERSON_B_PLACE

    context.user_data["together_b_place"] = birthplace
    name_a = context.user_data.get("together_person_a", {}).get("name", "A")
    name_b = context.user_data.get("together_b_name", "B")
    date_b = context.user_data.get("together_b_date", "")
    time_b = context.user_data.get("together_b_time", "")

    summary = (
        f"Perevirite dani Persony B:\n\n"
        f"Imia: {name_b}\n"
        f"Data narodzhennia: {date_b}\n"
        f"Chas narodzhennia: {time_b}\n"
        f"Misto: {birthplace}\n\n"
        f"Para: {name_a} + {name_b}"
    )
    await update.message.reply_text(summary, reply_markup=get_together_confirm_keyboard())
    return TOGETHER_CONFIRM


async def together_handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    if query.data == "together_confirm_restart":
        context.user_data.pop("together_b_name", None)
        context.user_data.pop("together_b_date", None)
        context.user_data.pop("together_b_time", None)
        context.user_data.pop("together_b_time_known", None)
        context.user_data.pop("together_b_place", None)
        await query.message.reply_text("Vvedit imia Persony B zanovo.")
        return TOGETHER_PERSON_B_NAME

    await deliver_together_report(query.message, update.effective_user, context)
    return ConversationHandler.END


async def deliver_together_report(message, user, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send the Together PDF."""
    from services.astrology import AstrologyError, calculate_natal_chart
    from services.pdf_together_report import generate_together_report
    from services.pdf_report import PDFGenerationError

    profile_a = context.user_data.get("together_person_a", {})
    name_b = context.user_data.get("together_b_name", "")
    date_b = context.user_data.get("together_b_date", "")
    time_b = context.user_data.get("together_b_time", "Ne znaiu")
    place_b = context.user_data.get("together_b_place", "")

    profile_b = {
        "name": name_b,
        "birth_date": date_b,
        "birth_time": time_b,
        "birthplace": place_b,
    }

    notice = await message.reply_text(
        "Hotuiu Kartu stosunkiv. Tse zaiime do khvylyny."
    )

    try:
        chart_a = calculate_natal_chart(profile_a)
        chart_b = calculate_natal_chart(profile_b)
    except AstrologyError as err:
        LOGGER.exception("Natal chart calc failed for Together user %s", user.id)
        await notice.edit_text(f"Ne vdalosia rozrakhuvaty kartu: {err}")
        return
    except Exception:
        LOGGER.exception("Unexpected error in Together chart calc for user %s", user.id)
        await notice.edit_text("Vynykla neperedbachena pomylka. Sprobuite shche raz.")
        return

    try:
        report_path = generate_together_report(
            profile_a=profile_a,
            profile_b=profile_b,
            telegram_user_id=user.id,
            chart_a=chart_a,
            chart_b=chart_b,
        )
    except PDFGenerationError:
        LOGGER.exception("Together PDF gen failed for user %s", user.id)
        await notice.edit_text("Ne vdalosia stvoryty PDF-zvit. Sprobuite shche raz.")
        return
    except Exception:
        LOGGER.exception("Unexpected Together PDF error for user %s", user.id)
        await notice.edit_text("Vynykla neperedbachena pomylka. Sprobuite shche raz.")
        return

    try:
        save_together_report(
            owner_user_id=user.id,
            person_a_name=profile_a.get("name", ""),
            person_a_birth_date=profile_a.get("birth_date", ""),
            person_a_birth_time=profile_a.get("birth_time", ""),
            person_a_birthplace=profile_a.get("birthplace", ""),
            person_a_birth_time_known=chart_a.get("birth_time_known", True),
            person_b_name=name_b,
            person_b_birth_date=date_b,
            person_b_birth_time=time_b,
            person_b_birthplace=place_b,
            person_b_birth_time_known=chart_b.get("birth_time_known", True),
            report_path=str(report_path),
        )
    except Exception:
        LOGGER.exception("Failed to save Together report to DB for user %s", user.id)

    try:
        with open(report_path, "rb") as f:
            await message.reply_document(
                document=f,
                filename=report_path.name,
                caption="Vasha Karta stosunkiv hotova.",
            )
    except Exception:
        LOGGER.exception("Failed to send Together PDF for user %s", user.id)
        await notice.edit_text("Zvit hotovyi, ale ne vdalosia nadislaты fail. Sprobuite shche raz.")
        return

    try:
        await notice.delete()
    except Exception:
        pass

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /report — show report type selection."""
    user = update.effective_user
    try:
        saved_profile = get_user_profile(user.id)
    except Exception:
        LOGGER.exception("Failed to load profile for Telegram user %s", user.id)
        await update.message.reply_text(
            "Наразі не вдалося завантажити ваш профіль. Будь ласка, спробуйте трохи пізніше."
        )
        return

    if not saved_profile:
        await update.message.reply_text(
            "Профіль ще не збережено. Будь ласка, скористайтеся /start, щоб заповнити анкету."
        )
        return

    await ask_report_type(update.message)


BOT_COMMANDS = [
    BotCommand("start", "Заповнити анкету й отримати звіт"),
    BotCommand("report", "Вибрати та згенерувати звіт"),
    BotCommand("profile", "Переглянути збережені дані"),
    BotCommand("cancel", "Скасувати заповнення анкети"),
    BotCommand("help", "Допомога"),
]


async def trace_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id if user else "unknown"

    if update.message and update.message.text is not None:
        LOGGER.info("IN  message from %s: %r", user_id, update.message.text)
    elif update.callback_query:
        LOGGER.info("IN  callback from %s: %r", user_id, update.callback_query.data)
    else:
        LOGGER.info("IN  other update from %s: %s", user_id, update)

    try:
        for handler in context.application.handlers.get(0, []):
            if isinstance(handler, ConversationHandler) and update.effective_chat and user:
                key = (update.effective_chat.id, user.id)
                state = handler._conversations.get(key)
                LOGGER.info("    conversation state for %s: %r", key, state)
                break
    except Exception:
        LOGGER.debug("Could not read conversation state", exc_info=True)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.exception(
        "Unhandled exception while processing update: %s", update, exc_info=context.error
    )


async def post_init(application: Application) -> None:
    try:
        await application.bot.set_my_commands(BOT_COMMANDS)
        LOGGER.info("Bot command menu registered")
    except Exception:
        LOGGER.exception("Failed to register the bot command menu")


def main():
    if not TOKEN:
        raise ValueError("Не знайдено TELEGRAM_BOT_TOKEN у файлі .env")

    try:
        init_db()
    except Exception:
        LOGGER.exception("Database initialization failed")
        raise

    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_date)],
            BIRTH_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_time)],
            BIRTH_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_city)],
            CONFIRMATION: [CallbackQueryHandler(handle_confirmation, pattern="^confirm_")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("help", help_command),
            CommandHandler("profile", profile),
            CommandHandler("report", report),
        ],
        allow_reentry=True,
    )

    # Group -1: trace every update before routing
    app.add_handler(MessageHandler(filters.ALL, trace_update), group=-1)
    app.add_handler(CallbackQueryHandler(trace_update), group=-1)

    app.add_handler(conversation_handler)

    # Together ConversationHandler
    together_conversation_handler = ConversationHandler(
        entry_points=[],
        states={
            TOGETHER_PERSON_B_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, together_get_person_b_name)
            ],
            TOGETHER_PERSON_B_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, together_get_person_b_date)
            ],
            TOGETHER_PERSON_B_TIME_KNOWN: [
                CallbackQueryHandler(together_handle_time_known, pattern="^together_time_")
            ],
            TOGETHER_PERSON_B_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, together_get_person_b_time)
            ],
            TOGETHER_PERSON_B_PLACE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, together_get_person_b_place)
            ],
            TOGETHER_CONFIRM: [
                CallbackQueryHandler(together_handle_confirm, pattern="^together_confirm_")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        name="together_conversation",
    )
    app.add_handler(together_conversation_handler)

    # Report-type selection callback — registered globally so it works after
    # the conversation ends
    app.add_handler(CallbackQueryHandler(handle_report_type, pattern="^report_type_"))

    # Commands available outside the conversation
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("help", help_command))

    app.add_error_handler(on_error)

    print("✅ Bot started...")
    print(f"   Логи пишуться у {LOG_PATH}")
    app.run_polling()


if __name__ == "__main__":
    main()
