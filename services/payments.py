"""Telegram Stars checkout helpers for Inner Compass digital reports."""

from __future__ import annotations

import re

from telegram import LabeledPrice, Update
from telegram.ext import ContextTypes

import config
from database import get_pending_payment, save_payment

PRODUCTS = {
    "natal": ("Inner Compass — натальний звіт", "Повний персональний PDF-звіт за натальною картою."),
    "year": ("Inner Compass Year", "Персональний PDF-прогноз на наступні 12 місяців."),
    "together": ("Inner Compass Together", "Повний PDF-звіт про взаємодію двох людей."),
}


def make_payload(product: str, user_id: int) -> str:
    if product not in PRODUCTS:
        raise ValueError("Unknown report product")
    return f"inner_compass:{product}:{user_id}"


def parse_payload(payload: str) -> tuple[str, int] | None:
    match = re.fullmatch(r"inner_compass:(natal|year|together):(\d+)", payload or "")
    return (match.group(1), int(match.group(2))) if match else None


async def send_product_invoice(message, user, context: ContextTypes.DEFAULT_TYPE, product: str) -> None:
    title, description = PRODUCTS[product]
    price = config.REPORT_PRICES_XTR[product]
    await context.bot.send_invoice(
        chat_id=message.chat_id,
        title=title,
        description=description,
        payload=make_payload(product, user.id),
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Акційна ціна — {price} ⭐", amount=price)],
        start_parameter=f"inner-compass-{product}",
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    parsed = parse_payload(query.invoice_payload)
    valid = bool(
        parsed
        and parsed[1] == query.from_user.id
        and query.currency == "XTR"
        and query.total_amount == config.REPORT_PRICES_XTR.get(parsed[0])
    )
    if valid:
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Не вдалося перевірити замовлення. Створіть рахунок ще раз.")


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    parsed = parse_payload(payment.invoice_payload)
    if not parsed or parsed[1] != update.effective_user.id:
        await update.message.reply_text("Платіж отримано, але замовлення не розпізнано. Напишіть у підтримку.")
        return -1
    product, user_id = parsed
    payment_id = save_payment(
        telegram_user_id=user_id,
        product=product,
        amount_xtr=payment.total_amount,
        invoice_payload=payment.invoice_payload,
        telegram_payment_charge_id=payment.telegram_payment_charge_id,
        provider_payment_charge_id=payment.provider_payment_charge_id,
    )
    if payment_id is None:
        await update.message.reply_text("Цей платіж уже зареєстрований. Перевіряю ваш звіт.")
        pending = get_pending_payment(user_id, product)
        payment_id = pending["id"] if pending else None
    dispatch = context.application.bot_data["paid_report_dispatch"]
    return await dispatch(product, update.message, update.effective_user, context, payment_id)
