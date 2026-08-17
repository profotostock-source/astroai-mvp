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
        # Console history is easy to lose; keep a durable copy for debugging.
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)

LOGGER = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

TOKEN = config.TELEGRAM_BOT_TOKEN

NAME, BIRTH_DATE, BIRTH_TIME, BIRTH_CITY, CONFIRMATION = range(5)
TOGETHER_NAME, TOGETHER_DATE, TOGETHER_TIME_KNOWN, TOGETHER_TIME, TOGETHER_PLACE, TOGETHER_CONFIRM = range(5, 11)

UNKNOWN_TIME_PHRASES = {
    "не знаю",
    "невідомо",
    "не пам’ятаю",
    "не пам'ятаю",
}


def normalize_spaces(value: str) -> str:
    return " ".join(value.split())


def is_valid_name(value: str) -> bool:
    normalized_value = normalize_spaces(value)
    if len(normalized_value) < 2:
        return False

    if normalized_value.isdigit():
        return False

    return True


def parse_birth_date(value: str):
    if not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", value):
        return None

    try:
        parsed_date = datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        return None

    if parsed_date > date.today():
        return None

    return parsed_date


def normalize_birth_time(value: str):
    normalized_value = normalize_spaces(value)
    if normalized_value.lower() in UNKNOWN_TIME_PHRASES:
        return "Не знаю"

    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", normalized_value):
        return None

    return normalized_value


def is_valid_birth_place(value: str) -> bool:
    return len(normalize_spaces(value)) >= 2


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Все правильно", callback_data="confirm_yes")],
            [InlineKeyboardButton("✏️ Ввести заново", callback_data="confirm_restart")],
        ]
    )


def build_summary_text(data) -> str:
    return (
        "Перевірте ваші дані:\n\n"
        f"Ім’я: {data['name']}\n"
        f"Дата народження: {data['birth_date']}\n"
        f"Час народження: {data['birth_time']}\n"
        f"Місце народження: {data['birth_city']}"
    )


