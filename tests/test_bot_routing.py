"""Regression tests for three-product Telegram routing."""

import bot


def test_report_keyboard_exposes_three_products():
    callbacks = [
        button.callback_data
        for row in bot.get_report_type_keyboard().inline_keyboard
        for button in row
    ]
    assert callbacks == [
        "report_type_free",
        "report_type_natal",
        "report_type_year",
        "report_type_together",
    ]


def test_together_states_do_not_overlap_profile_states():
    profile_states = {bot.NAME, bot.BIRTH_DATE, bot.BIRTH_TIME, bot.BIRTH_CITY, bot.CONFIRMATION}
    together_states = {
        bot.TOGETHER_NAME,
        bot.TOGETHER_DATE,
        bot.TOGETHER_TIME_KNOWN,
        bot.TOGETHER_TIME,
        bot.TOGETHER_PLACE,
        bot.TOGETHER_CONFIRM,
    }
    assert profile_states.isdisjoint(together_states)


def test_all_product_handlers_are_callable():
    names = [
        "deliver_report",
        "deliver_year_report",
        "deliver_together_report",
        "handle_report_type",
        "start_together",
    ]
    assert all(callable(getattr(bot, name)) for name in names)