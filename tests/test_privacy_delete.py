import sqlite3

import database


def test_delete_user_data_removes_profile_and_anonymizes_payment(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "privacy.db")
    database.init_db()
    database.upsert_user_profile(42, "person", "Test", "01.01.1990", "12:00", "Kyiv")
    database.save_feedback(42, "person", "Private feedback")
    payment_id = database.save_payment(42, "natal", 99, "inner_compass:natal:42", "charge-private")
    assert payment_id

    database.delete_user_data(42)

    assert database.get_user_profile(42) is None
    with sqlite3.connect(database.DB_PATH) as connection:
        assert connection.execute("SELECT count(*) FROM feedback WHERE telegram_user_id=42").fetchone()[0] == 0
        payment = connection.execute("SELECT telegram_user_id, invoice_payload FROM payments WHERE id=?", (payment_id,)).fetchone()
    assert payment == (0, f"deleted:{payment_id}")