async def ask_name_question(message):
    await message.reply_text(
        "👋 Вітаю.\n\n"
        "Я Inner Compass AI.\n"
        "Допоможу зібрати дані для вашого персонального Life Report.\n\n"
        "👤 Будь ласка, введіть ваше ім’я."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ask_name_question(update.message)
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = normalize_spaces(update.message.text)

    if not is_valid_name(name):
        await update.message.reply_text(
            "Будь ласка, введіть коректне ім’я. Воно має містити щонайменше 2 символи та не може складатися лише з цифр."
        )
        return NAME

    context.user_data["name"] = name

    await update.message.reply_text(
        "📅 Будь ласка, введіть вашу дату народження.\n\n"
        "Формат: ДД.ММ.РРРР"
    )
    return BIRTH_DATE


async def get_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    birth_date = normalize_spaces(update.message.text)

    if not parse_birth_date(birth_date):
        await update.message.reply_text(
            "Будь ласка, введіть коректну дату народження у форматі ДД.ММ.РРРР. Дата має існувати та не може бути в майбутньому."
        )
        return BIRTH_DATE

    context.user_data["birth_date"] = birth_date

    await update.message.reply_text(
        "🕒 Будь ласка, введіть ваш час народження.\n\n"
        "Формат: ГГ:ХХ\n\n"
        "Якщо точний час невідомий, напишіть: не знаю."
    )
    return BIRTH_TIME


async def get_birth_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    birth_time = normalize_birth_time(update.message.text)

    if not birth_time:
        await update.message.reply_text(
            "Будь ласка, введіть коректний час у форматі ГГ:ХХ або напишіть: не знаю, невідомо, не пам'ятаю."
        )
        return BIRTH_TIME

    context.user_data["birth_time"] = birth_time

    await update.message.reply_text(
        "🌍 Будь ласка, введіть місто та країну народження.\n\n"
        "Наприклад: Одеса, Україна"
    )
    return BIRTH_CITY


async def get_birth_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    LOGGER.info("HANDLER get_birth_city reached")
    birth_city = normalize_spaces(update.message.text)

    if "," not in birth_city:
        await update.message.reply_text(
            "Будь ласка, вкажіть також країну.\n"
            "Наприклад: Татарбунари, Україна"
        )
        return BIRTH_CITY

    if not is_valid_birth_place(birth_city):
        await update.message.reply_text(
            "Будь ласка, введіть коректне місце народження. Поле має містити щонайменше 2 символи."
        )
        return BIRTH_CITY

    context.user_data["birth_city"] = birth_city

    data = context.user_data
    summary_text = build_summary_text(data)
    confirmation_keyboard = get_confirmation_keyboard()

    LOGGER.info("Birthplace confirmation summary text: %s", summary_text)
    LOGGER.info("Birthplace confirmation keyboard: %r", confirmation_keyboard)

    try:
        await update.message.reply_text(
            summary_text,
            reply_markup=confirmation_keyboard,
        )
    except Exception:
        LOGGER.exception("Failed to send birthplace confirmation message")
        try:
            await update.message.reply_text(summary_text)
        except Exception:
            LOGGER.exception("Fallback confirmation send also failed")
        return BIRTH_CITY

    return CONFIRMATION


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_yes":
        user = update.effective_user

        try:
            upsert_user_profile(
                telegram_user_id=user.id,
                telegram_username=user.username,
                name=context.user_data["name"],
                birth_date=context.user_data["birth_date"],
                birth_time=context.user_data["birth_time"],
                birthplace=context.user_data["birth_city"],
            )
        except Exception:
            LOGGER.exception("Failed to save profile for Telegram user %s", user.id)
            await query.message.reply_text(
                "Наразі не вдалося зберегти ваші дані. Будь ласка, спробуйте ще раз трохи пізніше."
            )
            return CONFIRMATION

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("✅ Дані збережено.")

        context.user_data.clear()
        await deliver_report(query.message, user, context)
        return ConversationHandler.END

    context.user_data.clear()
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(
        "Введення даних розпочато заново."
    )
    await ask_name_question(query.message)

    return NAME


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Створення звіту скасовано. Щоб почати знову, введіть /start."
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ось що я вмію:\n\n"
        "/start — заповнити анкету й отримати звіт\n"
        "/report — згенерувати звіт за збереженими даними\n"
        "/profile — переглянути збережені дані\n"
        "/cancel — скасувати заповнення анкети\n"
        "/help — це повідомлення\n\n"
        "Якщо щось пішло не так — просто надішліть /start ще раз."
    )


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    await update.message.reply_text(
        "Ваш збережений профіль:\n\n"
        f"Ім’я: {saved_profile['name']}\n"
        f"Дата народження: {saved_profile['birth_date']}\n"
        f"Час народження: {saved_profile['birth_time']}\n"
        f"Місце народження: {saved_profile['birthplace']}"
    )


