import database


def test_feedback_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "feedback.db")
    feedback_id = database.save_feedback(123, "tester", "Корисний звіт")
    items = database.get_recent_feedback()
    assert feedback_id == 1
    assert items[0]["telegram_user_id"] == 123
    assert items[0]["telegram_username"] == "tester"
    assert items[0]["text"] == "Корисний звіт"