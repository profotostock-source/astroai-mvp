import database
from services.free_preview import build_free_preview


def test_payment_can_be_retried_until_delivery(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "payments.db")
    database.init_db()
    payment_id = database.save_payment(
        telegram_user_id=123,
        product="year",
        amount_xtr=99,
        invoice_payload="inner_compass:year:123",
        telegram_payment_charge_id="charge-test-1",
    )
    assert payment_id
    assert database.get_pending_payment(123, "year")["id"] == payment_id
    database.mark_payment_delivered(payment_id)
    assert database.get_pending_payment(123, "year") is None


def test_duplicate_charge_is_not_inserted_twice(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "payments.db")
    database.init_db()
    args = dict(
        telegram_user_id=123,
        product="natal",
        amount_xtr=99,
        invoice_payload="inner_compass:natal:123",
        telegram_payment_charge_id="same-charge",
    )
    assert database.save_payment(**args)
    assert database.save_payment(**args) is None


def test_free_preview_contains_core_placements_and_offer():
    text = build_free_preview(
        {"name": "Марія"},
        {
            "sun_sign": "Gem", "moon_sign": "Cap", "ascendant_sign": "Tau",
            "birth_time_known": True,
            "planets": {"venus": {"sign": "Can"}, "mars": {"sign": "Leo"}},
        },
    )
    assert "Безкоштовний міні-портрет" in text
    assert all(label in text for label in ("Сонце", "Місяць", "Асцендент", "Венера", "Марс"))
    assert "99 ⭐" in text