async def deliver_report(message, user, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Build and send the PDF report.

    Takes a plain message object rather than an Update so it can be called both
    from the /report command and from the inline confirmation callback, where
    update.message is None.
    """
    try:
        saved_profile = get_user_profile(user.id)
    except Exception:
        LOGGER.exception("Failed to load profile for report for Telegram user %s", user.id)
        await message.reply_text(
            "Наразі не вдалося підготувати ваш звіт. Будь ласка, спробуйте трохи пізніше."
        )
        return

    if not saved_profile:
        await message.reply_text(
            "Профіль ще не збережено. Будь ласка, скористайтеся /start, щоб заповнити анкету."
        )
        return

    # Chart calculation plus the AI call and PDF build take a while; without
    # this the bot looks frozen.
    notice = await message.reply_text(
        "⏳ Готую ваш звіт. Це займе до хвилини."
    )
    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_DOCUMENT)

    try:
        astrology_data = calculate_natal_chart(saved_profile)
    except AstrologyError:
        LOGGER.exception("Natal chart calculation failed for Telegram user %s", user.id)
        await notice.edit_text(
            "Не вдалося розрахувати натальну карту. Перевірте, будь ласка, місце, дату та час народження."
        )
        return
    except Exception:
        LOGGER.exception("Unexpected astrology error for Telegram user %s", user.id)
        await notice.edit_text(
            "Наразі не вдалося розрахувати натальну карту. Будь ласка, спробуйте трохи пізніше."
        )
        return

    try:
        report_path = generate_report(saved_profile, user.id, astrology_data)
    except PDFGenerationError:
        LOGGER.exception("Failed to generate report for Telegram user %s", user.id)
        await notice.edit_text(
            "Наразі не вдалося створити PDF-звіт. Будь ласка, спробуйте трохи пізніше."
        )
        return
    except Exception:
        LOGGER.exception("Unexpected report error for Telegram user %s", user.id)
        await notice.edit_text(
            "Наразі не вдалося створити PDF-звіт. Будь ласка, спробуйте трохи пізніше."
        )
        return

    try:
        report_exists = report_path.exists()
        report_size = report_path.stat().st_size if report_exists else None
        LOGGER.info(
            "Preparing PDF delivery for Telegram user %s: path=%s exists=%s size=%s",
            user.id,
            report_path,
            report_exists,
            report_size,
        )

        with open(report_path, "rb") as report_file:
            await message.reply_document(
                document=report_file,
                filename=report_path.name,
                caption="Ваш персональний звіт готовий.",
            )
    except Exception:
        LOGGER.exception("Failed to deliver PDF for Telegram user %s", user.id)
        try:
            await notice.edit_text(
                "Звіт створено, але не вдалося надіслати PDF. Спробуйте ще раз."
            )
        except Exception:
            pass
        return

    try:
        await notice.delete()
    except Exception:
        LOGGER.debug("Could not delete the progress notice", exc_info=True)


def get_report_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Inner Compass — натальний звіт", callback_data="report_type_natal")],
        [InlineKeyboardButton("Inner Compass Year — прогноз на рік", callback_data="report_type_year")],
        [InlineKeyboardButton("Inner Compass Together — звіт для пари", callback_data="report_type_together")],
    ])


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    saved = get_user_profile(update.effective_user.id)
    if not saved:
        await update.message.reply_text("Спочатку заповніть профіль командою /start.")
        return
    await update.message.reply_text("Оберіть звіт:", reply_markup=get_report_type_keyboard())


async def deliver_year_report(message, user, context: ContextTypes.DEFAULT_TYPE) -> None:
    saved = get_user_profile(user.id)
    notice = await message.reply_text("Готую річний звіт. Це може тривати до хвилини.")
    try:
        chart = calculate_natal_chart(saved)
        path = generate_year_report(saved, user.id, chart)
        with open(path, "rb") as stream:
            await message.reply_document(stream, filename=path.name, caption="Ваш річний звіт готовий.")
        await notice.delete()
    except Exception:
        LOGGER.exception("Year report failed for user %s", user.id)
        await notice.edit_text("Не вдалося створити річний звіт. Спробуйте ще раз.")


async def handle_report_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    if query.data == "report_type_natal":
        await deliver_report(query.message, update.effective_user, context)
    elif query.data == "report_type_year":
        await deliver_year_report(query.message, update.effective_user, context)


def get_time_known_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Так, знаю", callback_data="together_time_yes")],
        [InlineKeyboardButton("Не знаю", callback_data="together_time_no")],
    ])


def get_together_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Усе правильно", callback_data="together_confirm_yes")],
        [InlineKeyboardButton("Ввести заново", callback_data="together_confirm_restart")],
    ])


async def start_together(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    profile = get_user_profile(update.effective_user.id)
    if not profile:
        await query.message.reply_text("Спочатку заповніть профіль командою /start.")
        return ConversationHandler.END
    context.user_data["together_a"] = dict(profile)
    await query.message.reply_text(f"Перший профіль — {profile['name']}. Введіть ім’я другої людини.")
    return TOGETHER_NAME


async def together_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = normalize_spaces(update.message.text)
    if not is_valid_name(value):
        await update.message.reply_text("Введіть коректне ім’я.")
        return TOGETHER_NAME
    context.user_data["together_b_name"] = value
    await update.message.reply_text("Введіть дату народження у форматі ДД.ММ.РРРР.")
    return TOGETHER_DATE


async def together_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = normalize_spaces(update.message.text)
    if not parse_birth_date(value):
        await update.message.reply_text("Дата некоректна. Формат: ДД.ММ.РРРР.")
        return TOGETHER_DATE
    context.user_data["together_b_date"] = value
    await update.message.reply_text("Чи відомий точний час народження?", reply_markup=get_time_known_keyboard())
    return TOGETHER_TIME_KNOWN


async def together_time_known(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    if query.data == "together_time_yes":
        await query.message.reply_text("Введіть час у форматі ГГ:ХХ.")
        return TOGETHER_TIME
    context.user_data["together_b_time"] = "Не знаю"
    await query.message.reply_text("Введіть місто та країну, наприклад: Львів, Україна.")
    return TOGETHER_PLACE


async def together_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = normalize_birth_time(update.message.text)
    if not value or value == "Не знаю":
        await update.message.reply_text("Введіть точний час у форматі ГГ:ХХ.")
        return TOGETHER_TIME
    context.user_data["together_b_time"] = value
    await update.message.reply_text("Введіть місто та країну, наприклад: Львів, Україна.")
    return TOGETHER_PLACE


async def together_place(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = normalize_spaces(update.message.text)
    if not is_valid_birth_place(value) or "," not in value:
        await update.message.reply_text("Вкажіть місто і країну через кому.")
        return TOGETHER_PLACE
    context.user_data["together_b_place"] = value
    a = context.user_data["together_a"]
    summary = (f"Перевірте дані:\n\nПерша людина: {a['name']}\n"
               f"Друга людина: {context.user_data['together_b_name']}\n"
               f"Дата: {context.user_data['together_b_date']}\n"
               f"Час: {context.user_data['together_b_time']}\nМісце: {value}")
    await update.message.reply_text(summary, reply_markup=get_together_confirm_keyboard())
    return TOGETHER_CONFIRM


async def together_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    if query.data == "together_confirm_restart":
        for key in list(context.user_data):
            if key.startswith("together_b_"):
                context.user_data.pop(key, None)
        await query.message.reply_text("Введіть ім’я другої людини заново.")
        return TOGETHER_NAME
    await deliver_together_report(query.message, update.effective_user, context)
    return ConversationHandler.END


async def deliver_together_report(message, user, context: ContextTypes.DEFAULT_TYPE) -> None:
    from services.pdf_together_report import generate_together_report
    a = context.user_data["together_a"]
    b = {"name": context.user_data["together_b_name"], "birth_date": context.user_data["together_b_date"],
         "birth_time": context.user_data["together_b_time"], "birthplace": context.user_data["together_b_place"]}
    notice = await message.reply_text("Готую звіт для пари. Це може тривати до хвилини.")
    try:
        chart_a, chart_b = calculate_natal_chart(a), calculate_natal_chart(b)
        path = generate_together_report(profile_a=a, profile_b=b, telegram_user_id=user.id, chart_a=chart_a, chart_b=chart_b)
        save_together_report(owner_user_id=user.id,
            person_a_name=a["name"], person_a_birth_date=a["birth_date"], person_a_birth_time=a["birth_time"], person_a_birthplace=a["birthplace"], person_a_birth_time_known=bool(chart_a.get("birth_time_known")),
            person_b_name=b["name"], person_b_birth_date=b["birth_date"], person_b_birth_time=b["birth_time"], person_b_birthplace=b["birthplace"], person_b_birth_time_known=bool(chart_b.get("birth_time_known")), report_path=str(path))
        with open(path, "rb") as stream:
            await message.reply_document(stream, filename=path.name, caption="Ваш звіт для пари готовий.")
        await notice.delete()
    except Exception:
        LOGGER.exception("Together report failed for user %s", user.id)
        await notice.edit_text("Не вдалося створити звіт для пари. Перевірте дані й спробуйте ще раз.")
    finally:
        for key in list(context.user_data):
            if key.startswith("together_"):
                context.user_data.pop(key, None)

BOT_COMMANDS = [
    BotCommand("start", "Заповнити анкету й отримати звіт"),
    BotCommand("report", "Згенерувати звіт за збереженими даними"),
    BotCommand("profile", "Переглянути збережені дані"),
    BotCommand("cancel", "Скасувати заповнення анкети"),
    BotCommand("help", "Допомога"),
]


async def trace_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log every incoming update before the ConversationHandler routes it.

    Registered in group -1, which runs ahead of the real handlers and never
    consumes the update. If a message shows up here but the matching state
    handler never logs, the conversation state was lost rather than the handler
    raising — that distinction is invisible from the handler side alone.
    """
    user = update.effective_user
    user_id = user.id if user else "unknown"

    if update.message and update.message.text is not None:
        LOGGER.info("IN  message from %s: %r", user_id, update.message.text)
    elif update.callback_query:
        LOGGER.info("IN  callback from %s: %r", user_id, update.callback_query.data)
    else:
        LOGGER.info("IN  other update from %s: %s", user_id, update)

    # _conversations is private API; if it moves in a future PTB release we
    # still want the update trace above, so failure here must stay harmless.
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
    """Catch-all so no handler exception is swallowed silently."""
    LOGGER.exception("Unhandled exception while processing update: %s", update, exc_info=context.error)


async def post_init(application: Application) -> None:
    """Register the command menu shown next to the Telegram input field."""
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
            NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)
            ],
            BIRTH_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_date)
            ],
            BIRTH_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_time)
            ],
            BIRTH_CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_birth_city)
            ],
            CONFIRMATION: [
                CallbackQueryHandler(handle_confirmation, pattern="^confirm_")
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("help", help_command),
            CommandHandler("profile", profile),
            CommandHandler("report", report),
        ],
        # Without this, /start is silently ignored for anyone who abandoned the
        # form mid-way: the state handlers filter commands out and entry_points
        # are not re-checked while a conversation is active.
        allow_reentry=True,
    )

    # Group -1 runs before everything else and does not consume the update.
    app.add_handler(MessageHandler(filters.ALL, trace_update), group=-1)
    app.add_handler(CallbackQueryHandler(trace_update), group=-1)

    app.add_handler(conversation_handler)

    together_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_together, pattern="^report_type_together$")],
        states={
            TOGETHER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, together_name)],
            TOGETHER_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, together_date)],
            TOGETHER_TIME_KNOWN: [CallbackQueryHandler(together_time_known, pattern="^together_time_")],
            TOGETHER_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, together_time)],
            TOGETHER_PLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, together_place)],
            TOGETHER_CONFIRM: [CallbackQueryHandler(together_confirm, pattern="^together_confirm_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        name="together_conversation",
    )
    app.add_handler(together_handler)
    app.add_handler(CallbackQueryHandler(handle_report_type, pattern="^report_type_(natal|year)$"))
    # Also registered outside the conversation so they work for users who have
    # no active conversation state.
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("help", help_command))

    app.add_error_handler(on_error)

    print("Bot started...")
    print(f"   Логи пишуться у {LOG_PATH}")
    app.run_polling()


if __name__ == "__main__":
    main()