from datetime import date

from services.transits import format_month_year_ua


def test_all_month_names_are_ukrainian():
    expected = [
        "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
        "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень",
    ]

    actual = [format_month_year_ua(date(2027, month, 1)) for month in range(1, 13)]

    assert actual == [f"{month} 2027" for month in expected]
