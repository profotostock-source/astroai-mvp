import os
import re
import logging
from datetime import date, datetime

import config
from database import get_user_profile, init_db, upsert_user_profile
from services.astrology import AstrologyError, calculate_natal_chart
from services.pdf import PDFGenerationError, generate_report
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)

LOGGER = logging.getLogger(__name__)

TOKEN = config.TELEGRAM_BOT_TOKEN

NAME, BIRTH_DATE, BIRTH_TIME, BIRTH_CITY, CONFIRMATION = range(5)

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
        "🌍 Будь ласка, введіть місто та країну народження."
    )
    return BIRTH_CITY


async def get_birth_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    birth_city = normalize_spaces(update.message.text)

    if not is_valid_birth_place(birth_city):
        await update.message.reply_text(
            "Будь ласка, введіть коректне місце народження. Поле має містити щонайменше 2 символи."
        )
        return BIRTH_CITY

    context.user_data["birth_city"] = birth_city

    data = context.user_data

    await update.message.reply_text(
        build_summary_text(data),
        reply_markup=get_confirmation_keyboard(),
    )

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
        await query.message.reply_text(
            "Дані збережено. Наступним кроком ми створимо ваш персональний звіт."
        )
        return ConversationHandler.END

    context.user_data.clear()
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(
        "Введення даних розпочато заново."
    )
    await ask_name_question(query.message)

    return NAME


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Створення звіту скасовано. Щоб почати знову, введіть /start."
    )
    return ConversationHandler.END


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


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    try:
        saved_profile = get_user_profile(user.id)
    except Exception:
        LOGGER.exception("Failed to load profile for report for Telegram user %s", user.id)
        await update.message.reply_text(
            "Наразі не вдалося підготувати ваш звіт. Будь ласка, спробуйте трохи пізніше."
        )
        return

    if not saved_profile:
        await update.message.reply_text(
            "Профіль ще не збережено. Будь ласка, скористайтеся /start, щоб заповнити анкету."
        )
        return

    try:
        astrology_data = calculate_natal_chart(saved_profile)
    except AstrologyError as error:
        import traceback

        print("=" * 80)
        print("ASTROLOGY ERROR")
        print("Exception type:", type(error).__name__)
        print("Exception message:", str(error))
        traceback.print_exc()
        print("=" * 80)

        await update.message.reply_text(
            "Не вдалося розрахувати натальну карту. Перевірте, будь ласка, місце, дату та час народження."
        )
        return
    except Exception:
        LOGGER.exception("Unexpected astrology error for Telegram user %s", user.id)
        await update.message.reply_text(
            "Наразі не вдалося розрахувати натальну карту. Будь ласка, спробуйте трохи пізніше."
        )
        return

    try:
        report_path = generate_report(saved_profile, user.id, astrology_data)
    except PDFGenerationError:
        LOGGER.exception("Failed to generate report for Telegram user %s", user.id)
        await update.message.reply_text(
            "Наразі не вдалося створити PDF-звіт. Будь ласка, спробуйте трохи пізніше."
        )
        return
    except Exception:
        LOGGER.exception("Unexpected report error for Telegram user %s", user.id)
        await update.message.reply_text(
            "Наразі не вдалося створити PDF-звіт. Будь ласка, спробуйте трохи пізніше."
        )
        return

    with open(report_path, "rb") as report_file:
        await update.message.reply_document(
            document=report_file,
            filename=report_path.name,
            caption="Ваш демонстраційний звіт готовий.",
        )


def main():
    if not TOKEN:
        raise ValueError("Не знайдено TELEGRAM_BOT_TOKEN у файлі .env")

    try:
        init_db()
    except Exception:
        LOGGER.exception("Database initialization failed")
        raise

    app = ApplicationBuilder().token(TOKEN).build()

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
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conversation_handler)
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("report", report))

    print("✅ Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()