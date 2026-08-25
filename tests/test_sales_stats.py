from datetime import datetime, timedelta, timezone

import database


def _save_payment(user_id, product, amount, charge_id, created_at):
    payment_id = database.save_payment(
        telegram_user_id=user_id,
        product=product,
        amount_xtr=amount,
        invoice_payload=f"inner_compass:{product}:{user_id}",
        telegram_payment_charge_id=charge_id,
    )
    with database.get_connection() as connection:
        connection.execute(
            "UPDATE payments SET created_at = ? WHERE id = ?",
            (created_at.isoformat(), payment_id),
        )
    return payment_id


def test_sales_stats_aggregate_periods_products_and_buyers(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "stats.db")
    now = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)
    first = _save_payment(1, "natal", 99, "today", now - timedelta(hours=1))
    _save_payment(1, "year", 149, "week", now - timedelta(days=3))
    _save_payment(2, "natal", 99, "month", now - timedelta(days=20))
    _save_payment(3, "together", 199, "old", now - timedelta(days=40))
    database.mark_payment_delivered(first)

    stats = database.get_sales_stats(now)

    assert stats["today"] == {"sales": 1, "revenue_xtr": 99}
    assert stats["7_days"] == {"sales": 2, "revenue_xtr": 248}
    assert stats["30_days"] == {"sales": 3, "revenue_xtr": 347}
    assert stats["all_time"] == {"sales": 4, "revenue_xtr": 546, "buyers": 3, "delivered": 1}
    assert stats["products"][0] == {"product": "natal", "sales": 2, "revenue_xtr": 198}


def test_sales_stats_are_zero_without_payments(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "empty-stats.db")
    stats = database.get_sales_stats(datetime(2026, 8, 25, tzinfo=timezone.utc))
    assert stats["all_time"] == {"sales": 0, "revenue_xtr": 0, "buyers": 0, "delivered": 0}
    assert stats["products"] == []